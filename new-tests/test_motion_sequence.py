"""Temporal logic tests independent of native face-model availability."""
import importlib.util
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1] / 'module3-face-recognition' / 'app'
spec = importlib.util.spec_from_file_location('motion_test_face_app', ROOT/'__init__.py', submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from motion_test_face_app.motion import BlinkCounter, SequenceRequest

@pytest.mark.parametrize('samples,expected', [
    ([.3,.1,.3,.3,.1,.3], 2),
    ([.3,.1,.1,.1,.3], 1),
    ([.1,.1,.3], 0),
    ([.3,.3,.3,.3], 0),
    ([.3,.2,.21,.22,.3], 0),
    ([.3]+[.1]*10+[.3], 0),
])
def test_complete_blinks_only(samples, expected):
    counter = BlinkCounter()
    for i, ear in enumerate(samples): counter.update(ear, i*80)
    assert counter.count == expected

@pytest.mark.parametrize('times', [[0]*20, list(range(0,6000,300)), list(range(0,20)), list(range(300,1900,80))])
def test_sequence_rejects_gaps_duplicates_and_short_capture(times):
    with pytest.raises(ValueError):
        SequenceRequest(frames=[{'image':'aGVsbG8=', 'timestamp_ms':t} for t in times], reference_template_hash='a'*64)

def test_bounded_sequence_contract():
    request = SequenceRequest(frames=[{'image':'aGVsbG8=', 'timestamp_ms':i*80} for i in range(20)], reference_template_hash='a'*64)
    assert len(request.frames) == 20

@pytest.mark.parametrize('failure', [None, 'multiple_faces', 'identity', 'passive'])
def test_sequence_combines_motion_identity_and_passive(monkeypatch, failure):
    from types import SimpleNamespace as N
    import numpy as np
    from motion_test_face_app import motion
    samples = [.3]*3 + [.1]*2 + [.3]*4 + [.1]*2 + [.3]*9
    request = SequenceRequest(frames=[{'image':'aGVsbG8=', 'timestamp_ms':i*80} for i in range(len(samples))], reference_template_hash='a'*64)
    class Mesh:
        def __init__(self, **kwargs): self.index = -1
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def process(self, image):
            self.index += 1
            face = N(landmark=[N(x=.5,y=.5,z=0)]*468)
            faces = [face,face] if failure == 'multiple_faces' and self.index == 5 else [face]
            return N(multi_face_landmarks=faces)
    monkeypatch.setitem(sys.modules, 'mediapipe', N(solutions=N(face_mesh=N(FaceMesh=Mesh))))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *args, **kwargs: np.zeros((40,40,3)))
    ears = iter(samples)
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {'eye_aspect_ratio':next(ears)})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99,bbox=(0,0,40,40)))
    monkeypatch.setattr(motion, 'assess_liveness', lambda *args: N(liveness_score=.95 if failure != 'passive' else .1,liveness_passed=failure != 'passive'))
    calls = []
    def match(*args):
        calls.append(args)
        passed = failure != 'identity' or len(calls) < 2
        return N(match_score=.98 if passed else .1,match_passed=passed), ''
    result = motion.analyze_sequence(request, match)
    assert result['passed'] is (failure is None)
    if failure is None:
        assert result['blink_count'] == 2
        assert len(calls) >= 4
