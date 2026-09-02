"""Single-image liveness and presentation-attack signal analysis.

The implementation follows the documented 30/25/25/20 weighting for depth,
mesh plausibility, texture, and colour.  MediaPipe ``FaceMesh`` instances are
thread-local because solution objects are not thread-safe.  Only aggregate
scores are returned: images, crops, landmarks, histograms, and biometric
templates never leave the request scope.

Blink and head-turn modes provide honest single-frame *proxies*.  Proving an
action happened requires a short frame sequence and a server-issued challenge;
the proxy is reported as evidence but is not allowed to silently replace the
four specified passive-liveness components.
"""

from __future__ import annotations

import math
import threading
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence


COMPONENT_WEIGHTS: dict[str, float] = {
    "depth": 0.30,
    "mesh": 0.25,
    "texture": 0.25,
    "color": 0.20,
}
SUPPORTED_CHALLENGES = frozenset({"passive", "blink", "head_turn"})
EXPECTED_LANDMARK_COUNT = 468

# Six-point Eye Aspect Ratio groups: outer corner, two upper points, inner
# corner, two lower points.  Indices are from the canonical MediaPipe mesh.
_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)
_FACE_GEOMETRY = (10, 33, 263, 1, 61, 291, 152)
_CHEEK_LANDMARKS = (50, 101, 205, 280, 330, 425)

_thread_local = threading.local()


class LivenessUnavailableError(RuntimeError):
    """Raised when the configured local liveness model cannot run."""


@dataclass(frozen=True, slots=True)
class LivenessAnalysis:
    liveness_passed: bool
    liveness_score: float
    liveness_threshold: float
    challenge_type: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _MeshSnapshot:
    landmarks: tuple[tuple[float, float, float], ...]
    landmark_count: int
    face_mesh_complete: bool
    nose_tip_z: float
    landmark_z_variance: float
    relative_nose_depth: float
    depth_quality: str
    depth_detected: bool
    depth_score: float
    mesh_score: float
    x_span: float
    y_span: float


def _dependencies() -> tuple[Any, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise LivenessUnavailableError("OpenCV and NumPy are required for liveness analysis") from exc
    return np, cv2


def _face_mesh() -> Any:
    instance = getattr(_thread_local, "face_mesh", None)
    if instance is not None:
        return instance
    try:
        import mediapipe as mp

        factory = mp.solutions.face_mesh.FaceMesh
    except (ImportError, AttributeError) as exc:
        raise LivenessUnavailableError("MediaPipe FaceMesh is unavailable") from exc
    try:
        instance = factory(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    except Exception as exc:
        raise LivenessUnavailableError("MediaPipe FaceMesh could not be initialized") from exc
    _thread_local.face_mesh = instance
    return instance


def close_thread_local_face_mesh() -> None:
    """Release the current worker thread's MediaPipe native resources."""

    instance = getattr(_thread_local, "face_mesh", None)
    if instance is not None:
        try:
            instance.close()
        finally:
            try:
                delattr(_thread_local, "face_mesh")
            except AttributeError:
                pass


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _smoothstep(low: float, high: float, value: float) -> float:
    if high <= low:
        return float(value >= high)
    x = _clamp((float(value) - low) / (high - low))
    return x * x * (3.0 - 2.0 * x)


def _round(value: Any, digits: int = 5) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return round(number, digits) if math.isfinite(number) else 0.0


def _landmark_tuple(face_landmarks: Any) -> tuple[tuple[float, float, float], ...]:
    source = getattr(face_landmarks, "landmark", face_landmarks)
    points: list[tuple[float, float, float]] = []
    try:
        for point in source:
            if hasattr(point, "x") and hasattr(point, "y"):
                x = float(point.x)
                y = float(point.y)
                z = float(getattr(point, "z", 0.0))
            else:
                x = float(point[0])
                y = float(point[1])
                z = float(point[2]) if len(point) > 2 else 0.0
            points.append((x, y, z))
    except (TypeError, ValueError, IndexError, AttributeError):
        return ()
    return tuple(points)


def _extract_landmarks(image_rgb: Any) -> tuple[tuple[float, float, float], ...]:
    np, _cv2 = _dependencies()
    image = np.asarray(image_rgb)
    if image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
        raise ValueError("Liveness image must be a non-empty RGB array")
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8, copy=False)
    try:
        result = _face_mesh().process(image)
    except Exception as exc:
        raise LivenessUnavailableError("MediaPipe FaceMesh processing failed") from exc
    detected = getattr(result, "multi_face_landmarks", None)
    if not detected:
        return ()
    return _landmark_tuple(detected[0])


def _distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))


def _geometry_score(landmarks: Sequence[Sequence[float]]) -> float:
    if len(landmarks) <= max(_FACE_GEOMETRY):
        return 0.0
    forehead, left_eye, right_eye, nose, left_mouth, right_mouth, chin = (
        landmarks[index] for index in _FACE_GEOMETRY
    )
    interocular = _distance(left_eye, right_eye)
    face_height = _distance(forehead, chin)
    mouth_width = _distance(left_mouth, right_mouth)
    eye_min_x, eye_max_x = sorted((left_eye[0], right_eye[0]))
    mouth_y = (left_mouth[1] + right_mouth[1]) / 2.0

    checks = (
        _smoothstep(0.06, 0.18, interocular),
        _smoothstep(0.16, 0.42, face_height),
        _smoothstep(0.04, 0.15, mouth_width),
        float(eye_min_x < nose[0] < eye_max_x),
        float(forehead[1] < nose[1] < mouth_y < chin[1]),
    )
    return sum(checks) / len(checks)


def _mesh_snapshot(landmarks: tuple[tuple[float, float, float], ...]) -> _MeshSnapshot:
    np, _cv2 = _dependencies()
    count = len(landmarks)
    if not landmarks:
        return _MeshSnapshot((), 0, False, 0.0, 0.0, 0.0, "poor", False, 0.0, 0.0, 0.0, 0.0)

    coordinates = np.asarray(landmarks, dtype=np.float64)
    finite_rows = np.isfinite(coordinates).all(axis=1)
    finite_fraction = float(np.mean(finite_rows))
    if not finite_rows.any():
        return _MeshSnapshot(landmarks, count, False, 0.0, 0.0, 0.0, "poor", False, 0.0, 0.0, 0.0, 0.0)

    valid = coordinates[finite_rows]
    x_span = float(np.ptp(valid[:, 0]))
    y_span = float(np.ptp(valid[:, 1]))
    in_bounds = float(np.mean((valid[:, 0] >= -0.2) & (valid[:, 0] <= 1.2) & (valid[:, 1] >= -0.2) & (valid[:, 1] <= 1.2)))
    span_score = (
        _smoothstep(0.10, 0.24, x_span)
        * _smoothstep(0.12, 0.30, y_span)
        * (1.0 - 0.7 * _smoothstep(0.95, 1.4, max(x_span, y_span)))
    )
    completeness_score = _clamp(count / EXPECTED_LANDMARK_COUNT)
    geometry_score = _geometry_score(landmarks)
    mesh_score = _clamp(
        0.35 * completeness_score
        + 0.15 * finite_fraction
        + 0.15 * in_bounds
        + 0.15 * span_score
        + 0.20 * geometry_score
    )

    nose_z = float(coordinates[1, 2]) if count > 1 and np.isfinite(coordinates[1, 2]) else 0.0
    z_values = valid[:, 2]
    z_variance = float(np.var(z_values))
    z_std = math.sqrt(max(0.0, z_variance))
    cheek_z = [landmarks[index][2] for index in _CHEEK_LANDMARKS if index < count and math.isfinite(landmarks[index][2])]
    relative_nose_depth = float(abs(float(np.median(cheek_z)) - nose_z)) if cheek_z else abs(nose_z)

    absolute_nose = abs(nose_z)
    if absolute_nose > 0.03:
        depth_quality = "good"
    elif absolute_nose > 0.01:
        depth_quality = "moderate"
    else:
        depth_quality = "poor"
    nose_score = _smoothstep(0.008, 0.05, absolute_nose)
    variance_score = _smoothstep(0.006, 0.03, z_std)
    relative_score = _smoothstep(0.008, 0.055, relative_nose_depth)
    depth_score = _clamp(0.50 * nose_score + 0.30 * variance_score + 0.20 * relative_score)
    depth_detected = absolute_nose > 0.01 and z_std > 0.005

    complete = count >= EXPECTED_LANDMARK_COUNT and finite_fraction >= 0.99 and mesh_score >= 0.70
    return _MeshSnapshot(
        landmarks=landmarks,
        landmark_count=count,
        face_mesh_complete=complete,
        nose_tip_z=nose_z,
        landmark_z_variance=z_variance,
        relative_nose_depth=relative_nose_depth,
        depth_quality=depth_quality,
        depth_detected=depth_detected,
        depth_score=depth_score,
        mesh_score=mesh_score,
        x_span=x_span,
        y_span=y_span,
    )


def analyze_face_mesh(image_rgb: Any) -> dict[str, Any]:
    """Skeleton-compatible aggregate FaceMesh analysis (never raw landmarks)."""

    snapshot = _mesh_snapshot(_extract_landmarks(image_rgb))
    return {
        "face_mesh_complete": snapshot.face_mesh_complete,
        "landmark_count": snapshot.landmark_count,
        "nose_tip_z": _round(snapshot.nose_tip_z),
        "landmark_z_variance": _round(snapshot.landmark_z_variance, 7),
        "relative_nose_depth": _round(snapshot.relative_nose_depth),
        "depth_quality": snapshot.depth_quality,
        "depth_detected": snapshot.depth_detected,
        "depth_score": _round(snapshot.depth_score),
        "mesh_plausibility_score": _round(snapshot.mesh_score),
    }


def _resolve_bbox(face_bbox: Any) -> tuple[int, int, int, int] | None:
    if face_bbox is None:
        return None
    candidate = getattr(face_bbox, "bbox", face_bbox)
    if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)) or len(candidate) != 4:
        return None
    try:
        x, y, width, height = (int(round(float(value))) for value in candidate)
    except (TypeError, ValueError, OverflowError):
        return None
    return (x, y, width, height) if width > 0 and height > 0 else None


def _face_crop(image_rgb: Any, bbox: Any, landmarks: Sequence[Sequence[float]]) -> Any:
    np, _cv2 = _dependencies()
    image = np.asarray(image_rgb)
    image_height, image_width = image.shape[:2]
    resolved = _resolve_bbox(bbox)
    if resolved is None and landmarks:
        xs = [point[0] for point in landmarks if math.isfinite(point[0])]
        ys = [point[1] for point in landmarks if math.isfinite(point[1])]
        if xs and ys:
            left = int(math.floor(min(xs) * image_width))
            top = int(math.floor(min(ys) * image_height))
            right = int(math.ceil(max(xs) * image_width))
            bottom = int(math.ceil(max(ys) * image_height))
            resolved = (left, top, right - left, bottom - top)
    if resolved is None:
        return image

    x, y, width, height = resolved
    margin_x = max(2, int(width * 0.06))
    margin_y = max(2, int(height * 0.06))
    left = max(0, x - margin_x)
    top = max(0, y - margin_y)
    right = min(image_width, x + width + margin_x)
    bottom = min(image_height, y + height + margin_y)
    if right - left < 8 or bottom - top < 8:
        return image
    return image[top:bottom, left:right]


def _standard_gray(face_crop: Any) -> tuple[Any, Any]:
    np, cv2 = _dependencies()
    crop = np.asarray(face_crop)
    if crop.ndim != 3 or crop.shape[2] != 3 or crop.size == 0:
        raise ValueError("Face crop must be a non-empty RGB array")
    height, width = crop.shape[:2]
    scale = min(1.0, 256.0 / max(height, width))
    if scale < 1.0:
        crop = cv2.resize(crop, (max(8, int(width * scale)), max(8, int(height * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    return crop, gray


def _fft_naturalness(gray: Any) -> tuple[float, float, float, float]:
    np, cv2 = _dependencies()
    analysis = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA).astype(np.float64) / 255.0
    analysis -= float(np.mean(analysis))
    signal_energy = float(np.mean(analysis * analysis))
    if signal_energy < 1e-6:
        return 0.0, 0.0, 1.0, 0.0

    window = np.outer(np.hanning(analysis.shape[0]), np.hanning(analysis.shape[1]))
    power = np.abs(np.fft.fftshift(np.fft.fft2(analysis * window))) ** 2
    yy, xx = np.ogrid[-1.0:1.0:complex(analysis.shape[0]), -1.0:1.0:complex(analysis.shape[1])]
    radius = np.sqrt(xx * xx + yy * yy)
    non_dc = radius > 0.04
    high_mask = (radius >= 0.20) & (radius <= 0.85)
    total_energy = float(np.sum(power[non_dc])) + 1e-12
    high_values = power[high_mask]
    high_energy = float(np.sum(high_values))
    high_ratio = high_energy / total_energy
    if high_energy <= 1e-12 or high_values.size == 0:
        return 0.0, high_ratio, 1.0, 0.0

    top_count = max(1, int(high_values.size * 0.002))
    top_concentration = float(np.sum(np.partition(high_values, -top_count)[-top_count:]) / (high_energy + 1e-12))
    peak_to_mean = float(np.percentile(high_values, 99.9) / (np.mean(high_values) + 1e-12))
    detail_score = _smoothstep(0.006, 0.09, high_ratio)
    periodic_penalty = max(
        _smoothstep(0.12, 0.42, top_concentration),
        _smoothstep(35.0, 150.0, peak_to_mean),
    )
    naturalness = _clamp(detail_score * (1.0 - 0.85 * periodic_penalty))
    return naturalness, high_ratio, top_concentration, peak_to_mean


def _periodic_artifact_penalty(
    peak_concentration: float,
    peak_to_mean: float,
) -> float:
    """Return a bounded screen/halftone periodicity penalty.

    A flat presentation attack can still receive plausible FaceMesh depth
    because MediaPipe infers three-dimensional geometry from any facial image.
    Concentrated FFT peaks are therefore treated as a presentation-integrity
    signal in addition to their contribution to the texture component.
    """

    return _clamp(
        max(
            _smoothstep(0.12, 0.42, peak_concentration),
            _smoothstep(35.0, 150.0, peak_to_mean),
        )
    )


def _lbp_naturalness(gray: Any) -> tuple[float, float, float]:
    np, _cv2 = _dependencies()
    if min(gray.shape[:2]) < 3:
        return 0.0, 0.0, 1.0
    center = gray[1:-1, 1:-1]
    neighbours = (
        gray[:-2, :-2],
        gray[:-2, 1:-1],
        gray[:-2, 2:],
        gray[1:-1, 2:],
        gray[2:, 2:],
        gray[2:, 1:-1],
        gray[2:, :-2],
        gray[1:-1, :-2],
    )
    codes = np.zeros(center.shape, dtype=np.uint8)
    for bit, neighbour in enumerate(neighbours):
        codes |= ((neighbour >= center).astype(np.uint8) << bit)
    histogram = np.bincount(codes.ravel(), minlength=256).astype(np.float64)
    histogram /= max(1.0, float(histogram.sum()))
    nonzero = histogram[histogram > 0]
    entropy = float(-np.sum(nonzero * np.log2(nonzero)))
    peak_fraction = float(np.max(histogram))
    entropy_score = _smoothstep(2.0, 5.8, entropy)
    concentration_score = 1.0 - _smoothstep(0.28, 0.72, peak_fraction)
    return _clamp(0.7 * entropy_score + 0.3 * concentration_score), entropy, peak_fraction


def analyze_texture(face_crop: Any) -> tuple[float, dict[str, float]]:
    """Score blur, periodic screen artefacts, and local texture diversity."""

    np, cv2 = _dependencies()
    _crop, gray = _standard_gray(face_crop)
    laplacian_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    gray_std = float(np.std(gray))
    sharpness = _smoothstep(14.0, 130.0, laplacian_variance)
    # Extreme high-frequency energy is usually sensor noise, sharpening, or a
    # display pixel grid rather than natural facial detail.
    sharpness *= 1.0 - 0.55 * _smoothstep(2_500.0, 8_000.0, laplacian_variance)
    variance_gate = _smoothstep(3.0, 26.0, gray_std)
    fft_score, high_ratio, concentration, peak_to_mean = _fft_naturalness(gray)
    lbp_score, lbp_entropy, lbp_peak = _lbp_naturalness(gray)
    periodic_penalty = _periodic_artifact_penalty(concentration, peak_to_mean)
    texture_score = _clamp(variance_gate * (0.45 * sharpness + 0.30 * fft_score + 0.25 * lbp_score))
    return texture_score, {
        "laplacian_variance": _round(laplacian_variance, 3),
        "sharpness_score": _round(sharpness),
        "luma_variance_score": _round(variance_gate),
        "fft_naturalness_score": _round(fft_score),
        "fft_high_frequency_ratio": _round(high_ratio),
        "fft_peak_concentration": _round(concentration),
        "fft_peak_to_mean": _round(peak_to_mean, 3),
        "periodic_artifact_penalty": _round(periodic_penalty),
        "lbp_naturalness_score": _round(lbp_score),
        "lbp_entropy": _round(lbp_entropy, 3),
        "lbp_peak_fraction": _round(lbp_peak),
    }


def analyze_color(face_crop: Any) -> tuple[float, dict[str, float]]:
    """Score natural face-region luminance/chroma variation without skin identity."""

    np, cv2 = _dependencies()
    crop, _gray = _standard_gray(face_crop)
    analysis = cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA)
    ycrcb = cv2.cvtColor(analysis, cv2.COLOR_RGB2YCrCb).astype(np.float64)
    y_channel, cr_channel, cb_channel = (ycrcb[:, :, index] for index in range(3))
    channel_std = np.std(analysis.astype(np.float64), axis=(0, 1))
    channel_spread = float(np.mean(channel_std))
    luma_std = float(np.std(y_channel))
    chroma_std = float(math.hypot(float(np.std(cr_channel)), float(np.std(cb_channel))))

    # Broad YCbCr bounds cover diverse skin tones; this is only a weak colour
    # plausibility cue and therefore cannot decide liveness on its own.
    skin_mask = (
        (cr_channel >= 115)
        & (cr_channel <= 190)
        & (cb_channel >= 65)
        & (cb_channel <= 150)
        & (y_channel >= 20)
    )
    skin_fraction = float(np.mean(skin_mask))
    clipped_fraction = float(np.mean((analysis <= 2) | (analysis >= 253)))

    chroma_score = _smoothstep(1.5, 13.0, chroma_std)
    spread_score = _smoothstep(7.0, 34.0, channel_spread)
    luma_score = _smoothstep(8.0, 35.0, luma_std)
    skin_score = _smoothstep(0.04, 0.30, skin_fraction)
    gamut_score = 1.0 - _smoothstep(0.08, 0.35, clipped_fraction)
    color_score = _clamp(
        0.35 * chroma_score
        + 0.25 * spread_score
        + 0.15 * luma_score
        + 0.15 * skin_score
        + 0.10 * gamut_score
    )
    return color_score, {
        "chroma_variance_score": _round(chroma_score),
        "channel_spread_score": _round(spread_score),
        "luminance_variance_score": _round(luma_score),
        "skin_chroma_fraction": _round(skin_fraction),
        "gamut_score": _round(gamut_score),
    }


def _eye_aspect_ratio(landmarks: Sequence[Sequence[float]], indices: Sequence[int]) -> float:
    if len(landmarks) <= max(indices):
        return 0.0
    points = [landmarks[index] for index in indices]
    horizontal = 2.0 * _distance(points[0], points[3])
    if horizontal <= 1e-9:
        return 0.0
    return (_distance(points[1], points[5]) + _distance(points[2], points[4])) / horizontal


def blink_metrics(face_mesh_landmarks: Any) -> dict[str, Any]:
    landmarks = _landmark_tuple(face_mesh_landmarks)
    if not landmarks and isinstance(face_mesh_landmarks, tuple):
        landmarks = face_mesh_landmarks
    left = _eye_aspect_ratio(landmarks, _LEFT_EYE)
    right = _eye_aspect_ratio(landmarks, _RIGHT_EYE)
    average = (left + right) / 2.0
    detected = 0.0 < average < 0.19
    return {
        "blink_detected": detected,
        "eye_aspect_ratio": _round(average),
        "challenge_score": 1.0 if detected else 0.25,
    }


def detect_blink(face_mesh_landmarks: Any) -> bool:
    """Skeleton-compatible single-frame closed-eye proxy."""

    return bool(blink_metrics(face_mesh_landmarks)["blink_detected"])


def head_turn_metrics(face_mesh_landmarks: Any) -> dict[str, Any]:
    landmarks = _landmark_tuple(face_mesh_landmarks)
    if not landmarks and isinstance(face_mesh_landmarks, tuple):
        landmarks = face_mesh_landmarks
    if len(landmarks) <= 263:
        return {"head_turn_detected": False, "yaw_asymmetry": 0.0, "challenge_score": 0.0}
    nose = landmarks[1]
    left_distance = _distance(nose, landmarks[33])
    right_distance = _distance(nose, landmarks[263])
    denominator = left_distance + right_distance
    asymmetry = (right_distance - left_distance) / denominator if denominator > 1e-9 else 0.0
    absolute = abs(asymmetry)
    detected = absolute >= 0.12
    return {
        "head_turn_detected": detected,
        "yaw_asymmetry": _round(asymmetry),
        "challenge_score": _round(_smoothstep(0.06, 0.24, absolute)),
    }


def detect_head_turn(face_mesh_landmarks: Any) -> bool:
    return bool(head_turn_metrics(face_mesh_landmarks)["head_turn_detected"])


def assess_liveness(
    image_rgb: Any,
    face_detection_confidence: float = 0.0,
    face_bbox: Any = None,
    challenge_type: str = "passive",
    threshold: float = 0.60,
) -> LivenessAnalysis:
    """Analyze one detected face and return aggregate liveness evidence."""

    if challenge_type not in SUPPORTED_CHALLENGES:
        raise ValueError(f"Unsupported challenge type: {challenge_type}")
    threshold = _clamp(threshold)
    try:
        confidence = _clamp(float(face_detection_confidence))
    except (TypeError, ValueError, OverflowError):
        confidence = 0.0

    landmarks = _extract_landmarks(image_rgb)
    snapshot = _mesh_snapshot(landmarks)
    if not landmarks:
        details = {
            "face_detection_confidence": _round(confidence),
            "face_mesh_complete": False,
            "landmark_count": 0,
            "depth_detected": False,
            "depth_quality": "poor",
            "depth_score": 0.0,
            "mesh_plausibility_score": 0.0,
            "texture_analysis_score": 0.0,
            "color_distribution_score": 0.0,
            "challenge_evidence_score": 0.0,
            "challenge_integrity_score": 0.0,
            "single_image_challenge_proxy": challenge_type != "passive",
            "threshold": _round(threshold),
        }
        return LivenessAnalysis(False, 0.0, threshold, challenge_type, details)

    crop = _face_crop(image_rgb, face_bbox, landmarks)
    texture_score, texture_details = analyze_texture(crop)
    color_score, color_details = analyze_color(crop)

    if challenge_type == "blink":
        challenge_details = blink_metrics(landmarks)
    elif challenge_type == "head_turn":
        challenge_details = head_turn_metrics(landmarks)
    else:
        challenge_details = {"challenge_score": 1.0}

    weighted = {
        "depth": COMPONENT_WEIGHTS["depth"] * snapshot.depth_score,
        "mesh": COMPONENT_WEIGHTS["mesh"] * snapshot.mesh_score,
        "texture": COMPONENT_WEIGHTS["texture"] * texture_score,
        "color": COMPONENT_WEIGHTS["color"] * color_score,
    }
    component_score = _clamp(sum(weighted.values()))

    # FaceMesh depth is model-inferred and remains convincing for a flat photo.
    # Preserve the documented weighted score, then require the presentation
    # itself to have plausible non-periodic texture and colour diversity.  A
    # soft floor avoids turning any single noisy heuristic into an absolute
    # decision while still allowing strong screen/print artefacts to veto the
    # otherwise optimistic pseudo-depth signal.
    periodic_penalty = _clamp(
        float(texture_details.get("periodic_artifact_penalty", 0.0))
    )
    presentation_checks = {
        "periodicity": 1.0 - 0.60 * periodic_penalty,
        "texture_diversity": 0.45 + 0.55 * texture_score,
        "color_diversity": 0.45 + 0.55 * color_score,
    }
    presentation_integrity = _clamp(min(presentation_checks.values()))
    challenge_evidence = _clamp(
        float(challenge_details.get("challenge_score", 0.0))
    )
    challenge_integrity = (
        1.0
        if challenge_type == "passive"
        else 0.40 + 0.60 * challenge_evidence
    )
    score = _clamp(
        component_score * presentation_integrity * challenge_integrity
    )
    score = round(score, 6)
    passed = score >= threshold

    details = {
        "face_detection_confidence": _round(confidence),
        "face_mesh_complete": snapshot.face_mesh_complete,
        "landmark_count": snapshot.landmark_count,
        "nose_tip_z": _round(snapshot.nose_tip_z),
        "landmark_z_variance": _round(snapshot.landmark_z_variance, 7),
        "relative_nose_depth": _round(snapshot.relative_nose_depth),
        "depth_detected": snapshot.depth_detected,
        "depth_quality": snapshot.depth_quality,
        "depth_score": _round(snapshot.depth_score),
        "mesh_plausibility_score": _round(snapshot.mesh_score),
        "texture_analysis_score": _round(texture_score),
        "color_distribution_score": _round(color_score),
        "weighted_contributions": {name: _round(value, 6) for name, value in weighted.items()},
        "component_weights": dict(COMPONENT_WEIGHTS),
        "weighted_component_score": _round(component_score, 6),
        "presentation_integrity_score": _round(presentation_integrity, 6),
        "presentation_integrity_checks": {
            name: _round(value, 6) for name, value in presentation_checks.items()
        },
        "texture_signals": texture_details,
        "color_signals": color_details,
        "challenge_evidence_score": _round(challenge_evidence),
        "challenge_integrity_score": _round(challenge_integrity),
        "single_image_challenge_proxy": challenge_type != "passive",
        "threshold": _round(threshold),
    }
    details.update({key: value for key, value in challenge_details.items() if key != "challenge_score"})

    # Explicitly discard request-scoped views/references before returning the
    # scalar result.  Python/NumPy may retain allocator pages, but no application
    # object caches or persists the biometric material.
    del crop
    del landmarks
    return LivenessAnalysis(passed, score, threshold, challenge_type, details)


# Readable compatibility alias for route wiring and external tests.
analyze_liveness = assess_liveness


__all__ = [
    "COMPONENT_WEIGHTS",
    "LivenessAnalysis",
    "LivenessUnavailableError",
    "SUPPORTED_CHALLENGES",
    "analyze_color",
    "analyze_face_mesh",
    "analyze_liveness",
    "analyze_texture",
    "assess_liveness",
    "blink_metrics",
    "close_thread_local_face_mesh",
    "detect_blink",
    "detect_head_turn",
    "head_turn_metrics",
]
