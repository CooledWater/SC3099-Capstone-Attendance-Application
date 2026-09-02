"""Runtime configuration for the face-recognition service.

The service deliberately reads all deployable values from the environment and
fails fast when a value is malformed.  Keeping this module dependency-light is
useful for calibration scripts, which import the template code without starting
FastAPI.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_SIMHASH_SEED = 3099
DEFAULT_MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_IMAGE_DIM = 1024


class Settings(BaseModel):
    """Validated, immutable settings used throughout Module 3."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    service_name: str = "saiv-face-recognition"
    service_version: str = "1.0.0"

    face_match_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    # Midpoint measured by scripts/calibrate.py on the supplied Obama/Biden
    # corpus (max same-person 0.113281, min different-person 0.203125).
    face_match_hamming_fraction: float = Field(
        default=0.158203,
        gt=0.0,
        lt=0.5,
    )
    face_detection_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    face_quality_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    liveness_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    risk_threshold: float = Field(default=0.50, ge=0.0, le=1.0)

    simhash_seed: int = Field(
        default=DEFAULT_SIMHASH_SEED,
        ge=0,
        le=(2**128) - 1,
    )
    max_image_bytes: int = Field(
        default=DEFAULT_MAX_IMAGE_BYTES,
        ge=1,
        le=64 * 1024 * 1024,
    )
    max_image_dim: int = Field(default=DEFAULT_MAX_IMAGE_DIM, ge=1, le=8192)

    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    cors_allow_credentials: bool = False

    telemetry_enabled: bool = True
    metrics_enabled: bool = True
    json_logging_enabled: bool = True
    otel_exporter_otlp_endpoint: str | None = None
    max_log_field_chars: int = Field(default=256, ge=64, le=4096)

    @field_validator(
        "face_match_threshold",
        "face_match_hamming_fraction",
        "face_detection_threshold",
        "face_quality_threshold",
        "liveness_threshold",
        "risk_threshold",
    )
    @classmethod
    def _finite_threshold(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("thresholds must be finite")
        return value

    @field_validator("service_name", "service_version")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("otel_exporter_otlp_endpoint")
    @classmethod
    def _valid_optional_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute HTTP(S) URL")
        return value


def _get_env(
    environ: Mapping[str, str],
    name: str,
    default: Any,
    *fallback_names: str,
) -> Any:
    for candidate in (name, *fallback_names):
        if candidate in environ:
            return environ[candidate]
    return default


def _parse_float(environ: Mapping[str, str], name: str, default: float) -> float:
    raw = _get_env(environ, name, default)
    if isinstance(raw, float):
        return raw
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be a number") from exc


def _parse_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = _get_env(environ, name, default)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    try:
        return int(str(raw).strip(), 10)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} must be a base-10 integer") from exc


def _parse_bool(
    environ: Mapping[str, str],
    name: str,
    default: bool,
    *fallback_names: str,
) -> bool:
    raw = _get_env(environ, name, default, *fallback_names)
    if isinstance(raw, bool):
        return raw
    normalized = str(raw).strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean (true/false)")


def _parse_cors_origins(environ: Mapping[str, str]) -> tuple[str, ...]:
    raw = _get_env(
        environ,
        "FACE_CORS_ORIGINS",
        "http://localhost:3000",
        "CORS_ORIGINS",
        "ALLOWED_ORIGINS",
    )
    if isinstance(raw, (tuple, list)):
        values = list(raw)
    else:
        text = str(raw).strip()
        if not text:
            return ()
        if text.startswith("["):
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuntimeError("FACE_CORS_ORIGINS contains invalid JSON") from exc
            if not isinstance(decoded, list):
                raise RuntimeError("FACE_CORS_ORIGINS JSON must be an array")
            values = decoded
        else:
            values = text.split(",")

    origins: list[str] = []
    for raw_origin in values:
        if not isinstance(raw_origin, str):
            raise RuntimeError("FACE_CORS_ORIGINS entries must be strings")
        origin = raw_origin.strip().rstrip("/")
        if not origin:
            continue
        if origin == "*":
            raise RuntimeError("FACE_CORS_ORIGINS must not contain a wildcard")
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise RuntimeError(
                f"FACE_CORS_ORIGINS contains an invalid origin: {origin!r}"
            )
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read and validate settings from *environ* (or ``os.environ``).

    Supplying a mapping makes configuration behavior straightforward to test
    without mutating process-global environment variables.
    """

    env = os.environ if environ is None else environ
    try:
        return Settings(
            service_name=str(_get_env(env, "FACE_SERVICE_NAME", "saiv-face-recognition")),
            service_version=str(_get_env(env, "FACE_SERVICE_VERSION", "1.0.0")),
            face_match_threshold=_parse_float(env, "FACE_MATCH_THRESHOLD", 0.70),
            face_match_hamming_fraction=_parse_float(
                env, "FACE_MATCH_HAMMING_FRACTION", 0.158203
            ),
            face_detection_threshold=_parse_float(
                env, "FACE_DETECTION_THRESHOLD", 0.70
            ),
            face_quality_threshold=_parse_float(env, "FACE_QUALITY_THRESHOLD", 0.50),
            liveness_threshold=_parse_float(env, "LIVENESS_THRESHOLD", 0.60),
            risk_threshold=_parse_float(env, "RISK_THRESHOLD", 0.50),
            simhash_seed=_parse_int(env, "SIMHASH_SEED", DEFAULT_SIMHASH_SEED),
            max_image_bytes=_parse_int(
                env, "MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES
            ),
            max_image_dim=_parse_int(env, "MAX_IMAGE_DIM", DEFAULT_MAX_IMAGE_DIM),
            cors_origins=_parse_cors_origins(env),
            cors_allow_credentials=_parse_bool(
                env, "CORS_ALLOW_CREDENTIALS", False
            ),
            telemetry_enabled=_parse_bool(
                env, "TELEMETRY_ENABLED", True, "OTEL_ENABLED"
            ),
            metrics_enabled=_parse_bool(env, "METRICS_ENABLED", True),
            json_logging_enabled=_parse_bool(env, "JSON_LOGGING_ENABLED", True),
            otel_exporter_otlp_endpoint=_get_env(
                env, "OTEL_EXPORTER_OTLP_ENDPOINT", None
            ),
            max_log_field_chars=_parse_int(env, "MAX_LOG_FIELD_CHARS", 256),
        )
    except RuntimeError:
        raise
    except ValueError as exc:
        raise RuntimeError(f"Invalid face-service configuration: {exc}") from exc


settings = load_settings()

# Module-level constants keep call sites concise and preserve the uppercase
# environment-variable vocabulary used by deployment manifests.
SERVICE_NAME = settings.service_name
SERVICE_VERSION = settings.service_version
FACE_MATCH_THRESHOLD = settings.face_match_threshold
FACE_MATCH_HAMMING_FRACTION = settings.face_match_hamming_fraction
FACE_DETECTION_THRESHOLD = settings.face_detection_threshold
FACE_QUALITY_THRESHOLD = settings.face_quality_threshold
LIVENESS_THRESHOLD = settings.liveness_threshold
RISK_THRESHOLD = settings.risk_threshold
SIMHASH_SEED = settings.simhash_seed
MAX_IMAGE_BYTES = settings.max_image_bytes
MAX_IMAGE_DIM = settings.max_image_dim
CORS_ORIGINS = settings.cors_origins
CORS_ALLOW_CREDENTIALS = settings.cors_allow_credentials
TELEMETRY_ENABLED = settings.telemetry_enabled
METRICS_ENABLED = settings.metrics_enabled
JSON_LOGGING_ENABLED = settings.json_logging_enabled
OTEL_EXPORTER_OTLP_ENDPOINT = settings.otel_exporter_otlp_endpoint
MAX_LOG_FIELD_CHARS = settings.max_log_field_chars

# Fixed biometric dimensions are protocol invariants, not deployable settings.
SIMHASH_BITS = 256
FACE_EMBEDDING_DIM = 128


__all__ = [
    "Settings",
    "load_settings",
    "settings",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "FACE_MATCH_THRESHOLD",
    "FACE_MATCH_HAMMING_FRACTION",
    "FACE_DETECTION_THRESHOLD",
    "FACE_QUALITY_THRESHOLD",
    "LIVENESS_THRESHOLD",
    "RISK_THRESHOLD",
    "SIMHASH_SEED",
    "MAX_IMAGE_BYTES",
    "MAX_IMAGE_DIM",
    "CORS_ORIGINS",
    "CORS_ALLOW_CREDENTIALS",
    "TELEMETRY_ENABLED",
    "METRICS_ENABLED",
    "JSON_LOGGING_ENABLED",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "MAX_LOG_FIELD_CHARS",
    "SIMHASH_BITS",
    "FACE_EMBEDDING_DIM",
]
