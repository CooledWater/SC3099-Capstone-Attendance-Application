"""Fail-closed outages and database-authoritative concurrency invariants."""
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from harness import Runtime, World, PASSWORD, expect, new_key, register_device


@pytest.mark.specification
def test_real_redis_outage_blocks_protected_security_operations(tmp_path, pytestconfig):
    runtime = Runtime(tmp_path, pytestconfig)
    try:
        world = World(runtime.backend(strict=True))
        actor = world.student
        runtime.redis_process.terminate()
        runtime.redis_process.wait(timeout=5)
        expect(world.service.api("GET", "/users/me", actor), 503)
        expect(world.service.api("POST", "/auth/login", json={"email": actor.email, "password": PASSWORD}), 503)
        expect(world.service.api("POST", "/auth/refresh", json={"refresh_token": actor.refresh}), 503)
        expect(world.service.request("GET", "/health"), 200)
    finally:
        runtime.close()


@pytest.mark.specification
@pytest.mark.parametrize("strict", [False, True])
def test_unavailable_face_service_cannot_fabricate_a_pass(tmp_path, pytestconfig, strict):
    from harness import image_b64
    runtime = Runtime(tmp_path, pytestconfig)
    try:
        # This runtime deliberately starts no face process; its reserved face
        # port has no listener. This is a real transport failure, not a mock.
        world = World(runtime.backend(strict=strict))
        meeting = world.session(require_liveness_check=True)
        response = world.checkin(meeting, liveness_challenge_response=image_b64())
        if strict:
            assert response.status_code in (400, 503)
            assert not world.service.rows("checkins", session_id=meeting["id"])
        else:
            record = expect(response, 201)
            assert record["status"] == "flagged" and record["liveness_passed"] is None
    finally:
        runtime.close()


@pytest.mark.postgres
@pytest.mark.specification
def test_concurrent_registration_cannot_exceed_device_slots(world):
    register_device(world)
    identities = [new_key(), new_key()]
    barrier = threading.Barrier(2)
    def register(identity):
        barrier.wait(timeout=10)
        return world.service.api("POST", "/devices/", world.student, json={
            "device_fingerprint": identity[2], "public_key": identity[1]}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(register, identities))
    assert sorted(statuses) == [201, 409]
    assert len(world.service.rows("devices", user_id=world.student.id, is_active=True)) == 2


@pytest.mark.specification
def test_revoking_device_blocks_issued_proof(world):
    from harness import device_proof
    meeting = world.session()
    identity, device = register_device(world)
    proof = device_proof(world, meeting, identity)
    expect(world.service.api("PATCH", "/devices/" + device["id"], world.student, json={"is_active": False}), 200)
    expect(world.checkin(meeting, **proof), 403)
    assert not world.service.rows("checkins", session_id=meeting["id"])


@pytest.mark.specification
def test_student_cannot_grant_device_trust_or_change_another_device(world):
    _, _ = register_device(world)
    _, second = register_device(world)
    assert second["is_trusted"] is False
    expect(world.service.api("PATCH", "/devices/" + second["id"], world.student, json={"is_trusted": True}), 403)
    other = world.user()
    expect(world.service.api("PATCH", "/devices/" + second["id"], other, json={"is_active": False}), 403)
    row = world.service.rows("devices", id=second["id"])[0]
    assert row["is_trusted"] is False and row["is_active"] is True


@pytest.mark.native
@pytest.mark.specification
def test_required_biometric_failures_cannot_be_approved_by_trusted_device(world, face):
    from harness import png_b64, device_proof
    world.enroll_face()
    meeting = world.session(require_liveness_check=True, require_face_match=True, risk_threshold=1)
    identity, _ = register_device(world)
    record = expect(world.checkin(meeting, liveness_challenge_response=png_b64(),
                                  **device_proof(world, meeting, identity)), 201)
    assert record["liveness_passed"] is False and record["status"] == "rejected"
    assert record["face_match_passed"] is False


@pytest.mark.specification
def test_missing_required_biometrics_never_fabricates_a_pass(security_world):
    world = security_world
    meeting = world.session(require_liveness_check=True, require_face_match=True)
    response = world.checkin(meeting)
    if world.service.name == "strict":
        expect(response, 400)
        assert not world.service.rows("checkins", session_id=meeting["id"])
    else:
        record = expect(response, 201)
        assert record["status"] == "flagged"
        assert record["liveness_passed"] is None and record["face_match_passed"] is None

