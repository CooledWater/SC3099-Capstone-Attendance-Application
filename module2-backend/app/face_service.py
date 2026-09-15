"""Client for Module 3 (the face-recognition & risk service).

Every HTTP call the backend makes to the face service goes through this module
so that ``main.py`` never embeds raw ``httpx`` requests. The service base URL is
read from ``FACE_SERVICE_URL`` - ``docker-compose.yml`` sets it to
``http://face-recognition:8001`` and the local default is
``http://localhost:8001`` (matching docs/INTEGRATION-GUIDE.md).

Two error policies, deliberately different:

* **Check-in path** (:meth:`FaceServiceClient.check_liveness`,
  :meth:`~FaceServiceClient.verify_face`, :meth:`~FaceServiceClient.assess_risk`)
  **fails open**: any timeout, transport error, non-2xx response or malformed
  body yields ``None``. The caller then falls back to the geofence-only
  decision. A successful biometric result is **never fabricated** when the
  service cannot be reached - the corresponding check-in columns stay ``NULL``.

* **Enrollment path** (:meth:`~FaceServiceClient.enroll_face`) is strict: a 400
  from the service maps to :class:`FaceServiceValidationError` (surface as HTTP
  400) and any timeout/transport/5xx maps to :class:`FaceServiceUnavailableError`
  (surface as HTTP 503), matching docs/API-SPECIFICATION.md.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("saiv.face_service")

FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://localhost:8001").rstrip("/")

# docs/INTEGRATION-GUIDE.md pins Backend -> Face at 5s and the whole check-in
# must finish in under 2s, so check-in-path calls use the short timeout.
# Enrollment is a one-off interactive action and is allowed the 10s the API
# spec's own examples use.
_CHECKIN_TIMEOUT = float(os.getenv("FACE_SERVICE_TIMEOUT", "5.0"))
_ENROLL_TIMEOUT = float(os.getenv("FACE_SERVICE_ENROLL_TIMEOUT", "10.0"))

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class FaceServiceError(Exception):
    """Base class for face-service call failures (enrollment path)."""


class FaceServiceValidationError(FaceServiceError):
    """The face service rejected the input (HTTP 400)."""


class FaceServiceUnavailableError(FaceServiceError):
    """The face service could not be reached or failed (HTTP 503)."""


@dataclass
class LivenessResult:
    passed: bool | None
    score: float | None
    challenge_type: str | None
    face_embedding_hash: str | None


@dataclass
class FaceMatchResult:
    passed: bool | None
    score: float | None
    face_embedding_hash: str | None


@dataclass
class RiskResult:
    risk_score: float
    risk_level: str
    signal_breakdown: dict[str, float]
    recommendations: list[str]


@dataclass
class EnrollResult:
    face_template_hash: str
    quality_score: float


def _clean_hash(value: Any) -> str | None:
    """Return ``value`` only if it is a 64-char lowercase hex template hash."""
    if isinstance(value, str) and _HEX64_RE.match(value):
        return value
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_detail(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
    return None


class FaceServiceClient:
    """Thin, reuse-one-connection-pool wrapper around the face service."""

    def __init__(self, base_url: str = FACE_SERVICE_URL) -> None:
        self._base_url = base_url
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()

    def _get_client(self) -> httpx.Client:
        # httpx.Client is safe to share across threads; build it lazily so
        # importing this module never opens a socket (keeps tests/CI happy).
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = httpx.Client(base_url=self._base_url)
        return self._client

    def _post(self, path: str, payload: dict, timeout: float) -> httpx.Response:
        return self._get_client().post(path, json=payload, timeout=timeout)

    # ------------------------------------------------------------------
    # Check-in path - fail open, never fabricate a pass
    # ------------------------------------------------------------------
    def check_liveness(
        self, image_b64: str, challenge_type: str = "passive"
    ) -> LivenessResult | None:
        """POST /liveness/check. Returns ``None`` if the service is unusable."""
        if not image_b64:
            return None
        challenge_type = challenge_type or "passive"
        try:
            response = self._post(
                "/liveness/check",
                {"challenge_response": image_b64, "challenge_type": challenge_type},
                _CHECKIN_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            logger.warning("liveness check transport error: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            logger.warning("liveness check returned HTTP %s", response.status_code)
            return None
        try:
            body = response.json()
        except ValueError:
            logger.warning("liveness check returned a non-JSON body")
            return None

        passed = body.get("liveness_passed")
        score = _as_float(body.get("liveness_score"))
        if not isinstance(passed, bool) or score is None:
            return None
        returned_type = body.get("challenge_type")
        return LivenessResult(
            passed=passed,
            score=score,
            challenge_type=returned_type if isinstance(returned_type, str) else challenge_type,
            face_embedding_hash=_clean_hash(body.get("face_embedding_hash")),
        )

    def verify_face(
        self, image_b64: str, reference_hash: str
    ) -> FaceMatchResult | None:
        """POST /face/verify. Returns ``None`` if the service is unusable."""
        if not image_b64 or not reference_hash:
            return None
        try:
            response = self._post(
                "/face/verify",
                {"image": image_b64, "reference_template_hash": reference_hash},
                _CHECKIN_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            logger.warning("face verify transport error: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            logger.warning("face verify returned HTTP %s", response.status_code)
            return None
        try:
            body = response.json()
        except ValueError:
            logger.warning("face verify returned a non-JSON body")
            return None

        passed = body.get("match_passed")
        score = _as_float(body.get("match_score"))
        if not isinstance(passed, bool) or score is None:
            return None
        return FaceMatchResult(
            passed=passed,
            score=score,
            face_embedding_hash=_clean_hash(body.get("current_template_hash")),
        )

    def assess_risk(self, signals: dict) -> RiskResult | None:
        """POST /risk/assess. Returns ``None`` if the service is unusable."""
        try:
            response = self._post("/risk/assess", signals, _CHECKIN_TIMEOUT)
        except httpx.HTTPError as exc:
            logger.warning("risk assess transport error: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            logger.warning("risk assess returned HTTP %s", response.status_code)
            return None
        try:
            body = response.json()
        except ValueError:
            logger.warning("risk assess returned a non-JSON body")
            return None

        risk_score = _as_float(body.get("risk_score"))
        if risk_score is None:
            return None
        raw_breakdown = body.get("signal_breakdown")
        breakdown: dict[str, float] = {}
        if isinstance(raw_breakdown, dict):
            for name, value in raw_breakdown.items():
                as_float = _as_float(value)
                if as_float is not None:
                    breakdown[str(name)] = as_float
        raw_recs = body.get("recommendations")
        recommendations = [str(item) for item in raw_recs] if isinstance(raw_recs, list) else []
        level = body.get("risk_level")
        return RiskResult(
            risk_score=max(0.0, min(1.0, risk_score)),
            risk_level=level if isinstance(level, str) else "",
            signal_breakdown=breakdown,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Enrollment path - strict, surfaces 400 / 503
    # ------------------------------------------------------------------
    def enroll_face(
        self, user_id: str, image_b64: str, camera_consent: bool
    ) -> EnrollResult:
        """POST /face/enroll. Raises on any failure."""
        try:
            response = self._post(
                "/face/enroll",
                {
                    "user_id": user_id,
                    "image": image_b64,
                    "camera_consent": bool(camera_consent),
                },
                _ENROLL_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise FaceServiceUnavailableError(
                f"face service transport error: {type(exc).__name__}"
            ) from exc

        if response.status_code == 400:
            raise FaceServiceValidationError(
                _safe_detail(response) or "Face image was rejected by the face service"
            )
        if response.status_code not in (200, 201):
            raise FaceServiceUnavailableError(
                f"face service returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise FaceServiceUnavailableError(
                "face service returned a non-JSON body"
            ) from exc

        template_hash = _clean_hash(body.get("face_template_hash"))
        if not body.get("enrollment_successful") or template_hash is None:
            raise FaceServiceValidationError("Face enrollment did not succeed")
        return EnrollResult(
            face_template_hash=template_hash,
            quality_score=_as_float(body.get("quality_score")) or 0.0,
        )


# Module-level singleton reused across requests (one connection pool).
face_service = FaceServiceClient()
