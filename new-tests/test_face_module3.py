"""Additional Module 3 coverage for behavior omitted by the public suite."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = REPOSITORY_ROOT / "module3-face-recognition"
SAMPLE_IMAGES = REPOSITORY_ROOT / "sample_images"

# Import the face service rather than Module 2's identically named ``app``
# package when the tests are launched from the repository root.
sys.path.insert(0, str(MODULE_ROOT))
os.environ.setdefault("TELEMETRY_ENABLED", "false")
os.environ.setdefault("JSON_LOGGING_ENABLED", "false")

from app.config import MAX_IMAGE_BYTES  # noqa: E402
from app.imaging import ImageTooLargeError, decode_base64_image  # noqa: E402
from app.main import app  # noqa: E402
from app.risk import risk_level  # noqa: E402
from app.template import (  # noqa: E402
    build_hyperplanes,
    compare_templates,
    hamming_fraction,
    match_score,
    simhash_hex,
)


HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _image_base64(name: str) -> str:
    return base64.b64encode((SAMPLE_IMAGES / name).read_bytes()).decode("ascii")


def _encode_rgb(image: np.ndarray, image_format: str = "JPEG") -> str:
    with BytesIO() as buffer:
        Image.fromarray(image, mode="RGB").save(buffer, format=image_format, quality=92)
        return base64.b64encode(buffer.getvalue()).decode("ascii")


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def obama_image() -> str:
    return _image_base64("obama.jpg")


@pytest.fixture(scope="module")
def enrolled_hash(client: TestClient, obama_image: str) -> str:
    response = client.post(
        "/face/enroll",
        json={
            "user_id": "module3-edge-tests",
            "image": obama_image,
            "camera_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    value = response.json()["face_template_hash"]
    assert HASH_PATTERN.fullmatch(value)
    return value


def test_same_person_different_photos_and_different_person(
    client: TestClient,
    enrolled_hash: str,
) -> None:
    for image_name in ("obama2.jpg", "obama3.jpg"):
        response = client.post(
            "/face/verify",
            json={
                "image": _image_base64(image_name),
                "reference_template_hash": enrolled_hash,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["match_passed"] is True
        assert response.json()["match_score"] >= 0.70

    different = client.post(
        "/face/verify",
        json={
            "image": _image_base64("biden.jpg"),
            "reference_template_hash": enrolled_hash,
        },
    )
    assert different.status_code == 200, different.text
    assert different.json()["match_passed"] is False
    assert different.json()["match_score"] < 0.70


def test_templates_are_deterministic_monotonic_and_cancelable() -> None:
    embedding = np.linspace(-1.0, 1.0, 128, dtype=np.float64)
    first_planes = build_hyperplanes(3099)
    rotated_planes = build_hyperplanes(3100)

    first = simhash_hex(embedding, hyperplanes=first_planes)
    repeated = simhash_hex(embedding.copy(), hyperplanes=first_planes)
    rotated = simhash_hex(embedding, hyperplanes=rotated_planes)

    assert first == repeated
    assert HASH_PATTERN.fullmatch(first)
    assert rotated != first
    assert hamming_fraction(first, rotated) > 0.30
    assert compare_templates(first, first).match_passed is True
    assert compare_templates(first, rotated).match_passed is False

    fractions = (0.0, 0.05, 0.10, 0.158203, 0.25, 0.50, 1.0)
    scores = [match_score(value) for value in fractions]
    assert scores == sorted(scores, reverse=True)
    assert match_score(0.158203) == pytest.approx(0.70)


def test_liveness_hash_matches_enrollment_pipeline(
    client: TestClient,
    obama_image: str,
    enrolled_hash: str,
) -> None:
    liveness = client.post(
        "/liveness/check",
        json={"challenge_response": obama_image, "challenge_type": "passive"},
    )
    assert liveness.status_code == 200, liveness.text
    body = liveness.json()
    assert body["liveness_passed"] is True
    assert body["liveness_score"] >= 0.60
    assert body["face_embedding_hash"] == enrolled_hash
    assert body["challenge_type"] == "passive"
    assert body["details"]["presentation_integrity_score"] > 0.0


def test_active_liveness_challenge_requires_evidence(
    client: TestClient,
    obama_image: str,
) -> None:
    passive = client.post(
        "/liveness/check",
        json={"challenge_response": obama_image, "challenge_type": "passive"},
    )
    head_turn = client.post(
        "/liveness/check",
        json={"challenge_response": obama_image, "challenge_type": "head_turn"},
    )
    assert passive.status_code == 200, passive.text
    assert head_turn.status_code == 200, head_turn.text
    assert head_turn.json()["challenge_type"] == "head_turn"
    assert head_turn.json()["details"]["single_image_challenge_proxy"] is True
    assert head_turn.json()["liveness_score"] < passive.json()["liveness_score"]
    assert head_turn.json()["details"]["challenge_integrity_score"] < 1.0


@pytest.mark.parametrize("kind", ["screen", "print"])
def test_periodic_presentation_attacks_are_rejected(
    client: TestClient,
    kind: str,
) -> None:
    image = decode_base64_image(_image_base64("obama.jpg"))
    height, width = image.shape[:2]
    yy, xx = np.indices((height, width))

    if kind == "screen":
        small = cv2.resize(
            image,
            (max(64, width // 3), max(64, height // 3)),
            interpolation=cv2.INTER_AREA,
        )
        candidate = cv2.resize(
            small,
            (width, height),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32)
        grid = 1.0 + 0.14 * np.sin(2 * np.pi * xx / 5.0)
        grid += 0.10 * np.sin(2 * np.pi * yy / 7.0)
        candidate *= grid[..., None]
        glare = np.exp(
            -(
                ((xx - width * 0.68) / (width * 0.13)) ** 2
                + ((yy - height * 0.28) / (height * 0.18)) ** 2
            )
        )
        candidate = candidate * (1.0 - 0.30 * glare[..., None])
        candidate += 255.0 * 0.30 * glare[..., None]
    else:
        candidate = cv2.GaussianBlur(image, (5, 5), 1.2).astype(np.float32)
        candidate = candidate * np.array([0.90, 0.84, 0.78], dtype=np.float32)
        candidate += 18.0
        halftone = 1.0 + 0.09 * np.sin(2 * np.pi * (xx + yy) / 8.0)
        candidate *= halftone[..., None]

    encoded = _encode_rgb(np.clip(candidate, 0, 255).astype(np.uint8))
    response = client.post(
        "/liveness/check",
        json={"challenge_response": encoded, "challenge_type": "passive"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["liveness_passed"] is False
    assert body["liveness_score"] < body["liveness_threshold"]
    assert (
        body["details"]["texture_signals"]["periodic_artifact_penalty"]
        >= 0.90
    )


def test_uniform_image_fails_liveness(client: TestClient) -> None:
    uniform = Image.new("RGB", (256, 256), (255, 220, 185))
    with BytesIO() as buffer:
        uniform.save(buffer, format="PNG")
        payload = base64.b64encode(buffer.getvalue()).decode("ascii")

    response = client.post(
        "/liveness/check",
        json={"challenge_response": payload, "challenge_type": "passive"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["liveness_passed"] is False
    assert response.json()["liveness_score"] < 0.50


def test_legacy_aliases_and_reference_validation(
    client: TestClient,
    obama_image: str,
    enrolled_hash: str,
) -> None:
    legacy = client.post(
        "/face/match",
        json={"image": obama_image, "reference_hash": enrolled_hash},
    )
    assert legacy.status_code == 200, legacy.text
    body = legacy.json()
    assert body["match_passed"] is True
    assert body["face_embedding_hash"] == body["current_template_hash"]

    current = client.post(
        "/face/match",
        json={
            "image": obama_image,
            "reference_template_hash": enrolled_hash,
        },
    )
    assert current.status_code == 200, current.text
    assert current.json()["match_passed"] is True

    invalid = client.post(
        "/face/verify",
        json={"image": obama_image, "reference_template_hash": "A" * 64},
    )
    assert invalid.status_code == 400
    assert obama_image[:100] not in invalid.text


def test_malformed_images_and_request_size_are_rejected_privately(
    client: TestClient,
    enrolled_hash: str,
    obama_image: str,
) -> None:
    for malformed in ("not-base64", "AAAA", base64.b64encode(b"not an image").decode()):
        response = client.post(
            "/face/verify",
            json={
                "image": malformed,
                "reference_template_hash": enrolled_hash,
            },
        )
        assert response.status_code == 400
        assert "traceback" not in response.text.lower()

    missing_field = client.post(
        "/face/enroll",
        json={"image": obama_image, "camera_consent": True},
    )
    assert missing_field.status_code == 422
    assert obama_image[:100] not in missing_field.text

    declared_oversize = client.post(
        "/face/verify",
        content=json.dumps(
            {"image": "AAAA", "reference_template_hash": enrolled_hash}
        ),
        headers={
            "content-type": "application/json",
            "content-length": str(
                4 * ((MAX_IMAGE_BYTES + 2) // 3) + 128 * 1024 + 1
            ),
        },
    )
    assert declared_oversize.status_code == 400

    with pytest.raises(ImageTooLargeError):
        decode_base64_image(
            base64.b64encode(b"123456789").decode("ascii"),
            max_bytes=8,
        )


def test_data_uri_is_supported(client: TestClient, obama_image: str) -> None:
    response = client.post(
        "/face/enroll",
        json={
            "user_id": "data-uri-test",
            "image": f"data:image/jpeg;base64,{obama_image}",
            "camera_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    assert HASH_PATTERN.fullmatch(response.json()["face_template_hash"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "LOW"),
        (0.299999, "LOW"),
        (0.30, "MEDIUM"),
        (0.499999, "MEDIUM"),
        (0.50, "HIGH"),
        (0.699999, "HIGH"),
        (0.70, "CRITICAL"),
        (1.0, "CRITICAL"),
    ],
)
def test_risk_level_boundaries(value: float, expected: str) -> None:
    assert risk_level(value) == expected


def test_risk_breakdown_sums_to_total(client: TestClient) -> None:
    response = client.post(
        "/risk/assess",
        json={
            "liveness_score": 0.72,
            "face_match_score": 0.64,
            "ip_address": "10.0.0.1",
            "user_agent": "vpn-client",
            "geolocation": {
                "latitude": 1.3483,
                "longitude": 103.6831,
                "accuracy": 800.0,
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert sum(body["signal_breakdown"].values()) == pytest.approx(
        body["risk_score"],
        abs=1e-6,
    )


def test_metrics_are_exposed_without_biometric_values(
    client: TestClient,
    enrolled_hash: str,
) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/plain; version=0.0.4"
    )
    assert "http_request_duration_seconds" in response.text
    assert enrolled_hash not in response.text


def test_device_attestation_verifies_the_exact_challenge(client: TestClient) -> None:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    challenge = "module3-one-time-challenge"
    signature = base64.b64encode(private_key.sign(challenge.encode("utf-8"))).decode(
        "ascii"
    )
    request = {
        "device_public_key": public_pem,
        "device_signature": signature,
        "challenge": challenge,
        "device_info": {"platform": "test", "os_version": "1"},
    }

    accepted = client.post("/device/attest", json=request)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["attestation_passed"] is True
    assert accepted.json()["device_trusted"] is True
    assert HASH_PATTERN.fullmatch(accepted.json()["device_fingerprint"])

    rejected = client.post(
        "/device/attest",
        json={**request, "challenge": f"{challenge}-tampered"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["attestation_passed"] is False
    assert rejected.json()["device_trusted"] is False


def test_parallel_verification_is_consistent(
    client: TestClient,
    obama_image: str,
    enrolled_hash: str,
) -> None:
    def verify_once(_index: int) -> tuple[int, bool, str]:
        response = client.post(
            "/face/verify",
            json={
                "image": obama_image,
                "reference_template_hash": enrolled_hash,
            },
        )
        body = response.json()
        return response.status_code, body["match_passed"], body["current_template_hash"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(verify_once, range(20)))

    assert results == [(200, True, enrolled_hash)] * 20
