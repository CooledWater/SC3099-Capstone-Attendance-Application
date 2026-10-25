"""Approved replay policy: test decisions without claiming camera/model accuracy."""
import sys
from pathlib import Path
from types import SimpleNamespace as N

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module3-face-recognition'))
from app import liveness, main, motion
from app.config import Settings, load_settings


def snapshot(depth, mesh):
    return N(depth_score=depth, mesh_score=mesh, face_mesh_complete=True,
             landmark_count=468, nose_tip_z=-.04, landmark_z_variance=.0005,
             relative_nose_depth=.04, depth_detected=True, depth_quality='good')


@pytest.fixture
def components(monkeypatch):
    policy = Settings()
    for module in (liveness, main, motion):
        monkeypatch.setattr(module, 'settings', policy)
    state = {'depth': 1., 'mesh': 1., 'texture': 1., 'color': 1., 'periodicity': 0.}
    monkeypatch.setattr(liveness, '_extract_landmarks', lambda image: ((.5, .5, -.04),))
    monkeypatch.setattr(liveness, '_mesh_snapshot', lambda points: snapshot(state['depth'], state['mesh']))
    monkeypatch.setattr(liveness, '_face_crop', lambda image, *args: image)
    monkeypatch.setattr(liveness, 'analyze_texture', lambda crop: (
        state['texture'], {'periodic_artifact_penalty': state['periodicity']}))
    monkeypatch.setattr(liveness, 'analyze_color', lambda crop: (state['color'], {}))
    return state


def test_approved_defaults_and_valid_environment_overrides():
    for policy in (Settings(), load_settings({})):
        assert (policy.liveness_threshold, policy.liveness_depth_threshold,
                policy.liveness_mesh_threshold) == (.85, .80, .80)
    policy = load_settings({'LIVENESS_THRESHOLD': '.9', 'LIVENESS_DEPTH_THRESHOLD': '.81',
                            'LIVENESS_MESH_THRESHOLD': '.82'})
    assert (policy.liveness_threshold, policy.liveness_depth_threshold,
            policy.liveness_mesh_threshold) == (.9, .81, .82)


@pytest.mark.parametrize('name', ['LIVENESS_THRESHOLD', 'LIVENESS_DEPTH_THRESHOLD', 'LIVENESS_MESH_THRESHOLD'])
@pytest.mark.parametrize('value', ['nan', 'inf', '-0.1', '1.01'])
def test_invalid_policy_configuration_fails_at_startup(name, value):
    with pytest.raises(RuntimeError):
        load_settings({name: value})


@pytest.mark.parametrize('depth,mesh,passed', [
    (.80, .80, True), (.800001, .800001, True),
    (.799999, 1., False), (1., .799999, False), (.799999, .799999, False),
])
def test_component_minimums_cannot_be_offset_by_texture_or_colour(components, depth, mesh, passed):
    components.update(depth=depth, mesh=mesh)
    result = liveness.assess_liveness(object())
    assert result.details['pre_gate_liveness_score'] >= .85
    assert result.liveness_passed is passed
    assert result.details['depth_passed'] is (depth >= .8)
    assert result.details['mesh_passed'] is (mesh >= .8)
    assert result.details['depth_threshold'] == result.details['mesh_threshold'] == .8
    if not passed:
        assert result.liveness_score == 0.
    assert result.liveness_passed == (result.liveness_score >= result.liveness_threshold)


@pytest.mark.parametrize('score,passed', [(.849999, False), (.85, True), (.850001, True)])
def test_final_score_boundary_with_geometry_above_minimum(components, score, passed):
    components['periodicity'] = (1. - score) / .6
    result = liveness.assess_liveness(object())
    assert result.liveness_threshold == .85
    assert result.liveness_score == score
    assert result.liveness_passed is passed


@pytest.mark.parametrize('depth,mesh,texture,colour,integrity,old_score,passed', [
    (.99411, .92302, 1., 1., 1., .978987, True),
    (.62945, .75188, .99816, 1., .995662, .822759, False),
    (.86414, .82673, .9963, 1., .991288, .907025, True),
    (.74772, .77296, .97718, .99997, .976054, .841207, False),
])
def test_recorded_scalar_cases_under_new_policy(components, depth, mesh, texture, colour,
                                               integrity, old_score, passed):
    # Scalar observations from image-replay-test-0/1; these do not replay pixels.
    components.update(depth=depth, mesh=mesh, texture=texture, color=colour,
                      periodicity=(1. - integrity) / .6)
    result = liveness.assess_liveness(object())
    assert result.details['pre_gate_liveness_score'] == pytest.approx(old_score, abs=.000003)
    assert result.liveness_passed is passed
    assert (result.liveness_score >= .85) is passed


def test_missing_landmarks_cannot_pass_even_with_zero_threshold(components, monkeypatch):
    monkeypatch.setattr(liveness, '_extract_landmarks', lambda image: ())
    result = liveness.assess_liveness(object(), threshold=0.)
    assert result.liveness_passed is False
    assert result.liveness_score == 0.
    assert result.details['depth_passed'] is result.details['mesh_passed'] is False


def test_lower_final_override_does_not_bypass_component_minimums(components):
    components['depth'] = .799999
    result = liveness.assess_liveness(object(), threshold=0.)
    assert result.liveness_passed is False
    assert result.liveness_score == 0.


@pytest.mark.parametrize('depth,mesh,passed', [(1., 1., True), (.799999, 1., False), (1., .799999, False)])
def test_photo_endpoint_exposes_consistent_scores_and_scalar_gate_details(components, monkeypatch,
                                                                         depth, mesh, passed):
    components.update(depth=depth, mesh=mesh)
    monkeypatch.setattr(main, 'decode_base64_image', lambda image: object())
    monkeypatch.setattr(main, 'detect_face', lambda image: N(
        detected=True, multiple_faces=False, confidence=.99, bbox=(0, 0, 40, 40), face_count=1))
    monkeypatch.setattr(main, 'extract_face_embedding', lambda *args: object())
    monkeypatch.setattr(main, 'generate_face_hash', lambda embedding: 'a' * 64)
    with TestClient(main.app) as client:
        response = client.post('/liveness/check', json={'challenge_response': 'REQUEST_ONLY_IMAGE'})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['liveness_threshold'] == .85
    assert body['liveness_passed'] is passed
    assert body['liveness_passed'] == (body['liveness_score'] >= body['liveness_threshold'])
    assert body['details']['depth_passed'] is (depth >= .8)
    assert body['details']['mesh_passed'] is (mesh >= .8)
    assert 'REQUEST_ONLY_IMAGE' not in response.text
    assert 'landmarks' not in body['details']


def test_no_face_endpoint_reports_failed_component_checks(components, monkeypatch):
    monkeypatch.setattr(main, 'decode_base64_image', lambda image: object())
    monkeypatch.setattr(main, 'detect_face', lambda image: N(detected=False))
    with TestClient(main.app) as client:
        response = client.post('/liveness/check', json={'challenge_response': 'REQUEST_ONLY_IMAGE'})
    assert response.status_code == 200
    body = response.json()
    assert body['liveness_passed'] is False
    assert body['liveness_threshold'] == .85
    assert body['details']['depth_passed'] is body['details']['mesh_passed'] is False
    assert body['details']['depth_threshold'] == body['details']['mesh_threshold'] == .8


@pytest.mark.parametrize('failure', [None, 'first_depth', 'last_mesh', 'configured_threshold'])
def test_sequence_uses_real_passive_policy_on_both_endpoint_frames(components, monkeypatch, failure):
    # Stub landmark tracking and identity; keep the real passive scoring function.
    ears = [.3] * 3 + [.1] * 2 + [.3] * 4 + [.1] * 2 + [.3] * 9
    class Tracker:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def detect_for_video(self, image, timestamp):
            return N(face_landmarks=[[N(x=.5, y=.5, z=-.04)] * 478])
    mp = N(Image=lambda **kwargs: kwargs['data'], ImageFormat=N(SRGB='RGB'))
    monkeypatch.setattr(motion, '_create_landmarker', lambda: (mp, Tracker()))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *args, **kwargs: np.zeros((40, 40, 3)))
    samples = iter(ears)
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {'eye_aspect_ratio': next(samples)})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99, bbox=(0, 0, 40, 40)))
    monkeypatch.setattr(main, '_verify_image', lambda *args: (N(match_passed=True, match_score=.99), ''))
    first = snapshot(.799999 if failure == 'first_depth' else 1., 1.)
    last = snapshot(.8 if failure == 'configured_threshold' else 1.,
                    .799999 if failure == 'last_mesh' else .8 if failure == 'configured_threshold' else 1.)
    snapshots = iter((first, last))
    monkeypatch.setattr(liveness, '_mesh_snapshot', lambda points: next(snapshots))
    threshold = .9 if failure == 'configured_threshold' else .85
    policy = Settings(liveness_threshold=threshold)
    for module in (liveness, motion, main):
        monkeypatch.setattr(module, 'settings', policy)
    checks = []
    real_assess = liveness.assess_liveness
    def record_assessment(*args):
        checks.append(args[4])
        return real_assess(*args)
    monkeypatch.setattr(motion, 'assess_liveness', record_assessment)
    with TestClient(main.app) as client:
        response = client.post('/liveness/sequence', json={
            'reference_template_hash': 'a' * 64,
            'frames': [{'image': 'REQUEST_ONLY_IMAGE', 'timestamp_ms': i * 80} for i in range(len(ears))],
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['passed'] is (failure is None)
    assert checks == [threshold] * (1 if failure == 'first_depth' else 2)
    if failure in ('last_mesh', 'configured_threshold'):
        assert body['blink_count'] == 2  # Two blinks cannot override passive failure.
    if failure == 'configured_threshold':
        assert body['liveness_score'] == .89
    assert 'REQUEST_ONLY_IMAGE' not in response.text
