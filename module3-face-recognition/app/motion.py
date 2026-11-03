"""Bounded temporal motion analysis; pixels and landmarks stay request-local."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .imaging import decode_base64_image
from .liveness import blink_metrics, assess_liveness
from .config import settings, SIMHASH_BITS
from .detection import detect_face
from .liveness import LivenessUnavailableError
from .template import hamming_distance
from .random_motion import ChallengeSpec, MotionProgress, yaw_degrees
from pathlib import Path
import hashlib
import time


LANDMARKER_MODEL = Path(__file__).resolve().parent / 'assets' / 'face_landmarker.task'
LANDMARKER_SHA256 = '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'


def _create_landmarker():
    """Use M1's pinned eye model; never download or substitute another model."""
    try:
        model_bytes = LANDMARKER_MODEL.read_bytes()
        if hashlib.sha256(model_bytes).hexdigest() != LANDMARKER_SHA256:
            raise LivenessUnavailableError('Sequence landmark model is unavailable')
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=2,
            min_face_detection_confidence=.5,
            min_face_presence_confidence=.5,
            min_tracking_confidence=.5,
            output_facial_transformation_matrixes=True,
        )
        return mp, vision.FaceLandmarker.create_from_options(options)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise LivenessUnavailableError('Sequence landmark model is unavailable') from exc


class Frame(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image: str = Field(min_length=1, max_length=100_000)
    timestamp_ms: int = Field(ge=0, le=8000, strict=True)


class SequenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    frames: list[Frame] = Field(min_length=15, max_length=120)
    reference_template_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    # Missing spec retains the internal v1 contract; M2 always requires v2.
    challenge: ChallengeSpec | None = None

    @model_validator(mode='after')
    def validate_frames(self):
        times = [f.timestamp_ms for f in self.frames]
        if sum(len(f.image) for f in self.frames) > 6_000_000:
            raise ValueError('Sequence exceeds total image budget')
        if times[0] > 250 or times[-1]-times[0] < 1000:
            raise ValueError('Incomplete capture')
        if any(not 0 < b-a <= 250 for a,b in zip(times, times[1:])):
            raise ValueError('Invalid frame ordering or capture gaps')
        return self


class BlinkCounter:
    """Require an open baseline and complete closure/reopening with hysteresis."""
    def __init__(self):
        self.open = False
        self.closed_at = None
        self.count = 0

    def update(self, ear, timestamp):
        if ear >= .23:
            if self.closed_at is not None and 40 <= timestamp-self.closed_at <= 700:
                self.count += 1
            self.closed_at = None
            self.open = True
        elif ear < .19 and self.open:
            self.closed_at = timestamp
            self.open = False
        return self.count


def analyze_sequence(request, verify_image, observe=None):
    started = time.monotonic()
    counter = BlinkCounter()
    progress = MotionProgress(request.challenge, counter) if request.challenge is not None else None
    matches = []
    passive_scores = []
    previous = None
    def note(stage, **values):
        if observe is not None:
            try:
                observe(stage, **values)
            except Exception:
                # A broken diagnostic observer must not change verification.
                pass
    def result(passed=False, reason="passed"):
        note("finished", reason=reason)
        if progress:
            note('actions', challenge_version=2, completed_steps=progress.step, turn_passed=progress.turn_passed)
        return {**({'challenge_version': 2, 'turn_passed': progress.turn_passed,
                    'completed_steps': progress.step} if progress else {}),
                'passed': passed, 'blink_count': counter.count,
                'liveness_score': min(passive_scores, default=0.0),
                'face_match_score': min(matches, default=0.0)}
    note("started", frame_count=len(request.frames),
         duration_ms=request.frames[-1].timestamp_ms-request.frames[0].timestamp_ms,
         liveness_threshold=settings.liveness_threshold,
         face_match_threshold=settings.face_match_threshold)
    # A fresh tracker per request avoids mixing students or timestamp histories.
    mp, detector = _create_landmarker()
    with detector as landmarker:
        for index, frame in enumerate(request.frames):
            if time.monotonic()-started > 40:
                raise LivenessUnavailableError("Sequence processing timed out")
            image = decode_base64_image(frame.image, max_dimension=640)
            note("frame", last_frame_index=index, last_timestamp_ms=frame.timestamp_ms)
            try:
                output = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=image),
                    frame.timestamp_ms,
                )
            except (RuntimeError, ValueError) as exc:
                raise LivenessUnavailableError('Sequence landmark processing is unavailable') from exc
            faces = output.face_landmarks or []
            if len(faces) != 1:
                return result(reason="face_count")
            landmarks = faces[0]
            nose = landmarks[1]
            if previous and ((nose.x-previous[0])**2+(nose.y-previous[1])**2)**.5 > .15:
                return result(reason="face_jump")
            previous = (nose.x, nose.y)
            # EAR uses pixel aspect ratio, matching the browser implementation.
            h, w = image.shape[:2]
            points = tuple((p.x*w, p.y*h, p.z*w) for p in landmarks)
            before = counter.count
            before_step = progress.step if progress else 0
            ear = blink_metrics(points)['eye_aspect_ratio']
            if progress:
                matrices = getattr(output, 'facial_transformation_matrixes', None)
                try:
                    if matrices is None or len(matrices) != 1:
                        raise ValueError('Pose output missing')
                    yaw = yaw_degrees(matrices[0])
                except ValueError as exc:
                    raise LivenessUnavailableError('Face pose is unavailable') from exc
                progress.update(ear, yaw, frame.timestamp_ms)
                if progress.reason:
                    return result(reason=progress.reason)
            else:
                counter.update(ear, frame.timestamp_ms)
            # Sample identity regularly and at blink completion, including final frame.
            if (index % 8 == 0 or counter.count != before or index == len(request.frames)-1
                    or (progress and progress.step != before_step)):
                match, _ = verify_image(frame.image, request.reference_template_hash)
                matches.append(match.match_score)
                identity = {}
                if observe is not None:
                    try:
                        identity = {'frame_index': index, 'timestamp_ms': frame.timestamp_ms,
                                    'match_score': match.match_score, 'match_passed': match.match_passed,
                                    'face_detected': getattr(match, 'face_detected', None),
                                    'hamming_evaluated': False}
                        # Reuse the compared request-local templates; no extra face inference.
                        distance = hamming_distance(request.reference_template_hash,
                                                    getattr(match, 'current_template_hash', ''))
                        identity.update(hamming_evaluated=True, hamming_distance=distance,
                                        hamming_fraction=distance / SIMHASH_BITS)
                    except Exception:
                        # Missing/no-face templates or failed diagnostics cannot change the verdict.
                        pass
                note("identity", **identity)
                if not match.match_passed:
                    return result(reason="identity_failed")
            if index == 0 or index == len(request.frames)-1:
                detection = detect_face(image)
                passive = assess_liveness(image, detection.confidence, detection.bbox,
                                          'passive', settings.liveness_threshold)
                passive_scores.append(passive.liveness_score)
                if observe is not None:
                    note("passive", position="first_frame" if index == 0 else "last_frame",
                         frame_index=index, timestamp_ms=frame.timestamp_ms,
                         liveness_passed=passive.liveness_passed, liveness_score=passive.liveness_score,
                         liveness_threshold=getattr(passive, "liveness_threshold", settings.liveness_threshold),
                         details=getattr(passive, "details", {}))
                if not passive.liveness_passed:
                    return result(reason="passive_first_failed" if index == 0 else "passive_last_failed")
    motion_passed = progress.complete if progress else (counter.count >= 2 and counter.open and counter.closed_at is None)
    passed = motion_passed and min(matches, default=0) >= settings.face_match_threshold
    if passed:
        reason = 'passed'
    elif progress:
        reason = progress.failure_reason() if not motion_passed else 'identity_threshold'
    elif counter.count < 2:
        reason = 'insufficient_blinks'
    elif not counter.open or counter.closed_at is not None:
        reason = 'incomplete_blink'
    else:
        reason = 'identity_threshold'
    return result(passed, reason)
