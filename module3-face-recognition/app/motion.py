"""Bounded blink-sequence analysis; pixels and landmarks stay request-local."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .imaging import decode_base64_image
from .liveness import blink_metrics, assess_liveness
from .config import settings
from .detection import detect_face
from .liveness import LivenessUnavailableError
import time


class Frame(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image: str = Field(min_length=1, max_length=100_000)
    timestamp_ms: int = Field(ge=0, le=8000, strict=True)


class SequenceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    frames: list[Frame] = Field(min_length=15, max_length=120)
    reference_template_hash: str = Field(pattern=r'^[0-9a-f]{64}$')

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


def analyze_sequence(request, verify_image):
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise LivenessUnavailableError("MediaPipe unavailable") from exc
    started = time.monotonic()
    counter = BlinkCounter()
    matches = []
    passive_scores = []
    previous = None
    def result(passed=False):
        return {'passed': passed, 'blink_count': counter.count,
                'liveness_score': min(passive_scores, default=0.0),
                'face_match_score': min(matches, default=0.0)}
    # A fresh tracker per request avoids mixing different students' sequences.
    with mp.solutions.face_mesh.FaceMesh(static_image_mode=False, max_num_faces=2,
            refine_landmarks=False, min_detection_confidence=.5, min_tracking_confidence=.5) as mesh:
        for index, frame in enumerate(request.frames):
            if time.monotonic()-started > 40:
                raise LivenessUnavailableError("Sequence processing timed out")
            image = decode_base64_image(frame.image, max_dimension=640)
            output = mesh.process(image)
            faces = output.multi_face_landmarks or []
            if len(faces) != 1:
                return result()
            landmarks = faces[0].landmark
            nose = landmarks[1]
            if previous and ((nose.x-previous[0])**2+(nose.y-previous[1])**2)**.5 > .15:
                return result()
            previous = (nose.x, nose.y)
            # EAR uses pixel aspect ratio, matching the browser implementation.
            h, w = image.shape[:2]
            points = tuple((p.x*w, p.y*h, p.z*w) for p in landmarks)
            before = counter.count
            counter.update(blink_metrics(points)['eye_aspect_ratio'], frame.timestamp_ms)
            # Sample identity regularly and at blink completion, including final frame.
            if index % 8 == 0 or counter.count != before or index == len(request.frames)-1:
                match, _ = verify_image(frame.image, request.reference_template_hash)
                matches.append(match.match_score)
                if not match.match_passed:
                    return result()
            if index == 0 or index == len(request.frames)-1:
                detection = detect_face(image)
                passive = assess_liveness(image, detection.confidence, detection.bbox, 'passive')
                passive_scores.append(passive.liveness_score)
                if not passive.liveness_passed:
                    return result()
    return result(counter.count >= 2 and counter.open and counter.closed_at is None
                  and min(matches, default=0) >= settings.face_match_threshold)
