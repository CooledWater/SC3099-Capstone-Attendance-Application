"""Run separately from Module 3 tests: both services use an app package."""
import json
import os
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module2-backend'))
_temporary = tempfile.TemporaryDirectory(prefix='saiv-diagnostics-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_temporary.name) / 'test.db')
os.environ['JWT_SECRET'] = 'isolated-diagnostics-test-secret'
os.environ['STRICT_SECURITY_MODE'] = 'false'
from app import checkin_diagnostics as diag
from app.face_service import FaceServiceClient, face_service


@pytest.fixture
def records(monkeypatch, caplog):
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', 'true')
    diag.logger.addHandler(caplog.handler)
    yield lambda: [json.loads(record.message[len(diag.PREFIX):]) for record in caplog.records
                   if record.name == diag.logger.name and record.message.startswith(diag.PREFIX)]
    diag.logger.removeHandler(caplog.handler)


@pytest.mark.parametrize('enabled,allowed', [('false', True), ('true', False), ('true', None)])
def test_disabled_or_unlisted_sessions_emit_nothing(monkeypatch, records, enabled, allowed):
    sid = str(uuid.uuid4())
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', enabled)
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid if allowed else str(uuid.uuid4()) if allowed is False else '')
    with diag.capture(sid):
        diag.event('decision', risk_score=.2)
    assert records() == []


def test_only_allowed_finite_scalars_reach_logs(monkeypatch, records):
    sid = str(uuid.uuid4()); monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    secret = 'DO_NOT_RECORD_IMAGE_TOKEN_TEMPLATE'
    with diag.capture(sid):
        diag.observe_response('/liveness/check', httpx.Response(200, json={
            'liveness_passed': True, 'liveness_score': .8, 'liveness_threshold': .6,
            'image': secret, 'face_embedding_hash': secret, 'diagnostic_id': secret,
            'details': {'depth_score': .9, 'color_distribution_score': secret,
                        'face_mesh_complete': True, 'nose_tip_z': -.05,
                        'landmarks': [secret], 'depth_quality': secret,
                        'weighted_contributions': {'depth': .27, 'image': secret},
                        'texture_signals': {'fft_peak_to_mean': 24, 'image': secret}},
        }))
        diag.event('decision', risk_score=float('nan'), venue_risk_score=float('inf'),
                   effective_threshold=True, radius_meters=1e100, accuracy_meters=secret)
    output = json.dumps(records())
    assert secret not in output and 'nose_tip_z' not in output and 'landmarks' not in output
    assert records()[1]['values']['details']['weighted_contributions'] == {'depth': .27}
    assert records()[2]['values'] == {}


def test_unavailable_and_invalid_service_results_are_explicit(monkeypatch, records):
    sid = str(uuid.uuid4()); monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    with diag.capture(sid):
        diag.observe_response('/liveness/check')
        diag.observe_response('/face/verify', httpx.Response(503, text='DO_NOT_RECORD_BODY'))
        diag.observe_response('/risk/assess', httpx.Response(200, text='DO_NOT_RECORD_BODY'))
    assert [row['values']['outcome'] for row in records()[1:]] == ['unavailable', 'unavailable', 'invalid_response']
    assert 'DO_NOT_RECORD_BODY' not in json.dumps(records())


def test_concurrent_attempts_have_separate_ids_and_contexts(monkeypatch, records):
    sessions = [str(uuid.uuid4()), str(uuid.uuid4())]
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', ','.join(sessions))
    barrier = Barrier(2)
    @diag.trace_checkin
    def attempt(checkin_data):
        barrier.wait(timeout=5)
        diag.event('decision', risk_score=.2)
        return 'unchanged'
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda sid: attempt(SimpleNamespace(session_id=sid)), sessions)) == ['unchanged'] * 2
    groups = {}
    for record in records():
        groups.setdefault(record['diagnostic_id'], []).append(record)
    assert len(groups) == 2
    for group in groups.values():
        assert len({item['session_id'] for item in group}) == 1
        assert [item['stage'] for item in group] == ['attempt_started', 'decision']
    diag.event('decision', risk_score=.9)
    assert len(records()) == 4


def test_failure_does_not_log_exception_content_and_resets_context(monkeypatch, records):
    sid = str(uuid.uuid4()); monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    with pytest.raises(RuntimeError):
        with diag.capture(sid):
            raise RuntimeError('DO_NOT_RECORD_EXCEPTION')
    assert records()[-1]['stage'] == 'request_failed'
    assert records()[-1]['values']['reason'] == 'server_error'
    assert 'DO_NOT_RECORD_EXCEPTION' not in json.dumps(records())
    diag.event('attendance_committed', status='approved')
    assert len(records()) == 2


def test_failing_log_sink_cannot_change_service_results(monkeypatch):
    sid = str(uuid.uuid4()); monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', 'true')
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    def broken(*args, **kwargs):
        raise OSError('unavailable log sink')
    monkeypatch.setattr(diag.logger, 'info', broken)
    client = FaceServiceClient()
    client._client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        'liveness_passed': True, 'liveness_score': .9, 'challenge_type': 'passive'})), base_url='http://test')
    with diag.capture(sid):
        result = client.check_liveness('request-only-image')
    assert result.passed and result.score == .9
    client._client.close()


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import SessionLocal
    from app.auth import get_current_user
    from app.models import User, Course, Enrollment, Session as AttendanceSession
    with SessionLocal() as db:
        user = User(email=f'{uuid.uuid4()}@example.test', full_name='Test', role='student',
                    hashed_password='unused', camera_consent=True, geolocation_consent=True,
                    face_enrolled=True, face_embedding_hash='a' * 64)
        db.add(user); db.flush()
        course = Course(code=str(uuid.uuid4())[:8], name='Test', semester='Test', instructor_id=user.id,
                        venue_latitude=1.3472192106767371, venue_longitude=103.68029662241148)
        db.add(course); db.flush()
        now = datetime.utcnow()
        session = AttendanceSession(course_id=course.id, instructor_id=user.id, name='Diagnostics', status='active',
            scheduled_start=now-timedelta(minutes=1), scheduled_end=now+timedelta(hours=1),
            checkin_opens_at=now-timedelta(minutes=1), checkin_closes_at=now+timedelta(hours=1),
            require_liveness_check=True, require_face_match=True)
        db.add(session); db.flush(); db.add(Enrollment(student_id=user.id, course_id=course.id)); db.commit()
        uid, sid = user.id, session.id
    def auth():
        with SessionLocal() as db:
            yield db.get(User, uid)
    app.dependency_overrides[get_current_user] = auth
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    def transport(request):
        data = {
            '/liveness/check': {'liveness_passed': True, 'liveness_score': .9, 'liveness_threshold': .6,
                'challenge_type': 'passive', 'details': {'depth_score': .8, 'weighted_contributions': {'depth': .24}}},
            '/face/verify': {'match_passed': True, 'match_score': .95, 'match_threshold': .7},
            '/risk/assess': {'risk_score': .2125, 'risk_threshold': .5,
                'signal_breakdown': {'liveness': .025, 'face_match': .0125, 'device': .1, 'network': .075, 'geolocation': 0}},
        }
        return httpx.Response(200, json=data[request.url.path])
    with httpx.Client(transport=httpx.MockTransport(transport), base_url='http://test') as service:
        monkeypatch.setattr(face_service, '_client', service)
        with TestClient(app, raise_server_exceptions=False) as client:
            payload = {'session_id': sid, 'latitude': 1.3472192106767371, 'longitude': 103.68029662241148,
                       'location_accuracy_meters': 10, 'device_fingerprint': 'not-for-logs',
                       'liveness_challenge_response': 'IMAGE_NOT_FOR_LOGS'}
            yield client, payload, service
    app.dependency_overrides.clear()


def test_http_instrumentation_links_components_decision_and_commit(api, records):
    client, payload, _ = api
    response = client.post('/api/v1/checkins/', json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['status'] == 'approved' and body['risk_score'] == .2125
    assert 'diagnostic_id' not in body and 'details' not in body
    rows = records()
    assert [row['stage'] for row in rows] == ['attempt_started', 'liveness', 'face_match', 'module3_risk', 'decision', 'attendance_committed']
    assert len({row['diagnostic_id'] for row in rows}) == 1
    assert rows[-1]['values']['checkin_id'] == body['id']
    assert rows[-2]['values']['risk_score'] == max(rows[-2]['values']['venue_risk_score'], .2125)
    assert 'IMAGE_NOT_FOR_LOGS' not in json.dumps(rows) and 'not-for-logs' not in json.dumps(rows)
    schema = client.get('/openapi.json').json()['paths']['/api/v1/checkins/']['post']['requestBody']
    assert schema['content']['application/json']['schema']['$ref'].endswith('/CheckInCreate')


def test_service_outage_is_not_reported_as_a_liveness_pass(api, records, monkeypatch):
    client, payload, _ = api
    def unavailable(request):
        raise httpx.ConnectError('DO_NOT_RECORD_EXCEPTION')
    with httpx.Client(transport=httpx.MockTransport(unavailable), base_url='http://test') as service:
        monkeypatch.setattr(face_service, '_client', service)
        response = client.post('/api/v1/checkins/', json=payload)
    assert response.status_code == 201  # Preserve the existing non-strict failure policy.
    assert response.json()['liveness_passed'] is None
    decision = next(row['values'] for row in records() if row['stage'] == 'decision')
    assert decision['liveness_available'] is False and decision['module3_risk_available'] is False
    assert 'DO_NOT_RECORD_EXCEPTION' not in json.dumps(records())


@pytest.mark.parametrize('score,passed,expected', [
    (0., False, 'rejected'), (.849999, False, 'rejected'), (.85, True, 'approved'),
])
def test_liveness_policy_verdict_reaches_saved_attendance_despite_low_risk(
    api, records, monkeypatch, score, passed, expected
):
    from app.database import SessionLocal
    from app.models import CheckIn
    client, payload, _ = api
    def transport(request):
        bodies = {
            '/liveness/check': {'liveness_passed': passed, 'liveness_score': score,
                'liveness_threshold': .85, 'challenge_type': 'passive', 'details': {
                    'depth_threshold': .8, 'mesh_threshold': .8,
                    'depth_passed': score != 0., 'mesh_passed': True,
                    'pre_gate_liveness_score': .95 if score == 0. else score,
                    'unapproved_field': 'DO_NOT_RECORD'}},
            '/face/verify': {'match_passed': True, 'match_score': .99, 'match_threshold': .7},
            '/risk/assess': {'risk_score': .01, 'risk_level': 'LOW'},
        }
        return httpx.Response(200, json=bodies[request.url.path])
    with httpx.Client(transport=httpx.MockTransport(transport), base_url='http://test') as service:
        monkeypatch.setattr(face_service, '_client', service)
        response = client.post('/api/v1/checkins/', json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['status'] == expected
    assert body['liveness_passed'] is passed
    assert body['face_match_passed'] is True
    assert body['risk_score'] == .01
    with SessionLocal() as db:
        saved = db.get(CheckIn, body['id'])
        assert saved.status == expected
        assert saved.liveness_passed is passed
        assert saved.liveness_score == score
        assert (saved.verified_at is not None) is passed
    observed = next(row['values']['details'] for row in records() if row['stage'] == 'liveness')
    assert observed['depth_threshold'] == observed['mesh_threshold'] == .8
    assert observed['depth_passed'] is (score != 0.)
    assert observed['mesh_passed'] is True
    assert observed['pre_gate_liveness_score'] == (.95 if score == 0. else score)
    assert 'DO_NOT_RECORD' not in json.dumps(records())
    assert records()[-1]['stage'] == 'attendance_committed'
    assert records()[-1]['values']['status'] == expected


def test_failed_commit_never_emits_attendance_committed(api, records, monkeypatch):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    from app.models import CheckIn
    client, payload, _ = api
    original = Session.commit
    def fail_insert(db):
        if any(isinstance(item, CheckIn) for item in db.new):
            raise IntegrityError('test failure', {}, None)
        return original(db)
    monkeypatch.setattr(Session, 'commit', fail_insert)
    assert client.post('/api/v1/checkins/', json=payload).status_code == 500
    stages = [row['stage'] for row in records()]
    assert 'decision' in stages and 'attendance_committed' not in stages
    assert stages[-1] == 'request_failed'
