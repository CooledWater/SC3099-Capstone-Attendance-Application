"""Temporal v2 cases shared with the browser, plus sequence integration."""
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as N

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'module3-face-recognition/app'
spec = importlib.util.spec_from_file_location('random_motion_test_face_app', APP/'__init__.py', submodule_search_locations=[str(APP)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from random_motion_test_face_app import motion
from random_motion_test_face_app.random_motion import ChallengeSpec, MotionProgress, yaw_degrees
from random_motion_test_face_app.motion_diagnostics import SequenceDiagnostics

VECTORS = json.loads((ROOT/'new-tests/random-motion-vectors.json').read_text())


def rotation(yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, -40], [0, 0, 0, 1]]


@pytest.mark.parametrize('case', VECTORS, ids=lambda case: case['name'])
def test_temporal_vectors(case):
    progress = MotionProgress(ChallengeSpec(**case['spec']), motion.BlinkCounter())
    for timestamp, ear, yaw in case['samples']:
        progress.update(ear, yaw_degrees(rotation(yaw)), timestamp)
    assert progress.complete is case['passed']
    assert ('passed' if progress.complete else progress.failure_reason()) == case['reason']


@pytest.mark.parametrize('matrix', [None, [], [[0]*4]*4, [[float('nan')]*4]*4])
def test_invalid_pose_cannot_be_used(matrix):
    with pytest.raises(ValueError):
        yaw_degrees(matrix)


@pytest.mark.parametrize('changes', [{'version': 1}, {'blink_target': True}, {'blink_target': 0},
                                    {'blink_target': 3}, {'turn_direction': 'up'}, {'first_action': 'passive'}, {'extra': 1}])
def test_invalid_spec_rejected(changes):
    with pytest.raises(ValueError):
        ChallengeSpec(**{**VECTORS[0]['spec'], **changes})


@pytest.mark.parametrize('failure', [None, 'identity', 'passive_first', 'passive_last', 'pose', 'multiple_faces'])
@pytest.mark.parametrize('case', VECTORS[:8], ids=lambda case: case['name'])
def test_full_sequence_keeps_identity_passive_and_pose_requirements(monkeypatch, case, failure):
    state = {'index': -1, 'identity': [], 'passive': []}
    class Tracker:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def detect_for_video(self, image, timestamp):
            state['index'] += 1
            index = state['index']
            face = [N(x=.5, y=.5, z=0)]*478
            return N(face_landmarks=[face, face] if failure == 'multiple_faces' and index == 10 else [face],
                     facial_transformation_matrixes=[] if failure == 'pose' else [rotation(case['samples'][index][2])])
    monkeypatch.setattr(motion, '_create_landmarker', lambda: (N(Image=lambda **kwargs: kwargs['data'], ImageFormat=N(SRGB='RGB')), Tracker()))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *args, **kwargs: np.zeros((40, 80, 3)))
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {'eye_aspect_ratio': case['samples'][state['index']][1]})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99, bbox=(0, 0, 80, 40)))
    def passive(*args):
        index = state['index']; state['passive'].append(index)
        failed = failure == 'passive_first' and index == 0 or failure == 'passive_last' and index == len(case['samples'])-1
        return N(liveness_score=.0 if failed else .96, liveness_passed=not failed)
    def verify(*args):
        index = state['index']; state['identity'].append(index)
        failed = failure == 'identity' and index >= 8
        return N(match_score=.1 if failed else .98, match_passed=not failed), ''
    monkeypatch.setattr(motion, 'assess_liveness', passive)
    request = motion.SequenceRequest(challenge=case['spec'], reference_template_hash='a'*64,
        frames=[{'image': 'REQUEST_PIXELS', 'timestamp_ms': t} for t, _, _ in case['samples']])
    diagnostic = SequenceDiagnostics()
    if failure == 'pose':
        with pytest.raises(motion.LivenessUnavailableError):
            motion.analyze_sequence(request, verify, diagnostic.observe)
        return
    result = motion.analyze_sequence(request, verify, diagnostic.observe)
    assert result['passed'] is (failure is None)
    assert result['challenge_version'] == 2
    assert 'REQUEST_PIXELS' not in json.dumps(result)
    if failure is None:
        assert result['blink_count'] == case['spec']['blink_target']
        assert result['turn_passed'] and result['completed_steps'] == 2
        assert state['passive'] == [0, len(case['samples'])-1]
        assert all(index in state['identity'] for index in range(0, len(case['samples']), 8))
        assert state['identity'][-1] == len(case['samples'])-1
        assert diagnostic.snapshot()['turn_passed'] is True
