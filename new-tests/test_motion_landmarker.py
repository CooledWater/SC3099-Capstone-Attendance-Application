"""Sequence model parity, fail-closed setup, and tracking rejection cases."""
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as N

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'module3-face-recognition' / 'app'
spec = importlib.util.spec_from_file_location('landmarker_test_face_app', APP / '__init__.py', submodule_search_locations=[str(APP)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from landmarker_test_face_app import motion


def test_server_and_browser_bundle_the_same_pinned_model():
    browser = ROOT / 'module1-frontend/public/mediapipe/face_landmarker.task'
    assert hashlib.sha256(browser.read_bytes()).hexdigest() == motion.LANDMARKER_SHA256
    assert motion.LANDMARKER_MODEL.read_bytes() == browser.read_bytes()


@pytest.mark.parametrize('corrupt', [False, True])
def test_missing_or_corrupt_model_fails_closed(monkeypatch, tmp_path, corrupt):
    model = tmp_path / 'face_landmarker.task'
    if corrupt:
        model.write_bytes(b'not the pinned model')
    monkeypatch.setattr(motion, 'LANDMARKER_MODEL', model)
    with pytest.raises(motion.LivenessUnavailableError, match='Sequence landmark model is unavailable'):
        motion._create_landmarker()


@pytest.mark.parametrize('failure', ['no_face', 'multiple_faces', 'jump', 'inference'])
def test_tracking_failures_cannot_produce_a_proof(monkeypatch, failure):
    calls = []
    closed = []
    class Tracker:
        def __enter__(self):
            self.index = -1
            return self
        def __exit__(self, *args):
            closed.append(True)
        def detect_for_video(self, image, timestamp):
            self.index += 1
            assert timestamp == self.index * 80
            assert image.shape == (40, 80, 3)
            if self.index == 3 and failure == 'inference':
                raise RuntimeError('native failure containing no exported payload')
            face = [N(x=.5, y=.5, z=0)] * 478
            if self.index == 3 and failure == 'jump':
                face[1] = N(x=.8, y=.5, z=0)
            faces = [face]
            if self.index == 3 and failure == 'no_face':
                faces = []
            if self.index == 3 and failure == 'multiple_faces':
                faces = [face, face]
            return N(face_landmarks=faces)
    mp = N(Image=lambda **kwargs: kwargs['data'], ImageFormat=N(SRGB='RGB'))
    monkeypatch.setattr(motion, '_create_landmarker', lambda: (mp, Tracker()))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *a, **k: np.zeros((40, 80, 3), dtype=np.uint8))
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {'eye_aspect_ratio': .3})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99, bbox=(0, 0, 80, 40)))
    monkeypatch.setattr(motion, 'assess_liveness', lambda *a: N(liveness_score=.95, liveness_passed=True))
    request = motion.SequenceRequest(frames=[{'image': 'aGVsbG8=', 'timestamp_ms': i*80} for i in range(20)], reference_template_hash='a'*64)
    def verify(*args):
        calls.append(args)
        return N(match_score=.98, match_passed=True), ''
    if failure == 'inference':
        with pytest.raises(motion.LivenessUnavailableError, match='processing is unavailable'):
            motion.analyze_sequence(request, verify)
    else:
        result = motion.analyze_sequence(request, verify)
        assert result['passed'] is False
        assert result['blink_count'] == 0
    assert len(calls) == 1
    assert closed == [True]
