"""Held-out physical captures. No synthetic fallback and no label inference."""
import pytest
from corpus import load_cases, encoded_file, sequence_payload
from harness import expect, bounded_score

pytestmark = [pytest.mark.physical, pytest.mark.native, pytest.mark.specification]


def pytest_generate_tests(metafunc):
    if "physical_case" not in metafunc.fixturenames:
        return
    path = metafunc.config.getoption("--attack-manifest")
    if not path:
        if metafunc.config.getoption("--require-physical"):
            raise pytest.UsageError("--require-physical requires --attack-manifest=/path/to/captures.json")
        metafunc.parametrize("physical_case", [pytest.param(None, marks=pytest.mark.skip(
            reason="Physical attack/genuine corpus not supplied; see hidden-tests/README.md"))])
        return
    try:
        cases = load_cases(path)
        if metafunc.config.getoption("--require-physical"):
            kinds = {case["kind"] for case in cases}
            required = {"genuine", "impostor", "print", "screen_photo", "screen_video", "genuine_sequence"}
            if not required <= kinds:
                raise ValueError("Required physical coverage missing: " + ", ".join(sorted(required-kinds)))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise pytest.UsageError("Invalid physical corpus: " + str(exc)) from exc
    metafunc.parametrize("physical_case", cases, ids=[case["id"] for case in cases])


def test_real_capture_outcome(face, physical_case, record_property):
    case = physical_case
    enrollment = expect(face.request("POST", "/face/enroll", json={"user_id": "hidden-physical-corpus",
        "image": encoded_file(case["enrollment"]), "camera_consent": True}), 201)
    reference = enrollment["face_template_hash"]
    record_property("physical_kind", case["kind"])
    if "frames" in case:
        result = expect(face.request("POST", "/liveness/sequence", json=sequence_payload(case, reference)), 200)
        expected = case["kind"] == "genuine_sequence"
        assert result["passed"] is expected, "Physical sequence outcome disagrees with confirmed label"
        if expected:
            assert result["turn_passed"] is True and result["completed_steps"] == 2
    elif case["kind"] == "impostor":
        result = expect(face.request("POST", "/face/verify", json={"image": encoded_file(case["image"]),
                                     "reference_template_hash": reference}), 200)
        assert result["match_passed"] is False, "A confirmed different person matched the enrolled identity"
    else:
        image = encoded_file(case["image"])
        result = expect(face.request("POST", "/liveness/check", json={"challenge_response": image}), 200)
        bounded_score(result["liveness_score"])
        expected = case["kind"] == "genuine"
        assert result["liveness_passed"] is expected, "Physical liveness outcome disagrees with confirmed label"
        if expected:
            match = expect(face.request("POST", "/face/verify", json={"image": image, "reference_template_hash": reference}), 200)
            assert match["match_passed"] is True

