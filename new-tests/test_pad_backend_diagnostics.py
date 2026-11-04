"""Run separately from Module 3: backend and face service share an app name."""
import json
import httpx
import pytest

from test_checkin_diagnostics import api, records
from app import checkin_diagnostics as diag
from app.face_service import face_service

VERSION = 'minifasnet-v2-v1se-onnx-v1'


@pytest.mark.parametrize('pad_passed', [False, True])
def test_enforced_pad_failure_is_committed_as_rejected_despite_low_risk(api, records, monkeypatch, pad_passed):
    from app.database import SessionLocal
    from app.models import CheckIn
    client, payload, _ = api
    details = {'pad_mode': 'enforce', 'pad_status': 'evaluated', 'pad_evaluated': True,
               'pad_live_score': .9 if pad_passed else .500035, 'pad_threshold': .75,
               'pad_passed': pad_passed, 'pre_pad_liveness_score': .97,
               'pre_pad_liveness_passed': True, 'pad_would_veto': not pad_passed}
    def transport(request):
        bodies = {
            '/liveness/check': {'liveness_passed': pad_passed, 'liveness_score': .97 if pad_passed else 0.,
                'liveness_threshold': .85, 'challenge_type': 'passive', 'details': details},
            '/face/verify': {'match_passed': True, 'match_score': .99, 'match_threshold': .7},
            '/risk/assess': {'risk_score': .01, 'risk_level': 'LOW'},
        }
        return httpx.Response(200, json=bodies[request.url.path])
    with httpx.Client(transport=httpx.MockTransport(transport), base_url='http://test') as service:
        monkeypatch.setattr(face_service, '_client', service)
        response = client.post('/api/v1/checkins/', json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    # This fixture's unknown browser flags an otherwise valid capture.
    assert body['status'] == ('flagged' if pad_passed else 'rejected')
    assert body['liveness_passed'] is pad_passed
    assert body['risk_score'] < .5
    with SessionLocal() as db:
        saved = db.get(CheckIn, body['id'])
        assert saved.status == body['status']
        assert saved.liveness_score == (.97 if pad_passed else 0.)
    observed = next(r['values']['details'] for r in records() if r['stage'] == 'liveness')
    assert observed == details
    assert records()[-1]['stage'] == 'attendance_committed'


@pytest.mark.parametrize('pad_status,pad_passed', [('evaluated', False), ('evaluated', True), ('unavailable', None)])
def test_shadow_pad_diagnostics_survive_backend_without_changing_saved_attendance(
    api, records, monkeypatch, pad_status, pad_passed
):
    from app.database import SessionLocal
    from app.models import CheckIn
    client, payload, _ = api
    measured = pad_status == 'evaluated'
    details = {'pad_mode': 'shadow', 'pad_status': pad_status,
        'pad_evaluated': measured, 'pad_model_version': VERSION,
        'pad_live_score': (.9 if pad_passed else .01) if measured else None,
        'pad_threshold': .5, 'pad_passed': pad_passed,
        'pad_v2_live_score': .02 if measured else None,
        'pad_v1se_live_score': 0. if measured else None,
        'pad_inference_ms': 6.2 if measured else None,
        'pre_pad_liveness_score': .97, 'pre_pad_liveness_passed': True,
        'pad_would_veto': not pad_passed if measured else None,
        'image': 'SECRET_IMAGE', 'pad_features': ['SECRET_FEATURE']}
    def transport(request):
        bodies = {
            '/liveness/check': {'liveness_passed': True, 'liveness_score': .97,
                'liveness_threshold': .85, 'challenge_type': 'passive', 'details': details},
            '/face/verify': {'match_passed': True, 'match_score': .99, 'match_threshold': .7},
            '/risk/assess': {'risk_score': .01, 'risk_level': 'LOW'},
        }
        return httpx.Response(200, json=bodies[request.url.path])
    with httpx.Client(transport=httpx.MockTransport(transport), base_url='http://test') as service:
        monkeypatch.setattr(face_service, '_client', service)
        response = client.post('/api/v1/checkins/', json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['status'] == 'flagged' and body['liveness_passed'] is True
    # The fixture has an unknown device; its existing flag is independent of PAD.
    assert body['risk_score'] == .208
    with SessionLocal() as db:
        saved = db.get(CheckIn, body['id'])
        assert saved.status == 'flagged' and saved.liveness_score == .97
    observed = next(r['values']['details'] for r in records() if r['stage'] == 'liveness')
    assert observed == {k: v for k, v in details.items() if k not in ('image', 'pad_features')}
    assert 'SECRET' not in json.dumps(records(), allow_nan=False)
    assert records()[-1]['stage'] == 'attendance_committed'


def test_pad_allowlist_rejects_invalid_strings_types_and_nonfinite_scores():
    clean = diag.sanitize({'pad_mode': 'shadow', 'pad_status': 'evaluated',
        'pad_model_version': 'SECRET_IMAGE', 'pad_live_score': float('nan'),
        'pad_v2_live_score': 1.1, 'pad_v1se_live_score': True,
        'pad_inference_ms': float('inf'), 'pad_passed': 'SECRET',
        'pad_evaluated': True, 'image': 'SECRET'}, diag.DETAILS)
    assert clean == {'pad_mode': 'shadow', 'pad_status': 'evaluated', 'pad_evaluated': True}


def test_setup_helper_session_contract_with_real_backend(api, tmp_path):
    import importlib.util
    from pathlib import Path
    from app.database import SessionLocal
    from app.models import User, Session as AttendanceSession
    spec = importlib.util.spec_from_file_location('pad_setup_contract', Path(__file__).with_name('prepare_photo_replay.py'))
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    client, payload, _ = api
    with SessionLocal() as db:
        existing = db.get(AttendanceSession, payload['session_id'])
        course_id = existing.course_id
        db.get(User, existing.instructor_id).role = 'instructor'
        db.commit()
    def request(base, path, *, token, body):
        response = client.post('/api/v1' + path, json=body)
        assert response.status_code == 201, response.text
        return response.json()
    config = setup.create_pair('http://test', 'SECRET', course_id, 60, tmp_path / 'config.json', request)
    assert len(config['sessions']) == 2
