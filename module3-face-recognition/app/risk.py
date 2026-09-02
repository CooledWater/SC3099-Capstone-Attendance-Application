"""Deterministic, privacy-safe multi-signal risk scoring.

All values in this module are *risk* values: ``0.0`` is safest and ``1.0``
is riskiest.  Signal weights and cut-offs are defined by the public API and
``docs/SECURITY-REQUIREMENTS.md``.  No raw signal value is logged or retained.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping


SIGNAL_WEIGHTS: dict[str, float] = {
    "liveness": 0.25,
    "face_match": 0.25,
    "device": 0.20,
    "network": 0.15,
    "geolocation": 0.15,
}

NEUTRAL_RISK = 0.5
RECOMMENDATION_RISK_CUTOFF = 0.4

LOW_LIVENESS_RECOMMENDATION = "Improve lighting and face visibility"
LOW_FACE_MATCH_RECOMMENDATION = "Re-enroll face or improve image quality"
DEVICE_RECOMMENDATION = "Provide valid device attestation"
VPN_RECOMMENDATION = "Disable VPN for check-in"
GEOLOCATION_RECOMMENDATION = "Enable precise location services"

_VPN_PATTERN = re.compile(
    r"(?:\b(?:vpn|proxy|tor|anonymi[sz]er|tunnel)\b|torbrowser|openvpn|wireguard)",
    re.IGNORECASE,
)
_BOT_PATTERN = re.compile(
    r"(?:\b(?:bot|crawler|spider|scraper)\b|headless(?:chrome)?|phantomjs|selenium|playwright)",
    re.IGNORECASE,
)
_PEM_PUBLIC_KEY_PATTERN = re.compile(
    r"\A\s*-----BEGIN (?:RSA |EC )?PUBLIC KEY-----\s+.+?\s+"
    r"-----END (?:RSA |EC )?PUBLIC KEY-----\s*\Z",
    re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Final risk decision and weighted, explainable contributions."""

    risk_score: float
    risk_level: str
    pass_threshold: bool
    risk_threshold: float
    signal_breakdown: dict[str, float]
    recommendations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def score_confidence_signal(value: Any) -> tuple[float, bool]:
    """Invert a confidence score; return ``(risk, signal_was_present)``."""

    score = _safe_float(value)
    if score is None:
        return NEUTRAL_RISK, False
    return 1.0 - _clamp(score), True


def _decode_signature(signature: str) -> bytes | None:
    """Decode a hex/base64 signature solely to validate its wire format."""

    candidate = signature.strip()
    if not candidate or len(candidate) > 32_768:
        return None

    if len(candidate) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", candidate):
        try:
            decoded = bytes.fromhex(candidate)
            return decoded if len(decoded) >= 16 else None
        except ValueError:
            return None

    padded = candidate + "=" * (-len(candidate) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        return None
    return decoded if len(decoded) >= 16 else None


def _is_parseable_public_key(public_key: str) -> bool:
    if len(public_key) > 16_384 or not _PEM_PUBLIC_KEY_PATTERN.fullmatch(public_key):
        return False

    # Parsing catches malformed PEM when cryptography is installed.  Risk
    # assessment has no signed challenge, so this intentionally checks format
    # only; /device/attest performs the cryptographic verification.
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError:
        return True
    try:
        load_pem_public_key(public_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        return False
    return True


def score_device_signal(signature: Any, public_key: Any) -> tuple[float, bool]:
    """Score attestation material without claiming it proves possession."""

    signature_present = isinstance(signature, str) and bool(signature.strip())
    key_present = isinstance(public_key, str) and bool(public_key.strip())
    if not signature_present and not key_present:
        return NEUTRAL_RISK, False
    if not signature_present or not key_present:
        return 0.8, True
    if _decode_signature(signature) is None or not _is_parseable_public_key(public_key):
        return 0.8, True
    return 0.1, True


def _normalise_ip(ip_address: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    address = ipaddress.ip_address(ip_address.strip())
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def score_network_signal(ip_address: Any, user_agent: Any) -> tuple[float, bool, bool]:
    """Return ``(risk, signal_present, vpn_or_proxy_indicator)``.

    ``ipaddress`` is used for both IPv4 and IPv6 so shorthand IPv6, mapped IPv4,
    loopback, private, and link-local ranges are handled consistently.
    """

    risks: list[float] = []
    vpn_indicator = False

    if isinstance(ip_address, str) and ip_address.strip():
        try:
            address = _normalise_ip(ip_address)
        except ValueError:
            risks.append(0.7)
        else:
            if address.is_private or address.is_loopback or address.is_link_local:
                risks.append(0.85)
                vpn_indicator = True
            elif (
                address.is_unspecified
                or address.is_multicast
                or getattr(address, "is_reserved", False)
            ):
                risks.append(0.75)
            else:
                risks.append(0.1)

    if isinstance(user_agent, str) and user_agent.strip():
        if _VPN_PATTERN.search(user_agent):
            risks.append(0.9)
            vpn_indicator = True
        elif _BOT_PATTERN.search(user_agent):
            risks.append(0.7)
        else:
            risks.append(0.1)

    if not risks:
        return NEUTRAL_RISK, False, False
    return max(risks), True, vpn_indicator


def detect_vpn_proxy(ip_address: str | None, user_agent: str | None) -> tuple[bool, float]:
    """Skeleton-compatible VPN/proxy helper returning a bounded confidence."""

    risk, present, indicator = score_network_signal(ip_address, user_agent)
    return bool(present and indicator), risk


def _read_field(value: Any, field: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(field)
    return getattr(value, field, None)


def score_geolocation_signal(geolocation: Any) -> tuple[float, bool]:
    if geolocation is None:
        return NEUTRAL_RISK, False

    latitude = _safe_float(_read_field(geolocation, "latitude"))
    longitude = _safe_float(_read_field(geolocation, "longitude"))
    accuracy = _safe_float(_read_field(geolocation, "accuracy"))

    if latitude is None or longitude is None or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return 1.0, True
    if accuracy is None:
        return NEUTRAL_RISK, True
    if accuracy < 0:
        return 1.0, True
    if accuracy > 5_000:
        return 0.8, True
    if accuracy > 500:
        return 0.4, True
    if accuracy < 5:
        return 0.35, True
    return 0.1, True


def risk_level(score: float) -> str:
    if score < 0.3:
        return "LOW"
    if score < 0.5:
        return "MEDIUM"
    if score < 0.7:
        return "HIGH"
    return "CRITICAL"


def _request_values(request: Any) -> dict[str, Any]:
    if request is None:
        return {}
    if isinstance(request, Mapping):
        return dict(request)
    if hasattr(request, "model_dump"):
        return request.model_dump()
    if hasattr(request, "dict"):
        return request.dict()
    return {
        field: getattr(request, field, None)
        for field in (
            "liveness_score",
            "face_match_score",
            "device_signature",
            "device_public_key",
            "ip_address",
            "user_agent",
            "geolocation",
        )
    }


def assess_risk(
    request: Any = None,
    *,
    liveness_score: Any = None,
    face_match_score: Any = None,
    device_signature: Any = None,
    device_public_key: Any = None,
    ip_address: Any = None,
    user_agent: Any = None,
    geolocation: Any = None,
    risk_threshold: float = 0.5,
) -> RiskAssessment:
    """Fuse a mapping/model or explicit keyword signals into one risk result."""

    values = _request_values(request)
    explicit = {
        "liveness_score": liveness_score,
        "face_match_score": face_match_score,
        "device_signature": device_signature,
        "device_public_key": device_public_key,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "geolocation": geolocation,
    }
    for key, value in explicit.items():
        if value is not None or key not in values:
            values[key] = value

    threshold_value = _safe_float(risk_threshold)
    threshold = _clamp(threshold_value if threshold_value is not None else 0.5)

    liveness_risk, has_liveness = score_confidence_signal(values.get("liveness_score"))
    face_risk, has_face = score_confidence_signal(values.get("face_match_score"))
    device_risk, has_device = score_device_signal(
        values.get("device_signature"), values.get("device_public_key")
    )
    network_risk, has_network, vpn_indicator = score_network_signal(
        values.get("ip_address"), values.get("user_agent")
    )
    geolocation_risk, has_geolocation = score_geolocation_signal(values.get("geolocation"))

    raw = {
        "liveness": liveness_risk,
        "face_match": face_risk,
        "device": device_risk,
        "network": network_risk,
        "geolocation": geolocation_risk,
    }
    # Rounding contributions first keeps the documented invariant exact for
    # serialized output: sum(signal_breakdown.values()) == risk_score.
    breakdown = {
        name: round(_clamp(raw[name]) * weight, 6)
        for name, weight in SIGNAL_WEIGHTS.items()
    }
    score = round(_clamp(sum(breakdown.values())), 6)

    recommendations: list[str] = []
    if has_liveness and liveness_risk > RECOMMENDATION_RISK_CUTOFF:
        recommendations.append(LOW_LIVENESS_RECOMMENDATION)
    if has_face and face_risk > RECOMMENDATION_RISK_CUTOFF:
        recommendations.append(LOW_FACE_MATCH_RECOMMENDATION)
    if has_device and device_risk > RECOMMENDATION_RISK_CUTOFF:
        recommendations.append(DEVICE_RECOMMENDATION)
    if has_network and vpn_indicator and network_risk > RECOMMENDATION_RISK_CUTOFF:
        recommendations.append(VPN_RECOMMENDATION)
    if has_geolocation and geolocation_risk > RECOMMENDATION_RISK_CUTOFF:
        recommendations.append(GEOLOCATION_RECOMMENDATION)

    return RiskAssessment(
        risk_score=score,
        risk_level=risk_level(score),
        pass_threshold=score < threshold,
        risk_threshold=threshold,
        signal_breakdown=breakdown,
        recommendations=recommendations,
    )


__all__ = [
    "RiskAssessment",
    "SIGNAL_WEIGHTS",
    "assess_risk",
    "detect_vpn_proxy",
    "risk_level",
    "score_confidence_signal",
    "score_device_signal",
    "score_geolocation_signal",
    "score_network_signal",
]
