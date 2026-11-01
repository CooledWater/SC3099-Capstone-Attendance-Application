"""Sequence diagnostics observe the existing checks without extra inference."""
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace as N

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module3-face-recognition'))
from app import main, motion
from app.motion_diagnostics import SequenceDiagnostics

SECRET = 'IMAGE_LANDMARK_TEMPLATE_TOKEN_MUST_NOT_LEAVE_REQUEST'
EARS = [.3] * 3 + [.1] * 2 + [.3] * 4 + [.1] * 2 + [.3] * 9


@pytest.fixture
def scenario(monkeypatch):
    state = {'failure': None, 'calls': [], 'index': -1}
    class Tracker:
        def __enter__(self):
            state['index'] = -1
            return self
        def __exit__(self, *args):
            pass
        def detect_for_video(self, image, timestamp):
            state['index'] += 1
            index = state['index']
            if state['failure'] == 'inference' and index == 5:
                raise RuntimeError(SECRET)
            face = [N(x=.5, y=.5, z=0)] * 478
            if state['failure'] == 'jump' and index == 5:
                face[1] = N(x=.8, y=.5, z=0)
            faces = [face]
            if index == 5 and state['failure'] in ('no_face', 'multiple_faces'):
                faces = [] if state['failure'] == 'no_face' else [face, face]
            return N(face_landmarks=faces)
    mp = N(Image=lambda **kwargs: kwargs['data'], ImageFormat=N(SRGB='RGB'))
    monkeypatch.setattr(motion, '_create_landmarker', lambda: (mp, Tracker()))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *args, **kwargs: np.zeros((40, 40, 3)))
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {
        'eye_aspect_ratio': .3 if state['failure'] == 'no_blinks' else EARS[state['index']]})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99, bbox=(0, 0, 40, 40)))
    def passive(*args):
        index = state['index']
        state['calls'].append(('passive', index))
        failed = (state['failure'] == 'first_depth' and index == 0
                  or state['failure'] == 'last_mesh' and index == len(EARS)-1)
        return N(liveness_passed=not failed, liveness_score=0. if failed else .96,
                 liveness_threshold=.85, details={
                     'depth_score': .6 if failed and index == 0 else .92,
                     'mesh_plausibility_score': .7 if failed and index else .91,
                     'depth_threshold': .8, 'mesh_threshold': .8,
                     'depth_passed': not (failed and index == 0),
                     'mesh_passed': not (failed and index > 0),
                     'pre_gate_liveness_score': .84 if failed else .96,
                     'texture_analysis_score': .99, 'color_distribution_score': 1.,
                     'weighted_contributions': {'depth': .276, 'image': SECRET},
                     'texture_signals': {'periodic_artifact_penalty': .01, 'image': SECRET},
                     'nose_tip_z': -.04, 'image': SECRET, 'landmarks': [SECRET]})
    monkeypatch.setattr(motion, 'assess_liveness', passive)
    def verify(*args):
        index = state['index']
        state['calls'].append(('identity', index))
        failed = state['failure'] == 'identity_first' or state['failure'] == 'identity_later' and index >= 5
        return N(match_passed=not failed, match_score=.1 if failed else .98), SECRET
    monkeypatch.setattr(main, '_verify_image', verify)
    payload = {'reference_template_hash': 'a' * 64,
               'frames': [{'image': SECRET, 'timestamp_ms': i * 80} for i in range(len(EARS))]}
    request = motion.SequenceRequest(**payload)
    def run(failure=None, observer=None):
        state.update(failure=failure, calls=[])
        result = motion.analyze_sequence(request, verify, observe=observer)
        return result, list(state['calls'])
    return state, payload, run


@pytest.mark.parametrize('failure,reason,first,last', [
    (None, 'passed', True, True),
    ('first_depth', 'passive_first_failed', True, False),
    ('last_mesh', 'passive_last_failed', True, True),
    ('identity_first', 'identity_failed', False, False),
    ('identity_later', 'identity_failed', True, False),
    ('no_face', 'face_count', True, False),
    ('multiple_faces', 'face_count', True, False),
    ('jump', 'face_jump', True, False),
    ('no_blinks', 'insufficient_blinks', True, True),
])
def test_measurements_preserve_verdict_and_processing_order(scenario, failure, reason, first, last):
    _, _, run = scenario
    baseline, baseline_calls = run(failure)
    diagnostics = SequenceDiagnostics()
    observed, calls = run(failure, diagnostics.observe)
    assert observed == baseline
    assert calls == baseline_calls  # No extra checks or processing after an early failure.
    details = diagnostics.snapshot()
    assert details['reason'] == reason
    assert details['first_frame']['evaluated'] is first
    assert details['last_frame']['evaluated'] is last
    assert details['identity_checks'] == sum(kind == 'identity' for kind, _ in calls)
    assert details['liveness_threshold'] == .85
    assert details['depth_threshold'] == details['mesh_threshold'] == .8
    if first:
        assert details['first_frame']['frame_index'] == 0
        assert 'depth_score' in details['first_frame']['details']
    if not last:
        assert details['last_frame'] == {'evaluated': False}
    assert SECRET not in json.dumps(details)
    assert 'nose_tip_z' not in json.dumps(details)


def test_observer_failure_cannot_change_verification(scenario):
    _, _, run = scenario
    baseline, calls = run()
    def broken(*args, **kwargs):
        raise OSError(SECRET)
    observed, observed_calls = run(observer=broken)
    assert observed == baseline and observed_calls == calls


@pytest.mark.parametrize('enabled,listed,header,expected', [
    ('false', True, True, False), ('true', False, True, False),
    ('true', True, False, False), ('true', True, True, True),
])
def test_internal_details_require_explicit_session_scope(scenario, monkeypatch, enabled, listed, header, expected):
    _, payload, _ = scenario
    sid = str(uuid.uuid4())
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', enabled)
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid if listed else str(uuid.uuid4()))
    headers = {'X-SAIV-Diagnostic-Session-ID': sid} if header else {}
    with TestClient(main.app) as client:
        response = client.post('/liveness/sequence', json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert ('diagnostics' in body) is expected
    assert set(body) == {'passed', 'blink_count', 'liveness_score', 'face_match_score'} | ({'diagnostics'} if expected else set())
    assert body['passed'] is True and body['blink_count'] == 2
    assert SECRET not in response.text


def test_late_model_failure_preserves_only_completed_measurements(scenario, monkeypatch):
    state, payload, _ = scenario
    state['failure'] = 'inference'
    sid = str(uuid.uuid4())
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', 'true')
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    with TestClient(main.app) as client:
        normal = client.post('/liveness/sequence', json=payload)
        response = client.post('/liveness/sequence', json=payload, headers={'X-SAIV-Diagnostic-Session-ID': sid})
    assert normal.status_code == response.status_code == 503
    assert normal.json() == {'detail': 'Face models are unavailable'}
    details = response.json()['diagnostics']
    assert details['reason'] == 'unavailable'
    assert details['first_frame']['evaluated'] is True
    assert details['last_frame'] == {'evaluated': False}
    assert SECRET not in response.text


def test_source_projection_rejects_sensitive_invalid_or_nonfinite_details():
    diagnostics = SequenceDiagnostics()
    diagnostics.observe('passive', position='first_frame', liveness_passed=True,
                        liveness_score=.9, liveness_threshold=.85, details={
                            'depth_score': float('nan'), 'mesh_plausibility_score': float('inf'),
                            'texture_analysis_score': True, 'depth_passed': SECRET,
                            'color_distribution_score': 1., 'image': SECRET,
                            'weighted_contributions': {'depth': .27, 'mesh': SECRET}})
    frame = diagnostics.snapshot()['first_frame']
    assert frame['details'] == {'color_distribution_score': 1., 'weighted_contributions': {'depth': .27}}
    assert SECRET not in json.dumps(frame, allow_nan=False)
