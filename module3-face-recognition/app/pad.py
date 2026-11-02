"""Pinned MiniFASNet ensemble. Only models, never input pixels, are reused.

Crop arithmetic follows Minivision's Apache-2.0 generate_patches.py; see the
bundled notices. OpenCV Net state is protected by one lock per process, bounding
CPU inference concurrency without retaining request tensors on a reusable Net.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import settings
from .metrics import record_pad_outcome


MODEL_VERSION = "minifasnet-v2-v1se-onnx-v1"
MODEL_SPECS = (
    ("MiniFASNetV2.onnx", 2.7, "b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907"),
    ("MiniFASNetV1SE.onnx", 4.0, "ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676"),
)
_lock = threading.Lock()
_runtime: PadRuntime | None = None
_runtime_path: str | None = None


class PadUnavailableError(RuntimeError):
    """Missing/corrupt assets or inference failure, never a spoof verdict."""


@dataclass(frozen=True, slots=True)
class PadAnalysis:
    live_score: float
    passed: bool
    model_version: str
    inference_ms: float
    v2_live_score: float
    v1se_live_score: float

    def details(self) -> dict[str, Any]:
        return {
            "pad_evaluated": True, "pad_status": "evaluated",
            "pad_model_version": self.model_version,
            "pad_live_score": round(self.live_score, 6), "pad_passed": self.passed,
            "pad_inference_ms": round(self.inference_ms, 3),
            "pad_v2_live_score": round(self.v2_live_score, 6),
            "pad_v1se_live_score": round(self.v1se_live_score, 6),
        }


def unevaluated_details(mode: str, threshold: float, status: str = "not_evaluated") -> dict[str, Any]:
    return {
        "pad_mode": mode, "pad_threshold": threshold,
        "pad_model_version": MODEL_VERSION, "pad_evaluated": False,
        "pad_status": "off" if mode == "off" else status,
        "pad_live_score": None, "pad_passed": None, "pad_inference_ms": None,
        "pad_v2_live_score": None, "pad_v1se_live_score": None,
    }


def context_box(image_shape, bbox, scale):
    """Original boundary shifting and inclusive end coordinates, xywh input."""
    height, width = image_shape[:2]
    if height < 2 or width < 2 or bbox is None or len(bbox) != 4:
        raise PadUnavailableError("PAD face box is unavailable")
    x, y, box_w, box_h = map(float, bbox)
    if (not all(math.isfinite(v) for v in (x, y, box_w, box_h, scale))
            or box_w <= 0 or box_h <= 0 or scale <= 0
            or x < 0 or y < 0 or x + box_w > width or y + box_h > height):
        raise PadUnavailableError("PAD face box is invalid")
    scale = min((height - 1) / box_h, (width - 1) / box_w, scale)
    new_w, new_h = box_w * scale, box_h * scale
    center_x, center_y = x + box_w / 2, y + box_h / 2
    left, top = center_x - new_w / 2, center_y - new_h / 2
    right, bottom = center_x + new_w / 2, center_y + new_h / 2
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > width - 1:
        left -= right - width + 1
        right = width - 1
    if bottom > height - 1:
        top -= bottom - height + 1
        bottom = height - 1
    return int(left), int(top), int(right), int(bottom)


def preprocess(image_rgb, bbox, scale):
    """RGB uint8 -> original context crop -> BGR float32 NCHW, range 0–255."""
    image = np.asarray(image_rgb)
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise PadUnavailableError("PAD requires RGB uint8 pixels")
    left, top, right, bottom = context_box(image.shape, bbox, scale)
    patch = cv2.resize(image[top:bottom + 1, left:right + 1], (80, 80),
                       interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(patch[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32)


def class_probabilities(output):
    """Pinned graphs emit logits. Apply exactly one stable softmax."""
    logits = np.asarray(output)
    if logits.shape != (1, 3) or not np.isfinite(logits).all():
        raise PadUnavailableError("PAD output is invalid")
    logits = logits.astype(np.float64)
    exponentials = np.exp(logits - logits.max(axis=1, keepdims=True))
    probabilities = exponentials / exponentials.sum(axis=1, keepdims=True)
    if not np.isfinite(probabilities).all():
        raise PadUnavailableError("PAD output is invalid")
    return probabilities[0]


class PadRuntime:
    """Caller holds _lock around all mutable OpenCV inference operations."""
    def __init__(self, manifest_path):
        try:
            path = Path(manifest_path)
            manifest = json.loads(path.read_text())
            expected = {
                "model_version": MODEL_VERSION, "input_shape": [1, 3, 80, 80],
                "color_order": "BGR", "input_range": [0, 255],
                "output_type": "logits", "output_shape": [1, 3], "live_class_index": 1,
                "crop_recipe": "minivision-inclusive-shift-v1",
                "models": [{"file": name, "scale": scale, "sha256": digest}
                           for name, scale, digest in MODEL_SPECS],
            }
            if manifest != expected:
                raise PadUnavailableError("PAD manifest is incompatible")
            self.nets = []
            for name, _scale, digest in MODEL_SPECS:
                data = (path.parent / name).read_bytes()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise PadUnavailableError("PAD asset checksum mismatch")
                net = cv2.dnn.readNetFromONNX(np.frombuffer(data, dtype=np.uint8))
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.nets.append(net)
            # Warmup validates both graph shapes before serving a real capture.
            self._forward([np.zeros((1, 3, 80, 80), np.float32) for _ in MODEL_SPECS])
        except PadUnavailableError:
            raise
        except Exception as exc:
            raise PadUnavailableError("PAD models are unavailable") from exc

    def _forward(self, tensors):
        scores = []
        try:
            for net, tensor in zip(self.nets, tensors):
                try:
                    net.setInput(tensor)
                    scores.append(float(class_probabilities(net.forward())[1]))
                finally:
                    # Net keeps its last input internally. Overwrite AND run a
                    # neutral input so cached activations also contain no face.
                    net.setInput(np.zeros((1, 3, 80, 80), np.float32))
                    net.forward()
            return scores
        except Exception as exc:
            # Drop any potentially tainted native state on failure.
            self.nets.clear()
            raise PadUnavailableError("PAD inference is unavailable") from exc

    def evaluate(self, image_rgb, bbox, threshold):
        started = time.perf_counter()
        tensors = [preprocess(image_rgb, bbox, scale) for _, scale, _ in MODEL_SPECS]
        first, second = self._forward(tensors)
        score = (first + second) / 2
        return PadAnalysis(score, score >= threshold, MODEL_VERSION,
                           (time.perf_counter() - started) * 1000, first, second)


def _get_runtime(manifest_path):
    global _runtime, _runtime_path
    if _runtime is None or _runtime_path != str(manifest_path):
        _runtime = PadRuntime(manifest_path)
        _runtime_path = str(manifest_path)
    return _runtime


def initialize_pad():
    """Warm the configured models; no model download at startup or inference."""
    if settings.pad_mode != "off":
        with _lock:
            _get_runtime(settings.pad_manifest_path)


def evaluate_pad(image_rgb, face_bbox, *, threshold=None, manifest_path=None):
    global _runtime
    cutoff = settings.pad_threshold if threshold is None else threshold
    started = time.perf_counter()
    outcome = "unavailable"
    try:
        if not math.isfinite(cutoff) or not 0 <= cutoff <= 1:
            raise PadUnavailableError("PAD cutoff is invalid")
        with _lock:
            try:
                result = _get_runtime(manifest_path or settings.pad_manifest_path).evaluate(image_rgb, face_bbox, cutoff)
            except Exception as exc:
                _runtime = None
                if isinstance(exc, PadUnavailableError):
                    raise
                raise PadUnavailableError("PAD inference is unavailable") from exc
        outcome = "passed" if result.passed else "failed"
        return result
    finally:
        record_pad_outcome(outcome, time.perf_counter() - started)
