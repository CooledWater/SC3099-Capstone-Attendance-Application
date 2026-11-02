"""Enforced PAD decisions, weighted geometry, and recorded-scalar regressions."""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace as N

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module3-face-recognition'))
from app import liveness, main, motion, pad
from app.config import Settings
from app.motion_diagnostics import SequenceDiagnostics


@pytest.fixture
def policy(monkeypatch):
    state = dict(depth=1., mesh=1., texture=1., color=1., periodicity=0.,
                 v2=.9, v1se=.9, unavailable=False, calls=0)
    for module in (liveness, main, motion):
        monkeypatch.setattr(module, 'settings', Settings())
    monkeypatch.setattr(liveness, '_extract_landmarks', lambda image: ((.5, .5, -.04),))
    monkeypatch.setattr(liveness, '_mesh_snapshot', lambda points: N(
        depth_score=state['depth'], mesh_score=state['mesh'], face_mesh_complete=True,
        landmark_count=468, nose_tip_z=-.04, landmark_z_variance=.0005,
        relative_nose_depth=.04, depth_detected=True, depth_quality='good'))
    monkeypatch.setattr(liveness, '_face_crop', lambda image, *args: image)
    monkeypatch.setattr(liveness, 'analyze_texture', lambda image: (
        state['texture'], {'periodic_artifact_penalty': state['periodicity']}))
    monkeypatch.setattr(liveness, 'analyze_color', lambda image: (state['color'], {}))
    def evaluate(*args, threshold, **kwargs):
        state['calls'] += 1
        assert threshold == .75
        if state['unavailable']:
            raise pad.PadUnavailableError('SECRET_INTERNAL_DETAILS')
        score = (state['v2'] + state['v1se']) / 2
        return pad.PadAnalysis(score, score >= threshold, pad.MODEL_VERSION, 1., state['v2'], state['v1se'])
    monkeypatch.setattr(liveness, 'evaluate_pad', evaluate)
    monkeypatch.setattr(main, 'decode_base64_image', lambda image: object())
    monkeypatch.setattr(main, 'detect_face', lambda image: N(
        detected=True, multiple_faces=False, confidence=.99, bbox=(0, 0, 40, 40), face_count=1))
    monkeypatch.setattr(main, 'extract_face_embedding', lambda *args: object())
    monkeypatch.setattr(main, 'generate_face_hash', lambda *args: 'a' * 64)
    return state


@pytest.mark.parametrize('pad_score,passed', [(.749999, False), (.75, True), (.750001, True)])
def test_pad_boundary_independently_vetoes_high_liveness(policy, pad_score, passed):
    policy.update(v2=pad_score, v1se=pad_score)
    result = liveness.assess_liveness(object())
    assert result.liveness_passed is passed
    assert result.liveness_score == (1. if passed else 0.)
    assert result.details['pre_pad_liveness_score'] == 1.
    assert result.details['pre_pad_liveness_passed'] is True
    assert result.details['pad_would_veto'] is (not passed)
    assert result.details['pad_mode'] == 'enforce'


def test_pad_veto_cannot_be_bypassed_by_zero_liveness_cutoff(policy):
    policy.update(v2=.999954, v1se=.000116)
    result = liveness.assess_liveness(object(), threshold=0.)
    assert result.details['pad_live_score'] == pytest.approx(.500035)
    assert result.liveness_passed is False and result.liveness_score == 0.


def test_pad_pass_does_not_rescue_low_weighted_liveness(policy):
    policy.update(depth=.4)
    result = liveness.assess_liveness(object())
    assert result.details['pad_passed'] is True
    assert result.liveness_score == .82 and result.liveness_passed is False


@pytest.mark.parametrize('v2,v1se,passed', [(.9, .9, True), (.999954, .000116, False)])
def test_photo_http_decision_uses_enforced_pad_with_low_geometry(policy, v2, v1se, passed):
    policy.update(depth=.72203, mesh=.76884, v2=v2, v1se=v1se)
    with TestClient(main.app) as client:
        response = client.post('/liveness/check', json={'challenge_response': 'SECRET_IMAGE'})
    assert response.status_code == 200
    body = response.json()
    assert body['liveness_passed'] is passed
    assert body['liveness_threshold'] == .85
    assert body['details']['pre_pad_liveness_score'] == .858819
    assert body['liveness_score'] == (.858819 if passed else 0.)
    assert not {'depth_threshold', 'mesh_threshold', 'depth_passed', 'mesh_passed'} & body['details'].keys()
    assert 'SECRET' not in response.text


def test_client_cannot_disable_pad_in_request(policy):
    with TestClient(main.app) as client:
        response = client.post('/liveness/check', json={
            'challenge_response': 'image', 'pad_mode': 'off', 'pad_threshold': 0.})
    assert response.status_code == 422
    assert policy['calls'] == 0


def test_pad_outage_is_service_error_not_a_fabricated_live_or_spoof_result(policy):
    policy['unavailable'] = True
    with TestClient(main.app) as client:
        response = client.post('/liveness/check', json={'challenge_response': 'SECRET_IMAGE'})
    assert response.status_code == 503
    assert 'SECRET' not in response.text
    assert 'liveness_passed' not in response.json()


@pytest.mark.parametrize('failure', [None, 'first', 'last', 'unavailable'])
def test_sequence_applies_pad_to_both_passive_frames(policy, monkeypatch, failure):
    ears = [.3] * 3 + [.1] * 2 + [.3] * 4 + [.1] * 2 + [.3] * 9
    class Tracker:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def detect_for_video(self, *args):
            return N(face_landmarks=[[N(x=.5, y=.5, z=-.04)] * 478])
    monkeypatch.setattr(motion, '_create_landmarker', lambda: (N(
        Image=lambda **kwargs: kwargs['data'], ImageFormat=N(SRGB='RGB')), Tracker()))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *a, **kw: np.zeros((40, 40, 3), np.uint8))
    samples = iter(ears)
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {'eye_aspect_ratio': next(samples)})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99, bbox=(0, 0, 40, 40)))
    monkeypatch.setattr(main, '_verify_image', lambda *args: (N(match_passed=True, match_score=.99), ''))
    evaluate = liveness.evaluate_pad
    def frame_pad(*args, **kwargs):
        failed = failure == 'first' and policy['calls'] == 0 or failure == 'last' and policy['calls'] == 1
        policy.update(v2=.01 if failed else .9, v1se=.01 if failed else .9,
                      unavailable=failure == 'unavailable')
        return evaluate(*args, **kwargs)
    monkeypatch.setattr(liveness, 'evaluate_pad', frame_pad)
    diagnostics = SequenceDiagnostics()
    request = motion.SequenceRequest(reference_template_hash='a' * 64,
        frames=[{'image': 'SECRET_IMAGE', 'timestamp_ms': i * 80} for i in range(len(ears))])
    if failure == 'unavailable':
        with pytest.raises(liveness.LivenessUnavailableError):
            motion.analyze_sequence(request, main._verify_image, diagnostics.observe)
        return
    result = motion.analyze_sequence(request, main._verify_image, diagnostics.observe)
    assert result['passed'] is (failure is None)
    assert policy['calls'] == (1 if failure == 'first' else 2)
    assert result['liveness_score'] == (0. if failure else 1.)
    if failure == 'last':
        assert result['blink_count'] == 2
    for frame in ('first_frame', 'last_frame'):
        observed = diagnostics.snapshot()[frame]
        if observed['evaluated']:
            assert observed['details']['pad_mode'] == 'enforce'
    assert 'SECRET' not in json.dumps(diagnostics.snapshot())


def recorded_cases():
    for path in sorted((ROOT / 'new-documentations/image-replay').glob('photo-pad-20*.md')):
        for block in re.findall(r'```json\s*(.*?)\s*```', path.read_text(), re.S):
            records = json.loads(block)
            stages = {r['stage']: r['values'] for r in records}
            yield pytest.param(stages['liveness']['details'], id=path.stem + '-' + records[0]['diagnostic_id'][:8])


@pytest.mark.parametrize('details', list(recorded_cases()))
def test_all_ten_recorded_captures_under_real_scoring_function(policy, details):
    policy.update(depth=details['depth_score'], mesh=details['mesh_plausibility_score'],
                  texture=details['texture_analysis_score'], color=details['color_distribution_score'],
                  periodicity=details['texture_signals']['periodic_artifact_penalty'],
                  v2=details['pad_v2_live_score'], v1se=details['pad_v1se_live_score'])
    result = liveness.assess_liveness(object())
    assert result.details['pre_pad_liveness_score'] == pytest.approx(details['pre_gate_liveness_score'], abs=.00001)
    assert result.liveness_passed is (details['pad_live_score'] >= .75)
    assert result.liveness_score == (result.details['pre_pad_liveness_score'] if result.liveness_passed else 0.)
