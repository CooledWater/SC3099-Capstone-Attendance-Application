"""Proof ownership, freshness, expiry, one-use rotation and concurrent races."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import base64
import pytest
from harness import expect, new_key, register_device, device_proof, sign, frames, sequence_image, utc_now

pytestmark = pytest.mark.specification


@pytest.mark.parametrize("fault", ["signature", "wrong_key", "wrong_session", "wrong_owner", "expired", "incomplete"])
def test_device_proof_cannot_be_forged_rebound_or_expired(world, fault):
    meeting = world.session()
    identity, _ = register_device(world)
    proof = device_proof(world, meeting, identity)
    actor = world.student
    if fault == "signature":
        proof["device_signature"] = base64.b64encode(b"x" * 64).decode()
    elif fault == "wrong_key":
        challenge = world.service.rows("device_challenges", id=proof["device_challenge_id"])[0]
        proof["device_signature"] = sign(new_key()[0], challenge["challenge"])
    elif fault == "wrong_session":
        course = world.service.rows("courses", id=meeting["course_id"])[0]
        # Enrollment is already present; create another independent course to
        # avoid treating duplicate enrollment as a successful setup.
        meeting = world.session()
    elif fault == "wrong_owner":
        actor = world.user()
        course = world.service.rows("courses", id=meeting["course_id"])[0]
        world.enroll(course, actor)
    elif fault == "expired":
        world.service.update("device_challenges", proof["device_challenge_id"],
                             expires_at=utc_now().replace(tzinfo=None) - timedelta(seconds=1))
    else:
        proof.pop("device_signature")
    response = world.checkin(meeting, actor, **proof)
    assert response.status_code in (403, 409)
    assert not world.service.rows("checkins", session_id=meeting["id"], student_id=actor.id)


def test_signature_replay_is_checked_after_attendance_row_is_removed(world):
    meeting = world.session()
    identity, _ = register_device(world)
    proof = device_proof(world, meeting, identity)
    record = expect(world.checkin(meeting, **proof), 201)
    assert world.service.rows("device_challenges", id=proof["device_challenge_id"])[0]["state"] == "consumed"
    # Owned scratch DB only. Remove the duplicate guard to test proof freshness
    # independently; preserve the audit rows.
    table = world.service.table("checkins")
    with world.service.engine.begin() as connection:
        connection.execute(table.delete().where(table.c.id == record["id"]))
    expect(world.checkin(meeting, **proof), 409)
    assert not world.service.rows("checkins", session_id=meeting["id"])


def test_device_proof_is_not_consumed_after_closed_window_rejection(world):
    meeting = world.session()
    identity, _ = register_device(world)
    proof = device_proof(world, meeting, identity)
    expect(world.service.api("PATCH", "/sessions/" + meeting["id"], world.admin, json={"status": "closed"}), 200)
    expect(world.checkin(meeting, **proof), 400)
    assert world.service.rows("device_challenges", id=proof["device_challenge_id"])[0]["state"] == "issued"
    assert not world.service.rows("checkins", session_id=meeting["id"])


def test_failed_checkin_after_device_verification_rolls_back_nonce(world):
    import uuid
    meeting = world.session()
    identity, _ = register_device(world)
    proof = device_proof(world, meeting, identity)
    response = world.checkin(meeting, **proof, motion_verification_id=str(uuid.uuid4()))
    expect(response, 400)
    assert world.service.rows("device_challenges", id=proof["device_challenge_id"])[0]["state"] == "issued"
    assert not world.service.rows("checkins", session_id=meeting["id"])
    expect(world.checkin(meeting, **proof), 201)
    assert world.service.rows("device_challenges", id=proof["device_challenge_id"])[0]["state"] == "consumed"


def test_first_submission_race_has_one_record_and_one_audit_pair(world):
    meeting = world.session()
    actor = world.student
    payload = world.payload(meeting)
    import threading
    barrier = threading.Barrier(10)
    def submit(_):
        barrier.wait(timeout=10)
        return world.service.api("POST", "/checkins/", actor, json=payload).status_code
    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(submit, range(10)))
    assert statuses.count(201) == 1 and statuses.count(400) == 9, f"Unexpected race statuses: {statuses}"
    records = world.service.rows("checkins", session_id=meeting["id"])
    assert len(records) == 1
    actions = [row["action"] for row in world.service.rows("audit_logs", resource_id=records[0]["id"])]
    assert sorted(actions) == ["checkin_attempted", "checkin_flagged"]


def test_refresh_rotation_replay(security_world):
    actor = security_world.student
    service = security_world.service
    first = expect(service.api("POST", "/auth/refresh", json={"refresh_token": actor.refresh}), 200)
    assert first["refresh_token"] != actor.refresh
    response = service.api("POST", "/auth/refresh", json={"refresh_token": actor.refresh})
    assert response.status_code == 401, f"{service.name}: refresh replay accepted"
    expect(service.api("POST", "/auth/refresh", json={"refresh_token": first["refresh_token"]}), 200)


def test_concurrent_refresh_reuse_has_exactly_one_winner(strict_world):
    actor = strict_world.student
    service = strict_world.service
    with ThreadPoolExecutor(max_workers=20) as pool:
        statuses = list(pool.map(lambda _: service.api("POST", "/auth/refresh", json={"refresh_token": actor.refresh}).status_code, range(20)))
    assert statuses.count(200) == 1 and statuses.count(401) == 19


def test_logout_revokes_presented_refresh_cookie(security_world):
    world = security_world
    actor = world.student
    expect(world.service.api("POST", "/auth/logout", headers={"Cookie": "saiv_refresh_token=" + actor.refresh}), 200)
    response = world.service.api("POST", "/auth/refresh", json={"refresh_token": actor.refresh})
    assert response.status_code == 401, f"{world.service.name}: logged-out refresh token remains usable"


@pytest.mark.native
def test_motion_requirements_are_server_owned_and_retry_invalidates_previous(world, face):
    world.enroll_face()
    meeting = world.session(require_motion_check=True, require_liveness_check=True, require_face_match=True)
    forged = world.service.api("POST", "/motion/challenges", world.student,
                               json={"session_id": meeting["id"], "challenge": {"version": 1}})
    expect(forged, 422)
    first = expect(world.service.api("POST", "/motion/challenges", world.student, json={"session_id": meeting["id"]}), 201)
    second = expect(world.service.api("POST", "/motion/challenges", world.student, json={"session_id": meeting["id"]}), 201)
    assert first["challenge_id"] != second["challenge_id"]
    spec = second["challenge"]
    assert spec["version"] == 2 and spec["blink_target"] in (1, 2)
    assert spec["turn_direction"] in ("left", "right") and spec["first_action"] in ("blink", "head_turn")
    expect(world.service.api("POST", f"/motion/challenges/{first['challenge_id']}/verify", world.student,
                             json={"frames": frames(sequence_image())}), 404)
    expect(world.checkin(meeting, motion_verification_id=first["challenge_id"]), 400)


@pytest.mark.native
def test_motion_proof_cannot_cross_accounts_or_accept_client_scores(world, face):
    world.enroll_face()
    meeting = world.session(require_motion_check=True)
    challenge = expect(world.service.api("POST", "/motion/challenges", world.student, json={"session_id": meeting["id"]}), 201)
    other = world.user()
    expect(world.service.api("POST", f"/motion/challenges/{challenge['challenge_id']}/verify", other,
                             json={"frames": frames(sequence_image())}), 404)
    expect(world.service.api("POST", f"/motion/challenges/{challenge['challenge_id']}/verify", world.student,
                             json={"frames": frames(sequence_image()), "passed": True, "liveness_score": 1}), 422)
    expect(world.checkin(meeting, motion_verification_id=challenge["challenge_id"]), 409)

