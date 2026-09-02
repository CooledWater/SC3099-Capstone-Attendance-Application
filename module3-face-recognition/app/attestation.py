"""Optional device-attestation verification.

The caller is responsible for issuing one-time challenges and preventing
replay.  This module only proves that the supplied public key signed the exact
UTF-8 challenge bytes.  It fails closed if cryptography support is unavailable.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Mapping


MAX_PUBLIC_KEY_BYTES = 16_384
MAX_SIGNATURE_BYTES = 16_384
MAX_CHALLENGE_BYTES = 4_096


@dataclass(frozen=True, slots=True)
class AttestationResult:
    attestation_passed: bool
    attestation_score: float
    device_trusted: bool
    device_fingerprint: str
    issues: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        for field in ("device_public_key", "device_signature", "challenge", "device_info")
    }


def _decode_signature(value: str) -> bytes:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Device signature is empty")
    if len(candidate) > MAX_SIGNATURE_BYTES * 2:
        raise ValueError("Device signature is too large")

    if len(candidate) % 2 == 0:
        try:
            decoded = bytes.fromhex(candidate)
        except ValueError:
            decoded = b""
        if decoded:
            if len(decoded) > MAX_SIGNATURE_BYTES:
                raise ValueError("Device signature is too large")
            return decoded

    padded = candidate + "=" * (-len(candidate) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Device signature is not valid hex or base64") from exc
    if not decoded or len(decoded) > MAX_SIGNATURE_BYTES:
        raise ValueError("Device signature has an invalid size")
    return decoded


def _failed(issue: str, fingerprint: str = "") -> AttestationResult:
    return AttestationResult(
        attestation_passed=False,
        attestation_score=0.0,
        device_trusted=False,
        device_fingerprint=fingerprint,
        issues=[issue],
    )


def _verify_signature(public_key: Any, signature: bytes, challenge: bytes) -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, ed448, padding, rsa

    if isinstance(public_key, rsa.RSAPublicKey):
        try:
            public_key.verify(signature, challenge, padding.PKCS1v15(), hashes.SHA256())
        except Exception as pkcs_error:
            try:
                public_key.verify(
                    signature,
                    challenge,
                    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.AUTO),
                    hashes.SHA256(),
                )
            except Exception:
                raise pkcs_error
        return
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(signature, challenge, ec.ECDSA(hashes.SHA256()))
        return
    if isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
        public_key.verify(signature, challenge)
        return
    raise TypeError("Unsupported public-key algorithm")


def verify_device_attestation(
    request: Any = None,
    *,
    device_public_key: str | None = None,
    device_signature: str | None = None,
    challenge: str | None = None,
    device_info: Mapping[str, Any] | None = None,
) -> AttestationResult:
    """Verify RSA, ECDSA, Ed25519, or Ed448 proof-of-possession.

    ``device_info`` is deliberately not trusted or incorporated into the
    signature implicitly.  Applications that bind metadata should include its
    canonical representation in the issued challenge.
    """

    values = _request_values(request)
    explicit = {
        "device_public_key": device_public_key,
        "device_signature": device_signature,
        "challenge": challenge,
        "device_info": device_info,
    }
    for key, value in explicit.items():
        if value is not None or key not in values:
            values[key] = value

    pem = values.get("device_public_key")
    encoded_signature = values.get("device_signature")
    challenge_value = values.get("challenge")

    if not isinstance(pem, str) or not pem.strip():
        return _failed("Device public key is required")
    if not isinstance(encoded_signature, str) or not encoded_signature.strip():
        return _failed("Device signature is required")
    if not isinstance(challenge_value, str) or not challenge_value:
        return _failed("Attestation challenge is required")

    try:
        pem_bytes = pem.encode("ascii")
        challenge_bytes = challenge_value.encode("utf-8")
    except UnicodeEncodeError:
        return _failed("Device public key must be ASCII PEM")
    if len(pem_bytes) > MAX_PUBLIC_KEY_BYTES:
        return _failed("Device public key is too large")
    if len(challenge_bytes) > MAX_CHALLENGE_BYTES:
        return _failed("Attestation challenge is too large")

    try:
        signature = _decode_signature(encoded_signature)
    except ValueError as exc:
        return _failed(str(exc))

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return _failed("Cryptographic verification is unavailable")

    try:
        public_key = serialization.load_pem_public_key(pem_bytes)
        canonical_key = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (ValueError, TypeError):
        return _failed("Device public key is malformed or unsupported")
    except Exception:
        return _failed("Device public key is malformed or unsupported")

    fingerprint = hashlib.sha256(canonical_key).hexdigest()
    try:
        _verify_signature(public_key, signature, challenge_bytes)
    except InvalidSignature:
        return _failed("Device signature verification failed", fingerprint)
    except TypeError:
        return _failed("Device public key algorithm is unsupported", fingerprint)
    except Exception:
        return _failed("Device signature verification failed", fingerprint)

    return AttestationResult(
        attestation_passed=True,
        attestation_score=0.95,
        device_trusted=True,
        device_fingerprint=fingerprint,
        issues=[],
    )


__all__ = ["AttestationResult", "verify_device_attestation"]
