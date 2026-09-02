"""Cancelable 256-bit SimHash templates for 128-dimensional face embeddings.

The returned value is always a 64-character lowercase hexadecimal string.  It
fits the existing database/API contract while retaining locality, which allows
the stateless service to compare a new embedding with an enrolled template.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from numbers import Real
from typing import TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .config import (
    FACE_EMBEDDING_DIM,
    FACE_MATCH_HAMMING_FRACTION,
    FACE_MATCH_THRESHOLD,
    SIMHASH_BITS,
    SIMHASH_SEED,
)


FloatArray: TypeAlias = NDArray[np.float64]
_TEMPLATE_PATTERN = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_CHANCE_HAMMING_FRACTION = 0.50


class InvalidEmbeddingError(ValueError):
    """Raised when an embedding cannot be converted into a safe template."""


class InvalidTemplateHashError(ValueError):
    """Raised when a reference is not a canonical Module 3 template."""


def build_hyperplanes(seed: int = SIMHASH_SEED) -> FloatArray:
    """Build the deterministic keyed 256 x 128 projection matrix.

    Deployments should override ``SIMHASH_SEED`` with a secret non-negative
    integer.  Rotating it invalidates previously enrolled templates, providing
    the revocation property of cancelable biometrics.
    """

    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise TypeError("SimHash seed must be a non-negative integer")
    seed_value = int(seed)
    if seed_value < 0:
        raise ValueError("SimHash seed must be a non-negative integer")

    # default_rng uses PCG64 for integer seeds.  Its deterministic stream keeps
    # enrollment and verification templates stable across service rebuilds.
    matrix = np.random.default_rng(seed_value).standard_normal(
        (SIMHASH_BITS, FACE_EMBEDDING_DIM)
    )
    matrix.setflags(write=False)
    return matrix


_HYPERPLANES = build_hyperplanes()


def normalize_embedding(embedding: ArrayLike) -> FloatArray:
    """Return a finite, unit-length 128-dimensional embedding."""

    try:
        vector = np.asarray(embedding, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise InvalidEmbeddingError("face embedding must be numeric") from exc

    if vector.shape != (FACE_EMBEDDING_DIM,):
        raise InvalidEmbeddingError(
            f"face embedding must have shape ({FACE_EMBEDDING_DIM},)"
        )
    if not np.isfinite(vector).all():
        raise InvalidEmbeddingError("face embedding must contain only finite values")

    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= np.finfo(np.float64).eps:
        raise InvalidEmbeddingError("face embedding must have non-zero magnitude")
    return vector / norm


def _validated_hyperplanes(hyperplanes: ArrayLike | None) -> FloatArray:
    if hyperplanes is None:
        return _HYPERPLANES
    try:
        matrix = np.asarray(hyperplanes, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise InvalidEmbeddingError("hyperplanes must be numeric") from exc
    expected_shape = (SIMHASH_BITS, FACE_EMBEDDING_DIM)
    if matrix.shape != expected_shape:
        raise InvalidEmbeddingError(f"hyperplanes must have shape {expected_shape}")
    if not np.isfinite(matrix).all():
        raise InvalidEmbeddingError("hyperplanes must contain only finite values")
    return matrix


def simhash_hex(
    embedding: ArrayLike,
    *,
    hyperplanes: ArrayLike | None = None,
) -> str:
    """Project an embedding to the canonical 256-bit lowercase hex template."""

    vector = normalize_embedding(embedding)
    matrix = _validated_hyperplanes(hyperplanes)
    projections = matrix @ vector
    # A projection exactly on a hyperplane is assigned to its positive side so
    # the encoding remains deterministic.
    sign_bits = projections >= 0.0
    packed = np.packbits(sign_bits, bitorder="big")
    template_hash = packed.tobytes().hex()
    if len(template_hash) != SIMHASH_BITS // 4:  # pragma: no cover - invariant
        raise RuntimeError("unexpected SimHash template length")
    return template_hash


def validate_template_hash(template_hash: str) -> str:
    """Validate and return a canonical lowercase 256-bit template.

    No normalization is performed: uppercase, whitespace, prefixes, and values
    of the wrong length are rejected so there is one unambiguous wire format.
    Route handlers should translate :class:`InvalidTemplateHashError` into an
    HTTP 400 response.
    """

    if not isinstance(template_hash, str) or _TEMPLATE_PATTERN.fullmatch(
        template_hash
    ) is None:
        raise InvalidTemplateHashError(
            "reference template hash must be exactly 64 lowercase hexadecimal characters"
        )
    return template_hash


def hamming_distance(left: str, right: str) -> int:
    """Return the number of differing bits between two templates."""

    left_bytes = bytes.fromhex(validate_template_hash(left))
    right_bytes = bytes.fromhex(validate_template_hash(right))
    return sum(
        (left_byte ^ right_byte).bit_count()
        for left_byte, right_byte in zip(left_bytes, right_bytes, strict=True)
    )


def hamming_fraction(left: str, right: str) -> float:
    """Return normalized Hamming distance in the closed interval [0, 1]."""

    return hamming_distance(left, right) / SIMHASH_BITS


def hamming_hex(left: str, right: str) -> float:
    """Compatibility name for normalized Hamming distance between hex values."""

    return hamming_fraction(left, right)


def _finite_fraction(value: Real, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def match_score(
    fraction: Real,
    *,
    match_fraction: Real = FACE_MATCH_HAMMING_FRACTION,
    threshold: Real = FACE_MATCH_THRESHOLD,
) -> float:
    """Map Hamming fraction to a calibrated, monotone similarity score.

    The piecewise-linear mapping is exactly ``threshold`` at
    ``match_fraction``, 1.0 for identical templates, and 0.0 at chance-level
    disagreement (or beyond).
    """

    f = _finite_fraction(fraction, "Hamming fraction")
    boundary = _finite_fraction(match_fraction, "match fraction")
    decision_threshold = _finite_fraction(threshold, "match threshold")
    if not 0.0 <= f <= 1.0:
        raise ValueError("Hamming fraction must be between 0 and 1")
    if not 0.0 < boundary < _CHANCE_HAMMING_FRACTION:
        raise ValueError("match fraction must be greater than 0 and less than 0.5")
    if not 0.0 <= decision_threshold <= 1.0:
        raise ValueError("match threshold must be between 0 and 1")

    if f <= boundary:
        score = decision_threshold + (1.0 - decision_threshold) * (
            boundary - f
        ) / boundary
    else:
        score = decision_threshold * max(
            0.0,
            (_CHANCE_HAMMING_FRACTION - f)
            / (_CHANCE_HAMMING_FRACTION - boundary),
        )
    return min(1.0, max(0.0, float(score)))


@dataclass(frozen=True, slots=True)
class TemplateComparison:
    """Full result of comparing two canonical templates."""

    hamming_distance: int
    hamming_fraction: float
    match_score: float
    match_passed: bool


def compare_templates(left: str, right: str) -> TemplateComparison:
    """Validate and compare two templates using configured calibration."""

    distance = hamming_distance(left, right)
    fraction = distance / SIMHASH_BITS
    score = match_score(fraction)
    return TemplateComparison(
        hamming_distance=distance,
        hamming_fraction=fraction,
        match_score=score,
        match_passed=score >= FACE_MATCH_THRESHOLD,
    )


__all__ = [
    "InvalidEmbeddingError",
    "InvalidTemplateHashError",
    "TemplateComparison",
    "build_hyperplanes",
    "normalize_embedding",
    "simhash_hex",
    "validate_template_hash",
    "hamming_distance",
    "hamming_fraction",
    "hamming_hex",
    "match_score",
    "compare_templates",
]
