"""128-dimensional dlib face descriptor extraction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .detection import (
    CssBoundingBox,
    FaceDetectionResult,
    ModelUnavailableError,
    bbox_to_css,
    detect_face,
    get_face_recognition_backend,
    validate_rgb_image,
)


class FaceEmbeddingError(RuntimeError):
    """Base error for face descriptor extraction."""


class EmbeddingModelUnavailableError(FaceEmbeddingError):
    """Raised when the local dlib encoding model is unavailable."""


class NoFaceError(FaceEmbeddingError):
    """Raised when no descriptor can be produced for the selected face."""


class InvalidEmbeddingError(FaceEmbeddingError):
    """Raised when a model returns a malformed or non-finite descriptor."""


def _coerce_four_ints(value: Any) -> tuple[int, int, int, int] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None
    if len(value) != 4:
        return None
    try:
        return tuple(int(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError, OverflowError):
        return None


def _resolve_css_box(
    detection: FaceDetectionResult | Mapping[str, Any] | Sequence[int] | None,
    image_height: int,
    image_width: int,
) -> CssBoundingBox:
    if detection is None:
        raise NoFaceError("No face detection was supplied")

    raw_box: tuple[int, int, int, int] | None = None
    if isinstance(detection, FaceDetectionResult):
        if not detection.detected:
            raise NoFaceError("No face was detected")
        raw_box = detection.css_box
    elif isinstance(detection, Mapping):
        if detection.get("detected", detection.get("face_detected", True)) is False:
            raise NoFaceError("No face was detected")
        raw_box = _coerce_four_ints(detection.get("css_box"))
        if raw_box is None:
            pixel_box = _coerce_four_ints(detection.get("bbox"))
            if pixel_box is not None:
                raw_box = bbox_to_css(pixel_box)
    else:
        # A bare 4-tuple follows face_recognition's CSS convention.
        raw_box = _coerce_four_ints(detection)

    if raw_box is None:
        raise NoFaceError("The face detection has no valid bounding box")
    top, right, bottom, left = raw_box
    top = min(max(top, 0), image_height)
    bottom = min(max(bottom, 0), image_height)
    left = min(max(left, 0), image_width)
    right = min(max(right, 0), image_width)
    if bottom <= top or right <= left:
        raise NoFaceError("The face bounding box is outside the image")
    return top, right, bottom, left


def extract_face_embedding(
    image_array: np.ndarray,
    detection: FaceDetectionResult | Mapping[str, Any] | Sequence[int] | None = None,
    *,
    num_jitters: int = 1,
    model: str = "small",
) -> np.ndarray:
    """Extract one validated 128-d descriptor for a selected face.

    If ``detection`` is omitted, the same deterministic detector used by the
    endpoints selects a face.  A bare four-item sequence is interpreted as a
    face_recognition CSS box: ``(top, right, bottom, left)``.
    """

    image = validate_rgb_image(image_array)
    if isinstance(num_jitters, bool) or not isinstance(num_jitters, int):
        raise ValueError("num_jitters must be an integer")
    if not 1 <= num_jitters <= 10:
        raise ValueError("num_jitters must be between 1 and 10")
    if model not in {"small", "large"}:
        raise ValueError("model must be 'small' or 'large'")

    if detection is None:
        detection = detect_face(image)
    css_box = _resolve_css_box(detection, image.shape[0], image.shape[1])

    try:
        backend = get_face_recognition_backend()
    except ModelUnavailableError as exc:
        raise EmbeddingModelUnavailableError(
            "The face embedding model is unavailable"
        ) from exc
    encoder = getattr(backend, "face_encodings", None)
    if not callable(encoder):
        raise EmbeddingModelUnavailableError(
            "The face_recognition backend does not expose face_encodings"
        )

    try:
        encodings = encoder(
            image,
            known_face_locations=[css_box],
            num_jitters=num_jitters,
            model=model,
        )
    except Exception as exc:
        raise FaceEmbeddingError("Face descriptor extraction failed") from exc
    if not encodings:
        raise NoFaceError("No face descriptor could be extracted")

    embedding = np.asarray(encodings[0], dtype=np.float64)
    if embedding.shape != (128,):
        raise InvalidEmbeddingError("Face descriptor must contain 128 values")
    if not np.isfinite(embedding).all():
        raise InvalidEmbeddingError("Face descriptor contains non-finite values")
    if float(np.linalg.norm(embedding)) <= np.finfo(np.float64).eps:
        raise InvalidEmbeddingError("Face descriptor has zero magnitude")
    return np.ascontiguousarray(embedding).copy()


__all__ = [
    "EmbeddingModelUnavailableError",
    "FaceEmbeddingError",
    "InvalidEmbeddingError",
    "NoFaceError",
    "extract_face_embedding",
]
