"""Native HTTP identity/quality checks and risk invariants; no mocked models."""
import base64
import io
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor

import pytest
from harness import expect, image_b64, png_b64, assert_private, bounded_score

pytestmark = [pytest.mark.specification, pytest.mark.native]


@pytest.fixture(scope="module")
def reference(face):
    result = expect(face.request("POST", "/face/enroll", json={"user_id": "hidden-native-reference",
                    "image": image_b64(), "camera_consent": True}), 201)
    assert result["enrollment_successful"] is True
    assert re.fullmatch(r"[0-9a-f]{64}", result["face_template_hash"])
    bounded_score(result["quality_score"])
    return result["face_template_hash"]


@pytest.mark.parametrize("image,expected", [("obama.jpg", True), ("obama2.jpg", True),
    ("obama3.jpg", True), ("biden.jpg", False)])
def test_identity_across_sample_photographs(face, reference, image, expected):
    encoded = image_b64(image)
    result = expect(face.request("POST", "/face/verify", json={"image": encoded, "reference_template_hash": reference}), 200)
    assert result["face_detected"] is True
    assert result["match_passed"] is expected
    bounded_score(result["match_score"])
    assert result["match_passed"] == (result["match_score"] >= result["match_threshold"])
    assert_private(json.dumps(result), encoded, encoded[80:240])


@pytest.mark.parametrize("consent", [False, None, "true", 1])
def test_enrollment_consent_is_explicit_boolean(face, consent):
    response = face.request("POST", "/face/enroll", json={"user_id": "hidden-consent", "image": image_b64(), "camera_consent": consent})
    assert response.status_code == (400 if consent is False else 422)


@pytest.mark.parametrize("encoded", ["%%%not-base64%%%", "", "eA==", "data:text/html;base64,PHNjcmlwdD4=", "🧬"])
def test_malformed_images_fail_privately(face, encoded):
    for endpoint, payload in (("/face/enroll", {"user_id": "hidden-invalid", "camera_consent": True, "image": encoded}),
                               ("/liveness/check", {"challenge_response": encoded})):
        response = face.request("POST", endpoint, json=payload)
        assert response.status_code in (400, 422)
        assert "traceback" not in response.text.lower()
        if encoded:
            assert_private(response.text, encoded)


@pytest.mark.parametrize("value", ["a" * 63, "a" * 65, "g" * 64, "A" * 64, "", "../../etc/passwd"])
def test_reference_template_validation(face, value):
    response = face.request("POST", "/face/verify", json={"image": image_b64(), "reference_template_hash": value})
    expect(response, 400)


def test_no_face_cannot_enroll_match_or_pass_liveness(face, reference):
    image = png_b64()
    expect(face.request("POST", "/face/enroll", json={"user_id": "hidden-landscape", "image": image, "camera_consent": True}), 400)
    result = expect(face.request("POST", "/face/verify", json={"image": image, "reference_template_hash": reference}), 200)
    assert result["match_passed"] is False and result["face_detected"] is False
    assert result["current_template_hash"] == ""
    live = expect(face.request("POST", "/liveness/check", json={"challenge_response": image}), 200)
    assert live["liveness_passed"] is False


def test_multiple_faces_cannot_be_enrolled_as_one_identity(face):
    from PIL import Image
    from harness import ROOT
    with Image.open(ROOT / "sample_images/obama.jpg") as source:
        source.thumbnail((350, 450))
        image = Image.new("RGB", (source.width * 2, source.height), "white")
        image.paste(source, (0, 0)); image.paste(source, (source.width, 0))
    buffer = io.BytesIO(); image.save(buffer, format="JPEG", quality=90)
    response = face.request("POST", "/face/enroll", json={"user_id": "hidden-multiple",
        "image": base64.b64encode(buffer.getvalue()).decode(), "camera_consent": True})
    expect(response, 400)


def test_oversized_json_body_is_rejected_before_inference(face):
    # The application byte cap is 12 MiB by default; exceed it with a bounded
    # payload. This is an actual body, not an inconsistent Content-Length.
    response = face.request("POST", "/face/enroll", json={"user_id": "hidden-oversize", "camera_consent": True,
                            "image": "A" * (12 * 1024 * 1024 + 1)})
    assert response.status_code in (400, 413)
    assert len(response.content) < 8192


def test_parallel_identity_comparisons_do_not_mix_results(face, reference):
    cases = [("same_identity", image_b64("obama.jpg"), True), ("different_identity", image_b64("biden.jpg"), False)] * 4
    def verify(case):
        name, encoded, expected = case
        result = expect(face.request("POST", "/face/verify", json={"image": encoded, "reference_template_hash": reference}), 200)
        return name, result["match_passed"], expected, result["match_score"], result["face_detected"]
    baseline = [verify(case) for case in cases[:2]]
    assert all(actual is expected for _, actual, expected, _, _ in baseline), "Serial identity setup failed"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(verify, cases))
    failures = [(name, actual, expected, score, detected) for name, actual, expected, score, detected in results if actual is not expected]
    assert not failures, f"Concurrent outcomes (identity,actual,expected,score,face_detected) differ from serial controls: {failures}"


@pytest.mark.parametrize("value", [True, "0.9", -0.01, 1.01, float("nan"), float("inf")])
def test_risk_scores_reject_invalid_json_numbers(face, value):
    response = face.request("POST", "/risk/assess", content=json.dumps({"liveness_score": value}),
                            headers={"Content-Type": "application/json"})
    expect(response, 422)


@pytest.mark.parametrize("score", [0, .2, .4, .6, .8, 1])
def test_risk_breakdown_is_finite_and_matches_threshold_semantics(face, score):
    result = expect(face.request("POST", "/risk/assess", json={"liveness_score": score, "face_match_score": score}), 200)
    bounded_score(result["risk_score"])
    for value in result["signal_breakdown"].values():
        bounded_score(value)
    assert sum(result["signal_breakdown"].values()) == pytest.approx(result["risk_score"])
    risk = result["risk_score"]
    level = "LOW" if risk < .3 else "MEDIUM" if risk < .5 else "HIGH" if risk < .7 else "CRITICAL"
    assert result["risk_level"] == level
    assert result["pass_threshold"] == (risk < result["risk_threshold"])


def test_worsening_identity_and_liveness_cannot_lower_risk(face):
    risks = [expect(face.request("POST", "/risk/assess", json={"liveness_score": score, "face_match_score": score}), 200)["risk_score"]
             for score in (1, .8, .6, .4, .2, 0)]
    assert risks == sorted(risks)


def test_obvious_proxy_user_agent_cannot_reduce_network_risk(face):
    payload = {"liveness_score": .95, "face_match_score": .95, "ip_address": "8.8.8.8"}
    clean = expect(face.request("POST", "/risk/assess", json={**payload, "user_agent": "Mozilla/5.0"}), 200)
    proxy = expect(face.request("POST", "/risk/assess", json={**payload, "user_agent": "Tor proxy VPN"}), 200)
    assert proxy["signal_breakdown"]["network"] > clean["signal_breakdown"]["network"]
    assert proxy["risk_score"] > clean["risk_score"]


def test_metrics_do_not_expose_biometrics(face, reference):
    response = face.request("GET", "/metrics")
    assert response.status_code == 200
    assert_private(response.text, reference, image_b64()[80:240])
    assert "http_request_duration_seconds" in response.text


@pytest.mark.parametrize("fault", [None, "challenge", "signature", "key", "invalid_pem"])
def test_standalone_attestation_checks_exact_signed_bytes(face, fault):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    private = ed25519.Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    challenge = "hidden-assessment-signed-challenge"
    payload = {"device_public_key": public, "device_signature": base64.b64encode(private.sign(challenge.encode())).decode(),
               "challenge": challenge, "device_info": {"platform": "web"}}
    if fault == "challenge": payload["challenge"] += "-tampered"
    elif fault == "signature": payload["device_signature"] = base64.b64encode(b"x" * 64).decode()
    elif fault == "key":
        payload["device_public_key"] = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    elif fault == "invalid_pem": payload["device_public_key"] = "not-a-public-key"
    result = expect(face.request("POST", "/device/attest", json=payload), 200)
    assert result["attestation_passed"] is (fault is None)
    assert result["device_trusted"] is (fault is None)
    bounded_score(result["attestation_score"])
    # Freshness belongs to M2's nonce tests, not this standalone signature API.

