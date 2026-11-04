"""PAD contract and native graph checks; synthetic pixels are not accuracy trials."""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as N

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module3-face-recognition'))
from app import pad, liveness, main, motion
from app.config import Settings, load_settings
from app.motion_diagnostics import SequenceDiagnostics, _details

ASSETS = ROOT / 'module3-face-recognition/app/assets/pad'


@pytest.mark.parametrize('name,value', [('PAD_MODE', 'unexpected'),
    ('PAD_THRESHOLD', 'nan'), ('PAD_THRESHOLD', 'inf'), ('PAD_THRESHOLD', '-.1'), ('PAD_THRESHOLD', '1.1')])
def test_reject_unsupported_modes_and_invalid_cutoffs(name, value):
    with pytest.raises(RuntimeError):
        load_settings({name: value})


def test_explicit_shadow_config_uses_independent_cutoff():
    policy = load_settings({'PAD_MODE': 'shadow', 'PAD_THRESHOLD': '.42'})
    assert policy.pad_mode == 'shadow' and policy.pad_threshold == .42
    assert policy.liveness_threshold == .85
    assert Settings().pad_mode == 'enforce'
    assert Settings().pad_threshold == .75


@pytest.mark.parametrize('bbox,scale,expected', [
    ((80, 60, 40, 40), 2.7, (46, 26, 154, 134)),
    ((0, 0, 40, 40), 2.7, (0, 0, 108, 108)),
    ((160, 120, 40, 40), 2.7, (91, 51, 199, 159)),
    ((0, 0, 200, 160), 4., (0, 0, 199, 159)),
])
def test_original_context_boundary_shifting_and_inclusive_crop(bbox, scale, expected):
    # Fixed vectors from the original Minivision crop helper, including borders.
    assert pad.context_box((160, 200, 3), bbox, scale) == expected
    image = np.random.default_rng(12).integers(0, 256, (160, 200, 3), dtype=np.uint8)
    left, top, right, bottom = expected
    bgr = image[:, :, ::-1]
    reference = cv2.resize(bgr[top:bottom + 1, left:right + 1], (80, 80))
    actual = pad.preprocess(image, bbox, scale)
    np.testing.assert_array_equal(actual[0], reference.transpose(2, 0, 1))
    assert actual.shape == (1, 3, 80, 80) and actual.dtype == np.float32


def test_bgr_255_scale_and_original_rgb_unchanged():
    image = np.full((100, 100, 3), (10, 80, 250), dtype=np.uint8)
    before = image.copy()
    tensor = pad.preprocess(image, (25, 25, 50, 50), 2.7)
    np.testing.assert_array_equal(tensor[0, :, 20, 20], [250., 80., 10.])
    np.testing.assert_array_equal(image, before)


@pytest.mark.parametrize('bbox', [None, (0, 0, 0, 3), (-1, 0, 5, 5),
    (0, 0, 101, 5), (0, float('nan'), 5, 5)])
def test_invalid_boxes_are_unavailable(bbox):
    with pytest.raises(pad.PadUnavailableError):
        pad.preprocess(np.zeros((100, 100, 3), np.uint8), bbox, 2.7)


def test_live_class_is_not_the_winning_spoof_confidence_and_one_softmax():
    probs = pad.class_probabilities(np.array([[20., 0., -20.]], np.float32))
    assert probs[0] > .99 and probs[1] < .001
    logits = np.array([[1., 2., 3.]], np.float32)
    expected = np.exp(logits - logits.max()) / np.exp(logits - logits.max()).sum()
    np.testing.assert_allclose(pad.class_probabilities(logits), expected[0], rtol=1e-6)


@pytest.mark.parametrize('output', [np.zeros(3), np.zeros((1, 2)), np.zeros((2, 3)),
    np.array([[0, np.nan, 0]]), np.array([[0, np.inf, 0]])])
def test_invalid_model_outputs_are_unavailable(output):
    with pytest.raises(pad.PadUnavailableError):
        pad.class_probabilities(output)


@pytest.mark.parametrize('failure', ['missing_manifest', 'bad_manifest', 'missing_asset', 'corrupt_asset'])
def test_missing_corrupt_or_incompatible_assets_are_unavailable(tmp_path, failure):
    manifest = json.loads((ASSETS / 'manifest.json').read_text())
    if failure == 'bad_manifest':
        manifest['live_class_index'] = 0
    if failure != 'missing_manifest':
        (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    if failure == 'corrupt_asset':
        (tmp_path / 'MiniFASNetV2.onnx').write_bytes(b'corrupt model')
    with pytest.raises(pad.PadUnavailableError):
        pad.PadRuntime(tmp_path / 'manifest.json')


@pytest.fixture
def legacy(monkeypatch):
    state = {'pad_passed': False, 'unavailable': False, 'depth': 1.}
    policy = Settings(pad_mode='shadow')
    monkeypatch.setattr(liveness, 'settings', policy)
    monkeypatch.setattr(main, 'settings', policy)
    monkeypatch.setattr(liveness, '_extract_landmarks', lambda image: ((.5, .5, -.04),))
    monkeypatch.setattr(liveness, '_mesh_snapshot', lambda points: N(
        depth_score=state['depth'], mesh_score=1., face_mesh_complete=True, landmark_count=468,
        nose_tip_z=-.04, landmark_z_variance=.0005, relative_nose_depth=.04,
        depth_detected=True, depth_quality='good'))
    monkeypatch.setattr(liveness, '_face_crop', lambda image, *args: image)
    monkeypatch.setattr(liveness, 'analyze_texture', lambda crop: (1., {'periodic_artifact_penalty': 0.}))
    monkeypatch.setattr(liveness, 'analyze_color', lambda crop: (1., {}))
    def evaluate(*args, **kwargs):
        if state['unavailable']:
            raise pad.PadUnavailableError('sensitive internal error')
        score = .9 if state['pad_passed'] else .01
        return pad.PadAnalysis(score, state['pad_passed'], pad.MODEL_VERSION, 5., score, score)
    monkeypatch.setattr(liveness, 'evaluate_pad', evaluate)
    return state


@pytest.mark.parametrize('passed,unavailable', [(True, False), (False, False), (False, True)])
def test_shadow_pass_failure_and_outage_preserve_legacy_decisions(legacy, passed, unavailable):
    legacy.update(pad_passed=passed, unavailable=unavailable)
    result = liveness.assess_liveness(object(), face_bbox=(0, 0, 40, 40))
    assert result.liveness_passed is True and result.liveness_score == 1.
    details = result.details
    assert details['pre_pad_liveness_score'] == result.liveness_score
    assert details['pad_evaluated'] is (not unavailable)
    assert details['pad_would_veto'] is (None if unavailable else not passed)
    if unavailable:
        assert details['pad_status'] == 'unavailable'
        assert details['pad_live_score'] is details['pad_passed'] is None
        assert 'sensitive' not in json.dumps(details)


def test_shadow_pad_pass_cannot_rescue_a_low_overall_score(legacy):
    legacy.update(pad_passed=True, depth=.4)
    result = liveness.assess_liveness(object(), face_bbox=(0, 0, 40, 40))
    assert result.liveness_passed is False and result.liveness_score == .82
    assert result.details['pad_passed'] is True
    assert result.details['pad_would_veto'] is False


def test_off_and_missing_landmarks_do_not_run_pad(legacy, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('PAD should not run')
    monkeypatch.setattr(liveness, 'evaluate_pad', unexpected)
    monkeypatch.setattr(liveness, 'settings', Settings(pad_mode='off'))
    assert liveness.assess_liveness(object()).details['pad_status'] == 'off'
    monkeypatch.setattr(liveness, 'settings', Settings(pad_mode='shadow'))
    monkeypatch.setattr(liveness, '_extract_landmarks', lambda image: ())
    result = liveness.assess_liveness(object())
    assert result.details['pad_evaluated'] is False
    assert result.details['pad_live_score'] is None


def test_photo_endpoint_exposes_shadow_comparison_and_unevaluated_guards(legacy, monkeypatch):
    detection = N(detected=True, multiple_faces=False, confidence=.99, bbox=(0, 0, 40, 40), face_count=1)
    monkeypatch.setattr(main, 'decode_base64_image', lambda image: object())
    monkeypatch.setattr(main, 'detect_face', lambda image: detection)
    monkeypatch.setattr(main, 'extract_face_embedding', lambda *args: object())
    monkeypatch.setattr(main, 'generate_face_hash', lambda *args: 'a' * 64)
    with TestClient(main.app) as client:
        response = client.post('/liveness/check', json={'challenge_response': 'SECRET_IMAGE'})
        assert response.status_code == 200
        body = response.json()
        assert body['liveness_passed'] is True and body['details']['pad_passed'] is False
        assert body['details']['pad_would_veto'] is True
        assert 'SECRET_IMAGE' not in response.text
        for detected, multiple in [(False, False), (True, True)]:
            detection.detected, detection.multiple_faces = detected, multiple
            details = client.post('/liveness/check', json={'challenge_response': 'SECRET_IMAGE'}).json()['details']
            assert details['pad_evaluated'] is False and details['pad_live_score'] is None


def test_sequence_first_and_last_frames_receive_shared_shadow_pad(legacy, monkeypatch):
    ears = [.3] * 3 + [.1] * 2 + [.3] * 4 + [.1] * 2 + [.3] * 9
    class Tracker:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def detect_for_video(self, *args):
            return N(face_landmarks=[[N(x=.5, y=.5, z=-.04)] * 478])
    monkeypatch.setattr(motion, '_create_landmarker', lambda: (N(
        Image=lambda **kw: kw['data'], ImageFormat=N(SRGB='RGB')), Tracker()))
    monkeypatch.setattr(motion, 'decode_base64_image', lambda *a, **kw: np.zeros((40, 40, 3), np.uint8))
    samples = iter(ears)
    monkeypatch.setattr(motion, 'blink_metrics', lambda points: {'eye_aspect_ratio': next(samples)})
    monkeypatch.setattr(motion, 'detect_face', lambda image: N(confidence=.99, bbox=(0, 0, 40, 40)))
    diagnostics = SequenceDiagnostics()
    request = motion.SequenceRequest(reference_template_hash='a' * 64, frames=[
        {'image': 'SECRET', 'timestamp_ms': i * 80} for i in range(len(ears))])
    result = motion.analyze_sequence(request, lambda *a: (N(match_passed=True, match_score=.99), ''),
                                     diagnostics.observe)
    assert result['passed'] is True and result['liveness_score'] == 1.
    for position in ('first_frame', 'last_frame'):
        details = diagnostics.snapshot()[position]['details']
        assert details['pad_passed'] is False and details['pad_would_veto'] is True
        assert details['pad_evaluated'] is True


def test_sequence_allowlist_rejects_unbounded_versions_and_keeps_nullable_results():
    details = _details({'pad_mode': 'shadow', 'pad_status': 'unavailable', 'pad_evaluated': False,
        'pad_model_version': pad.MODEL_VERSION, 'pad_live_score': None, 'pad_passed': None,
        'pad_inference_ms': float('nan'), 'pad_threshold': .5, 'pad_v2_live_score': 'SECRET',
        'image': 'SECRET', 'landmarks': ['SECRET']})
    assert details['pad_live_score'] is details['pad_passed'] is None
    assert details['pad_model_version'] == pad.MODEL_VERSION
    assert 'SECRET' not in json.dumps(details, allow_nan=False)
    assert _details({'pad_model_version': 'SECRET', 'pad_mode': 'SECRET', 'pad_status': []}) == {}


def test_real_graph_ensemble_is_finite_and_neutralizes_cached_inputs():
    runtime = pad.PadRuntime(ASSETS / 'manifest.json')
    image = np.random.default_rng(3099).integers(0, 256, (160, 200, 3), np.uint8)
    result = runtime.evaluate(image, (50, 40, 60, 80), .5)
    assert 0 <= result.live_score <= 1 and result.inference_ms >= 0
    assert result.live_score == pytest.approx((result.v2_live_score + result.v1se_live_score) / 2)
    assert result.passed is (result.live_score >= .5)
    # forward() without setInput now sees neutral pixels, not the prior face.
    for net in runtime.nets:
        after_request = net.forward().copy()
        net.setInput(np.zeros((1, 3, 80, 80), np.float32))
        np.testing.assert_allclose(after_request, net.forward(), atol=1e-6)


def test_shared_nets_cannot_interleave_requests(monkeypatch):
    active, peak = 0, 0
    class Runtime:
        def evaluate(self, image, box, cutoff):
            nonlocal active, peak
            active += 1; peak = max(peak, active)
            time.sleep(.005)
            active -= 1
            return pad.PadAnalysis(float(image), True, pad.MODEL_VERSION, 5., float(image), float(image))
    monkeypatch.setattr(pad, '_runtime', Runtime())
    monkeypatch.setattr(pad, '_runtime_path', 'fake')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda x: pad.evaluate_pad(x, None, manifest_path='fake'), [.1, .2, .3, .4] * 4))
    assert [r.live_score for r in results] == [.1, .2, .3, .4] * 4
    assert peak == 1


def test_native_concurrent_results_match_serial():
    image = np.random.default_rng(6).integers(0, 256, (160, 200, 3), np.uint8)
    images = [image, np.flip(image, axis=1).copy()]
    expected = [pad.evaluate_pad(im, (50, 40, 60, 80)).live_score for im in images]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda im: pad.evaluate_pad(im, (50, 40, 60, 80)).live_score, images * 4))
    np.testing.assert_allclose(results, expected * 4, atol=1e-7)


def test_native_logits_match_original_pytorch_reference_vectors():
    reference = json.loads((ROOT / 'new-tests/pad-reference-vectors.json').read_text())
    image = np.random.default_rng(reference['numpy_seed']).integers(0, 256, reference['image_shape'], np.uint8)
    for case in reference['cases']:
        net = cv2.dnn.readNetFromONNX(str(ASSETS / case['model']))
        net.setInput(pad.preprocess(image, case['bbox'], case['scale']))
        np.testing.assert_allclose(net.forward(), case['reference_logits'],
                                   atol=reference['atol'], rtol=reference['rtol'])


def test_shadow_startup_failure_keeps_service_available(legacy, monkeypatch):
    def unavailable():
        raise pad.PadUnavailableError('SECRET_ASSET_PATH')
    monkeypatch.setattr(main, 'initialize_pad', unavailable)
    with TestClient(main.app) as client:
        assert main.app.state.pad_ready is False
        assert client.get('/health').status_code == 200


def test_pad_metrics_use_only_fixed_outcomes():
    from app import metrics
    image = np.zeros((100, 100, 3), np.uint8)
    pad.evaluate_pad(image, (25, 25, 50, 50))
    with pytest.raises(pad.PadUnavailableError):
        pad.evaluate_pad(image, None)
    exposition = metrics.render_metrics().decode()
    assert 'pad_outcomes_total{outcome="failed"}' in exposition
    assert 'pad_outcomes_total{outcome="unavailable"}' in exposition
    assert 'pad_duration_seconds_count' in exposition
    for line in exposition.splitlines():
        if line.startswith('pad_'):
            assert 'session' not in line and 'student' not in line


def test_real_photo_endpoint_runs_pad_in_shadow_and_preserves_legacy(monkeypatch):
    import base64
    image = base64.b64encode((ROOT / 'sample_images/obama.jpg').read_bytes()).decode()
    responses = []
    with TestClient(main.app) as client:
        for mode in ('off', 'shadow'):
            policy = Settings(pad_mode=mode)
            monkeypatch.setattr(liveness, 'settings', policy)
            monkeypatch.setattr(main, 'settings', policy)
            response = client.post('/liveness/check', json={'challenge_response': image})
            assert response.status_code == 200, response.text
            responses.append(response.json())
    off, shadow = responses
    for name in ('liveness_passed', 'liveness_score', 'face_embedding_hash'):
        assert off[name] == shadow[name]
    assert off['details']['pad_evaluated'] is False
    assert shadow['details']['pad_evaluated'] is True
    assert shadow['details']['pad_status'] == 'evaluated'
    assert 0 <= shadow['details']['pad_live_score'] <= 1
    assert image not in json.dumps(shadow)
