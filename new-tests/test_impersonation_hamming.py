"""Measured Hamming traces preserve sequence decisions, scope and privacy."""
import json
from types import SimpleNamespace as N

import pytest

from test_video_replay_sequence_diagnostics import scenario
from app import motion
from app.config import Settings, load_settings
from app.motion_diagnostics import SequenceDiagnostics
from app.template import compare_templates


def test_provisional_boundary_defaults_and_environment_override():
    for policy in (Settings(), load_settings({})):
        assert policy.face_match_hamming_fraction == .08984375
        assert policy.face_match_threshold == .70
    override = load_settings({'FACE_MATCH_HAMMING_FRACTION': '.11'})
    assert override.face_match_hamming_fraction == .11
    assert override.face_match_threshold == .70


@pytest.mark.parametrize('distance,passed', [
    (0, True), (6, True), (15, True), (16, True), (20, True), (22, True), (23, True),
    (24, False), (25, False), (29, False), (30, False), (31, False),
    (32, False), (33, False), (36, False), (38, False), (39, False),
    (40, False), (41, False), (256, False),
])
def test_actual_compared_templates_produce_trace_without_extra_inference(scenario, distance, passed):
    state, payload, _ = scenario
    reference = payload['reference_template_hash']
    current = f'{int(reference,16) ^ ((1 << distance)-1):064x}'
    comparison = compare_templates(reference, current)
    calls = []
    def verify(*args):
        calls.append(state['index'])
        return N(match_score=comparison.match_score, match_passed=comparison.match_passed,
                 current_template_hash=current, face_detected=True), 'outcome'
    request = motion.SequenceRequest(**payload)
    baseline = motion.analyze_sequence(request, verify)
    baseline_calls = list(calls)
    calls.clear()
    diagnostics = SequenceDiagnostics()
    observed = motion.analyze_sequence(request, verify, diagnostics.observe)
    data = diagnostics.snapshot()
    assert baseline == observed and observed['passed'] is passed
    assert calls == baseline_calls
    assert data['identity_checks'] == len(calls)
    assert data['simhash_bits'] == 256 and data['max_accepted_hamming_distance'] == 23
    assert data['face_match_hamming_fraction'] == .08984375
    assert data['min_hamming_distance'] == data['max_hamming_distance'] == distance
    for sample, frame in zip(data['identity_comparisons'], calls):
        assert sample == {'frame_index':frame, 'timestamp_ms':frame*80,
            'match_score':comparison.match_score, 'match_passed':passed, 'face_detected':True,
            'hamming_evaluated':True, 'hamming_distance':distance, 'hamming_fraction':distance/256}
    serialized = json.dumps(data)
    assert reference not in serialized and current not in serialized
    if not passed:
        assert data['reason'] == 'identity_failed' and data['first_frame'] == {'evaluated':False}


def test_no_face_does_not_fabricate_a_zero_hamming_distance(scenario):
    _, payload, _ = scenario
    diagnostics = SequenceDiagnostics()
    response = motion.analyze_sequence(motion.SequenceRequest(**payload),
        lambda *a: (N(match_score=0.,match_passed=False,current_template_hash='',face_detected=False),'no_face'),
        diagnostics.observe)
    assert response['passed'] is False
    item = diagnostics.snapshot()['identity_comparisons'][0]
    assert item['hamming_evaluated'] is False and item['face_detected'] is False
    assert 'hamming_distance' not in item and 'hamming_fraction' not in item


def test_diagnostic_distance_failure_does_not_change_a_verdict(scenario, monkeypatch):
    _, _, run = scenario
    baseline, calls = run()
    def broken(*a):
        raise RuntimeError('PRIVATE_FAILURE_DETAIL')
    monkeypatch.setattr(motion, 'hamming_distance', broken)
    diagnostics = SequenceDiagnostics()
    observed, observed_calls = run(observer=diagnostics.observe)
    assert observed == baseline and calls == observed_calls
    assert diagnostics.snapshot()['identity_checks'] > 0
    assert 'PRIVATE_FAILURE_DETAIL' not in json.dumps(diagnostics.snapshot())


def test_trace_is_bounded_retains_terminal_comparison_and_redacts_unknown_fields():
    diagnostics = SequenceDiagnostics()
    diagnostics.observe('started')
    for index in range(70):
        diagnostics.observe('identity',frame_index=index,timestamp_ms=index*80,
            hamming_evaluated=True,hamming_distance=index,hamming_fraction=index/256,
            match_score=.9,match_passed=index<69,face_detected=True,
            image='PRIVATE',embedding=['PRIVATE'],template_hash='PRIVATE')
    data = diagnostics.snapshot()
    assert data['identity_checks'] == 70 and data['identity_comparisons_truncated'] is True
    assert len(data['identity_comparisons']) == 64
    assert [item['frame_index'] for item in data['identity_comparisons']] == list(range(63)) + [69]
    assert data['identity_comparisons'][-1]['match_passed'] is False
    assert data['min_hamming_distance'] == 0 and data['max_hamming_distance'] == 69
    assert 'PRIVATE' not in json.dumps(data)


def test_numeric_projection_rejects_nonfinite_values_and_wrong_types():
    diagnostics = SequenceDiagnostics()
    diagnostics.observe('identity', hamming_distance=float('nan'), hamming_fraction=2,
                        match_score=True, face_detected='PRIVATE', match_passed=False,
                        hamming_evaluated=False, timestamp_ms=-1)
    assert diagnostics.snapshot()['identity_comparisons'] == [
        {'match_passed':False,'hamming_evaluated':False}]


def test_real_face_endpoint_reports_measured_hamming_without_exposing_templates(monkeypatch):
    import base64
    from io import BytesIO
    from pathlib import Path
    import uuid
    from fastapi.testclient import TestClient
    from PIL import Image
    from app.main import app

    sid = str(uuid.uuid4())
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED','true')
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS',sid)
    with Image.open(Path(__file__).resolve().parents[1] / 'sample_images/obama.jpg') as photo:
        photo.thumbnail((480,480))
        buffer = BytesIO()
        photo.convert('RGB').save(buffer,format='JPEG',quality=70)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    with TestClient(app) as client:
        enrollment = client.post('/face/enroll',json={
            'user_id':'isolated-hamming-smoke','image':encoded,'camera_consent':True})
        assert enrollment.status_code == 201
        reference = enrollment.json()['face_template_hash']
        response = client.post('/liveness/sequence',headers={'X-SAIV-Diagnostic-Session-ID':sid},json={
            'reference_template_hash':reference,
            'frames':[{'image':encoded,'timestamp_ms':i*80} for i in range(20)]})
    assert response.status_code == 200
    sample = response.json()['diagnostics']['identity_comparisons'][0]
    assert sample['hamming_evaluated'] is True
    assert sample['hamming_distance'] == 0 and sample['hamming_fraction'] == 0
    assert sample['match_score'] == 1 and sample['match_passed'] is True
    assert reference not in response.text and encoded[:100] not in response.text
