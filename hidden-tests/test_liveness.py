"""Actual sequence HTTP validation and native rejection; positive captures in corpus."""
from datetime import timedelta
import copy
import pytest
from harness import expect, frames, image_b64, sequence_image, assert_private, utc_now

pytestmark = [pytest.mark.specification, pytest.mark.native]


@pytest.fixture(scope="module")
def sequence_reference(face):
    image = sequence_image()
    body = expect(face.request("POST", "/face/enroll", json={"user_id": "hidden-sequence", "image": image, "camera_consent": True}), 201)
    return image, body["face_template_hash"]


@pytest.mark.parametrize("challenge", [None,
    {"version": 2, "blink_target": 1, "turn_direction": "left", "first_action": "blink"},
    {"version": 2, "blink_target": 2, "turn_direction": "right", "first_action": "head_turn"}])
def test_repeated_static_photo_cannot_pass_motion(face, sequence_reference, challenge):
    image, reference = sequence_reference
    payload = {"frames": frames(image), "reference_template_hash": reference}
    if challenge:
        payload["challenge"] = challenge
    result = expect(face.request("POST", "/liveness/sequence", json=payload), 200)
    assert result["passed"] is False
    if challenge:
        assert result["challenge_version"] == 2
    assert_private(str(result), image, reference)


@pytest.mark.parametrize("fault", ["too_few", "too_many", "duplicate", "descending", "gap", "late_start",
    "too_short", "negative", "over_duration", "boolean_time", "string_time", "per_frame_oversize", "total_oversize"])
def test_invalid_sequences_fail_before_inference(face, fault):
    values = frames("PRIVATE_FRAME_VALUE")
    if fault == "too_few": values = values[:14]
    elif fault == "too_many": values = frames("PRIVATE_FRAME_VALUE", 121)
    elif fault == "duplicate": values[5]["timestamp_ms"] = values[4]["timestamp_ms"]
    elif fault == "descending": values.reverse()
    elif fault == "gap": values[5]["timestamp_ms"] = values[4]["timestamp_ms"] + 251
    elif fault == "late_start":
        for item in values: item["timestamp_ms"] += 251
    elif fault == "too_short":
        for index, item in enumerate(values): item["timestamp_ms"] = index * 30
    elif fault == "negative": values[0]["timestamp_ms"] = -1
    elif fault == "over_duration": values[-1]["timestamp_ms"] = 8001
    elif fault == "boolean_time": values[0]["timestamp_ms"] = True
    elif fault == "string_time": values[0]["timestamp_ms"] = "0"
    elif fault == "per_frame_oversize": values[0]["image"] = "S" * 100001
    elif fault == "total_oversize":
        values = [{"image": "S" * 90000, "timestamp_ms": i * 80} for i in range(70)]
    response = face.request("POST", "/liveness/sequence", json={"frames": values, "reference_template_hash": "a" * 64})
    expect(response, 422)
    assert_private(response.text, "PRIVATE_FRAME_VALUE", "S" * 100)


@pytest.mark.parametrize("override", [{"pad_mode": "off"}, {"pad_threshold": 0}, {"liveness_threshold": 0},
    {"liveness_passed": True}, {"face_embedding_hash": "a" * 64}])
def test_client_cannot_override_liveness_policy(face, override):
    expect(face.request("POST", "/liveness/check", json={"challenge_response": "PRIVATE_FRAME_VALUE", **override}), 422)


def test_native_static_sequence_never_becomes_backend_proof(world, face):
    world.enroll_face()
    meeting = world.session(require_motion_check=True, require_face_match=True, require_liveness_check=True)
    issued = expect(world.service.api("POST", "/motion/challenges", world.student, json={"session_id": meeting["id"]}), 201)
    result = expect(world.service.api("POST", f"/motion/challenges/{issued['challenge_id']}/verify", world.student,
                                    json={"frames": frames(sequence_image())}), 200)
    assert result["passed"] is False and result["verification_id"] is None
    expect(world.checkin(meeting, motion_verification_id=issued["challenge_id"]), 409)
    assert not world.service.rows("checkins", session_id=meeting["id"])


@pytest.mark.parametrize("fault", ["expired", "withdrawn_consent", "reenrolled_face"])
def test_challenge_invalidated_by_expiry_or_enrollment_change(world, face, fault):
    world.enroll_face()
    meeting = world.session(require_motion_check=True)
    issued = expect(world.service.api("POST", "/motion/challenges", world.student, json={"session_id": meeting["id"]}), 201)
    if fault == "expired":
        world.service.update("motion_challenges", issued["challenge_id"], expires_at=utc_now().replace(tzinfo=None) - timedelta(seconds=1))
    elif fault == "withdrawn_consent":
        expect(world.service.api("PUT", "/users/me", world.student, json={"camera_consent": False}), 200)
    else:
        # Real public enrollment changes the reference; no fabricated model score.
        world.enroll_face(image=image_b64("biden.jpg"))
    response = world.service.api("POST", f"/motion/challenges/{issued['challenge_id']}/verify", world.student,
                                 json={"frames": frames(sequence_image())})
    assert response.status_code in (400, 409)
    assert not world.service.rows("checkins", session_id=meeting["id"])

