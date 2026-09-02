"""Normalized face-image quality assessment.

The score follows the implementation plan exactly: detection confidence 35%,
face size 25%, sharpness 20%, face resolution 10%, and brightness/contrast
10%.  Every component is independently constrained to ``[0, 1]``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from .detection import FaceDetectionResult, PixelBoundingBox, css_to_bbox, validate_rgb_image


_COMPONENT_WEIGHTS: Final[dict[str, float]] = {
    "detection_confidence": 0.35,
    "face_size": 0.25,
    "sharpness": 0.20,
    "resolution": 0.10,
    "brightness_contrast": 0.10,
}


class InvalidFaceCropError(ValueError):
    """Raised when a supplied face box has no pixels inside the image."""


@dataclass(frozen=True, slots=True)
class QualityAssessment(Mapping[str, object]):
    """Complete quality result with normalized components and raw metrics."""

    score: float
    label: str
    components: dict[str, float]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "quality_score": self.score,
            "image_quality": self.label,
            "components": dict(self.components),
            "metrics": dict(self.metrics),
        }

    def __getitem__(self, key: str) -> object:
        aliases: dict[str, object] = {
            "score": self.score,
            "quality_score": self.score,
            "label": self.label,
            "image_quality": self.label,
            "components": self.components,
            "metrics": self.metrics,
        }
        if key not in aliases:
            raise KeyError(key)
        return aliases[key]

    def __iter__(self) -> Iterator[str]:
        return iter(("quality_score", "image_quality", "components", "metrics"))

    def __len__(self) -> int:
        return 4

    def __float__(self) -> float:
        return self.score


def _clamp(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return min(max(float(value), 0.0), 1.0)


def _four_ints(value: Any) -> tuple[int, int, int, int] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None
    if len(value) != 4:
        return None
    try:
        return tuple(int(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError, OverflowError):
        return None


def _detection_values(
    detection: FaceDetectionResult | Mapping[str, Any] | None,
) -> tuple[float, PixelBoundingBox | None]:
    if isinstance(detection, FaceDetectionResult):
        return _clamp(detection.confidence), detection.bbox
    if isinstance(detection, Mapping):
        try:
            confidence = _clamp(float(detection.get("confidence", 0.0)))
        except (TypeError, ValueError):
            confidence = 0.0
        bbox = _four_ints(detection.get("bbox"))
        if bbox is None:
            css_box = _four_ints(detection.get("css_box"))
            if css_box is not None:
                bbox = css_to_bbox(css_box)
        return confidence, bbox
    return 0.0, None


def normalize_bbox(
    image_array: np.ndarray,
    box: PixelBoundingBox | Sequence[int] | None,
) -> PixelBoundingBox | None:
    """Clip an ``(x, y, width, height)`` box to image bounds."""

    image = validate_rgb_image(image_array)
    values = _four_ints(box)
    if values is None:
        return None
    x, y, width, height = values
    if width <= 0 or height <= 0:
        return None

    image_height, image_width = image.shape[:2]
    left = min(max(x, 0), image_width)
    top = min(max(y, 0), image_height)
    right = min(max(x + width, 0), image_width)
    bottom = min(max(y + height, 0), image_height)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def crop_face(
    image_array: np.ndarray,
    detection_or_bbox: FaceDetectionResult | Mapping[str, Any] | Sequence[int],
    *,
    padding: float = 0.0,
) -> np.ndarray:
    """Return a safely clipped face crop without writing or caching pixels."""

    image = validate_rgb_image(image_array)
    if not math.isfinite(padding) or padding < 0.0 or padding > 1.0:
        raise ValueError("padding must be between 0 and 1")

    if isinstance(detection_or_bbox, (FaceDetectionResult, Mapping)):
        _, box = _detection_values(detection_or_bbox)
    else:
        box = _four_ints(detection_or_bbox)
    normalized = normalize_bbox(image, box)
    if normalized is None:
        raise InvalidFaceCropError("Face bounding box has no pixels inside the image")

    x, y, width, height = normalized
    if padding:
        pad_x = int(round(width * padding))
        pad_y = int(round(height * padding))
        normalized = normalize_bbox(
            image,
            (x - pad_x, y - pad_y, width + 2 * pad_x, height + 2 * pad_y),
        )
        if normalized is None:  # defensive; the unpadded box was already valid
            raise InvalidFaceCropError("Padded face bounding box is invalid")
        x, y, width, height = normalized
    return image[y : y + height, x : x + width]


def _luma(rgb: np.ndarray) -> np.ndarray:
    # Rec. 601 coefficients match common OpenCV/Pillow luminance conversion.
    return (
        rgb[..., 0].astype(np.float32) * 0.299
        + rgb[..., 1].astype(np.float32) * 0.587
        + rgb[..., 2].astype(np.float32) * 0.114
    )


def _sharpness(luma: np.ndarray) -> tuple[float, float]:
    if min(luma.shape) < 3:
        return 0.0, 0.0
    center = luma[1:-1, 1:-1]
    laplacian = (
        luma[:-2, 1:-1]
        + luma[2:, 1:-1]
        + luma[1:-1, :-2]
        + luma[1:-1, 2:]
        - 4.0 * center
    )
    variance = float(np.var(laplacian, dtype=np.float64))
    # 25 is noticeably blurred; 350 is crisp for ordinary JPEG webcam data.
    score = _clamp((variance - 25.0) / 325.0)
    return variance, score


def _face_size_score(area_ratio: float) -> float:
    # The ideal band covers a face occupying 10%-35% of the frame.  Tiny and
    # extremely close/cropped faces degrade smoothly instead of crashing.
    if area_ratio < 0.01:
        return 0.0
    if area_ratio < 0.10:
        return _clamp((area_ratio - 0.01) / 0.09)
    if area_ratio <= 0.35:
        return 1.0
    return _clamp(1.0 - (area_ratio - 0.35) / 0.50)


def _brightness_score(mean: float) -> float:
    if 60.0 <= mean <= 205.0:
        return 1.0
    if mean < 60.0:
        return _clamp((mean - 15.0) / 45.0)
    return _clamp((245.0 - mean) / 40.0)


def _quality_label(score: float) -> str:
    if score >= 0.75:
        return "good"
    if score >= 0.50:
        return "fair"
    return "poor"


def assess_face_quality(
    image_array: np.ndarray,
    detection: FaceDetectionResult | Mapping[str, Any] | None = None,
    *,
    confidence: float | None = None,
    bbox: PixelBoundingBox | Sequence[int] | None = None,
) -> QualityAssessment:
    """Calculate the plan's weighted, normalized face quality score.

    Explicit ``confidence`` and ``bbox`` keyword values override those in the
    detection object, which is useful for isolated calibration and unit tests.
    Invalid/out-of-bounds crops produce conservative zero-valued components.
    """

    image = validate_rgb_image(image_array)
    detected_confidence, detected_bbox = _detection_values(detection)
    if confidence is not None:
        try:
            detected_confidence = _clamp(float(confidence))
        except (TypeError, ValueError):
            detected_confidence = 0.0
    selected_bbox = _four_ints(bbox) if bbox is not None else detected_bbox
    selected_bbox = normalize_bbox(image, selected_bbox)

    components = {
        "detection_confidence": detected_confidence,
        "face_size": 0.0,
        "sharpness": 0.0,
        "resolution": 0.0,
        "brightness_contrast": 0.0,
    }
    metrics = {
        "face_area_ratio": 0.0,
        "laplacian_variance": 0.0,
        "face_min_dimension": 0.0,
        "luma_mean": 0.0,
        "luma_std": 0.0,
    }

    if selected_bbox is not None:
        x, y, face_width, face_height = selected_bbox
        image_height, image_width = image.shape[:2]
        area_ratio = (face_width * face_height) / float(image_width * image_height)
        crop = image[y : y + face_height, x : x + face_width]
        gray = _luma(crop)
        laplacian_variance, sharpness_score = _sharpness(gray)
        luma_mean = float(np.mean(gray, dtype=np.float64))
        luma_std = float(np.std(gray, dtype=np.float64))
        brightness = _brightness_score(luma_mean)
        contrast = _clamp((luma_std - 5.0) / 35.0)

        components.update(
            {
                "face_size": _face_size_score(area_ratio),
                "sharpness": sharpness_score,
                "resolution": _clamp(min(face_width, face_height) / 256.0),
                "brightness_contrast": _clamp(0.60 * brightness + 0.40 * contrast),
            }
        )
        metrics.update(
            {
                "face_area_ratio": float(area_ratio),
                "laplacian_variance": laplacian_variance,
                "face_min_dimension": float(min(face_width, face_height)),
                "luma_mean": luma_mean,
                "luma_std": luma_std,
            }
        )

    score = _clamp(
        sum(
            _COMPONENT_WEIGHTS[name] * _clamp(value)
            for name, value in components.items()
        )
    )
    # Stable, bounded values are easier to serialize and compare in tests.
    components = {name: round(_clamp(value), 6) for name, value in components.items()}
    metrics = {
        name: round(float(value), 6) if math.isfinite(float(value)) else 0.0
        for name, value in metrics.items()
    }
    score = round(score, 6)
    return QualityAssessment(
        score=score,
        label=_quality_label(score),
        components=components,
        metrics=metrics,
    )


def calculate_quality_score(
    image_array: np.ndarray,
    detection: FaceDetectionResult | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> float:
    """Backward-compatible convenience wrapper returning only the score."""

    return assess_face_quality(image_array, detection, **kwargs).score


# A descriptive alias for consumers that used the skeleton helper naming.
calculate_face_quality = assess_face_quality


__all__ = [
    "InvalidFaceCropError",
    "QualityAssessment",
    "assess_face_quality",
    "calculate_face_quality",
    "calculate_quality_score",
    "crop_face",
    "normalize_bbox",
]
