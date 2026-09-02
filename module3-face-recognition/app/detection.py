"""Thread-safe face detection using dlib HOG and MediaPipe confidence.

dlib (through :mod:`face_recognition`) supplies the canonical face location
used for encoding.  MediaPipe runs alongside it to provide a calibrated
detection confidence.  A face is usable only when dlib locates it; a dlib box
without a corresponding MediaPipe detection is retained with confidence 0.0
so callers cannot accidentally treat an uncorroborated face as high quality.
"""

from __future__ import annotations

import importlib
import math
import threading
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Final, TypeAlias

import numpy as np


# Pixel boxes use (x, y, width, height).  CSS boxes use the ordering required
# by face_recognition: (top, right, bottom, left).
PixelBoundingBox: TypeAlias = tuple[int, int, int, int]
CssBoundingBox: TypeAlias = tuple[int, int, int, int]

_RESULT_KEYS: Final[tuple[str, ...]] = (
    "detected",
    "confidence",
    "bbox",
    "css_box",
    "face_count",
    "multiple_faces",
)


class FaceDetectionError(RuntimeError):
    """Base error for failures in the face-detection pipeline."""


class ModelUnavailableError(FaceDetectionError):
    """Raised when a required local face model cannot be loaded."""


class InvalidImageArrayError(ValueError):
    """Raised when detection receives something other than an RGB image."""


@dataclass(frozen=True, slots=True)
class FaceDetectionResult(Mapping[str, object]):
    """One deterministic dlib face result with MediaPipe corroboration.

    ``bbox`` is an integer ``(x, y, width, height)`` pixel box. ``css_box`` is
    ``(top, right, bottom, left)``, ready for ``face_recognition``.  Mapping
    behavior keeps the result compatible with the original skeleton's loose
    dictionary contract.
    """

    detected: bool
    confidence: float
    bbox: PixelBoundingBox | None
    css_box: CssBoundingBox | None
    face_count: int = 0
    multiple_faces: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "detected": self.detected,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "css_box": self.css_box,
            "face_count": self.face_count,
            "multiple_faces": self.multiple_faces,
        }

    def __getitem__(self, key: str) -> object:
        if key not in _RESULT_KEYS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(_RESULT_KEYS)

    def __len__(self) -> int:
        return len(_RESULT_KEYS)

    def __bool__(self) -> bool:
        return self.detected


@dataclass(frozen=True, slots=True)
class _MediaPipeCandidate:
    confidence: float
    bbox: PixelBoundingBox


_import_lock = threading.Lock()
_face_recognition_backend: Any | None = None
_mediapipe_backend: Any | None = None
_thread_models = threading.local()


def validate_rgb_image(image: np.ndarray) -> np.ndarray:
    """Validate and return a contiguous RGB uint8 image."""

    if not isinstance(image, np.ndarray):
        raise InvalidImageArrayError("Image must be a NumPy array")
    if image.ndim != 3 or image.shape[2] != 3:
        raise InvalidImageArrayError("Image must have RGB shape (height, width, 3)")
    if image.shape[0] <= 0 or image.shape[1] <= 0:
        raise InvalidImageArrayError("Image dimensions must be positive")
    if image.dtype != np.uint8:
        raise InvalidImageArrayError("Image must use uint8 RGB pixels")
    return np.ascontiguousarray(image)


def get_face_recognition_backend() -> Any:
    """Lazily import the face_recognition/dlib backend exactly once."""

    global _face_recognition_backend
    if _face_recognition_backend is not None:
        return _face_recognition_backend
    with _import_lock:
        if _face_recognition_backend is None:
            try:
                backend = importlib.import_module("face_recognition")
            except (ImportError, OSError) as exc:
                raise ModelUnavailableError(
                    "The face_recognition/dlib model is unavailable"
                ) from exc
            if not callable(getattr(backend, "face_locations", None)):
                raise ModelUnavailableError(
                    "The face_recognition backend does not expose face_locations"
                )
            _face_recognition_backend = backend
    return _face_recognition_backend


def _get_mediapipe_backend() -> Any:
    global _mediapipe_backend
    if _mediapipe_backend is not None:
        return _mediapipe_backend
    with _import_lock:
        if _mediapipe_backend is None:
            try:
                backend = importlib.import_module("mediapipe")
            except (ImportError, OSError) as exc:
                raise ModelUnavailableError("The MediaPipe face model is unavailable") from exc
            face_detection = getattr(
                getattr(getattr(backend, "solutions", None), "face_detection", None),
                "FaceDetection",
                None,
            )
            if face_detection is None:
                raise ModelUnavailableError(
                    "MediaPipe does not expose the FaceDetection solution"
                )
            _mediapipe_backend = backend
    return _mediapipe_backend


def get_mediapipe_face_detector() -> Any:
    """Return a FaceDetection instance owned by the current worker thread."""

    detector = getattr(_thread_models, "face_detector", None)
    if detector is not None:
        return detector

    backend = _get_mediapipe_backend()
    detector_class = backend.solutions.face_detection.FaceDetection
    try:
        detector = detector_class(
            model_selection=0,
            min_detection_confidence=0.5,
        )
    except Exception as exc:  # MediaPipe may surface native initialization errors
        raise ModelUnavailableError("The MediaPipe face detector failed to load") from exc
    _thread_models.face_detector = detector
    return detector


def close_thread_local_models() -> None:
    """Close models held by the current thread, primarily for test teardown."""

    detector = getattr(_thread_models, "face_detector", None)
    if detector is not None:
        close = getattr(detector, "close", None)
        if callable(close):
            close()
        delattr(_thread_models, "face_detector")


def _clip_css_box(
    box: tuple[int, int, int, int] | list[int], height: int, width: int
) -> CssBoundingBox | None:
    if len(box) != 4:
        return None
    top, right, bottom, left = (int(value) for value in box)
    top = min(max(top, 0), height)
    bottom = min(max(bottom, 0), height)
    left = min(max(left, 0), width)
    right = min(max(right, 0), width)
    if bottom <= top or right <= left:
        return None
    return top, right, bottom, left


def css_to_bbox(box: CssBoundingBox) -> PixelBoundingBox:
    """Convert ``(top, right, bottom, left)`` to ``(x, y, w, h)``."""

    top, right, bottom, left = box
    return left, top, right - left, bottom - top


def bbox_to_css(box: PixelBoundingBox) -> CssBoundingBox:
    """Convert ``(x, y, w, h)`` to ``(top, right, bottom, left)``."""

    x, y, width, height = box
    return y, x + width, y + height, x


def _clip_pixel_box(
    x_min: float,
    y_min: float,
    box_width: float,
    box_height: float,
    image_height: int,
    image_width: int,
) -> PixelBoundingBox | None:
    if not all(math.isfinite(v) for v in (x_min, y_min, box_width, box_height)):
        return None
    left = min(max(int(math.floor(x_min)), 0), image_width)
    top = min(max(int(math.floor(y_min)), 0), image_height)
    right = min(max(int(math.ceil(x_min + box_width)), 0), image_width)
    bottom = min(max(int(math.ceil(y_min + box_height)), 0), image_height)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def _intersection_over_union(a: PixelBoundingBox, b: PixelBoundingBox) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = float((right - left) * (bottom - top))
    union = float(aw * ah + bw * bh) - intersection
    return intersection / union if union > 0.0 else 0.0


def _mediapipe_candidates(image: np.ndarray) -> tuple[_MediaPipeCandidate, ...]:
    detector = get_mediapipe_face_detector()
    try:
        output = detector.process(image)
    except Exception as exc:
        raise FaceDetectionError("MediaPipe face detection failed") from exc

    image_height, image_width = image.shape[:2]
    candidates: list[_MediaPipeCandidate] = []
    for detection in getattr(output, "detections", None) or ():
        scores = getattr(detection, "score", None) or ()
        try:
            confidence = float(scores[0])
        except (IndexError, TypeError, ValueError):
            confidence = 0.0
        if not math.isfinite(confidence):
            confidence = 0.0
        confidence = min(max(confidence, 0.0), 1.0)

        location = getattr(detection, "location_data", None)
        relative_box = getattr(location, "relative_bounding_box", None)
        if relative_box is None:
            continue
        box = _clip_pixel_box(
            float(relative_box.xmin) * image_width,
            float(relative_box.ymin) * image_height,
            float(relative_box.width) * image_width,
            float(relative_box.height) * image_height,
            image_height,
            image_width,
        )
        if box is not None:
            candidates.append(_MediaPipeCandidate(confidence, box))

    # Stable ordering also makes mocked/model-regression tests deterministic.
    candidates.sort(
        key=lambda item: (
            -item.confidence,
            -(item.bbox[2] * item.bbox[3]),
            item.bbox[1],
            item.bbox[0],
        )
    )
    return tuple(candidates)


def _dlib_locations(image: np.ndarray) -> tuple[CssBoundingBox, ...]:
    backend = get_face_recognition_backend()
    try:
        raw_boxes = backend.face_locations(
            image,
            number_of_times_to_upsample=0,
            model="hog",
        )
        # Small images are cheap to retry and benefit most from one upsample.
        if not raw_boxes and max(image.shape[:2]) <= 512:
            raw_boxes = backend.face_locations(
                image,
                number_of_times_to_upsample=1,
                model="hog",
            )
    except Exception as exc:
        raise FaceDetectionError("dlib HOG face detection failed") from exc

    image_height, image_width = image.shape[:2]
    clipped = {
        box
        for raw_box in raw_boxes
        if (box := _clip_css_box(raw_box, image_height, image_width)) is not None
    }
    return tuple(
        sorted(
            clipped,
            key=lambda box: (
                box[0],
                box[3],
                -(box[2] - box[0]) * (box[1] - box[3]),
            ),
        )
    )


def detect_faces(image_array: np.ndarray) -> tuple[FaceDetectionResult, ...]:
    """Detect every usable face, ordered by confidence then area.

    Model imports and initialization are lazy.  MediaPipe instances are
    thread-local because its Solution objects are not safe to share between
    FastAPI worker threads.
    """

    image = validate_rgb_image(image_array)
    media_candidates = _mediapipe_candidates(image)
    css_boxes = _dlib_locations(image)
    face_count = len(css_boxes)
    if face_count == 0:
        return ()

    results: list[FaceDetectionResult] = []
    for css_box in css_boxes:
        bbox = css_to_bbox(css_box)
        confidence = 0.0
        best_iou = 0.0
        for candidate in media_candidates:
            overlap = _intersection_over_union(bbox, candidate.bbox)
            if overlap > best_iou:
                best_iou = overlap
                confidence = candidate.confidence
        # A zero-IoU detection is unrelated and must not lend its confidence.
        if best_iou == 0.0:
            confidence = 0.0
        results.append(
            FaceDetectionResult(
                detected=True,
                confidence=confidence,
                bbox=bbox,
                css_box=css_box,
                face_count=face_count,
                multiple_faces=face_count > 1,
            )
        )

    results.sort(
        key=lambda item: (
            -item.confidence,
            -((item.bbox or (0, 0, 0, 0))[2] * (item.bbox or (0, 0, 0, 0))[3]),
            (item.bbox or (0, 0, 0, 0))[1],
            (item.bbox or (0, 0, 0, 0))[0],
        )
    )
    return tuple(results)


def detect_face(image_array: np.ndarray) -> FaceDetectionResult:
    """Return the deterministic best face, or a typed negative result."""

    faces = detect_faces(image_array)
    if faces:
        return faces[0]
    return FaceDetectionResult(
        detected=False,
        confidence=0.0,
        bbox=None,
        css_box=None,
        face_count=0,
        multiple_faces=False,
    )


__all__ = [
    "CssBoundingBox",
    "FaceDetectionError",
    "FaceDetectionResult",
    "InvalidImageArrayError",
    "ModelUnavailableError",
    "PixelBoundingBox",
    "bbox_to_css",
    "close_thread_local_models",
    "css_to_bbox",
    "detect_face",
    "detect_faces",
    "get_face_recognition_backend",
    "get_mediapipe_face_detector",
    "validate_rgb_image",
]
