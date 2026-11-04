"""Isolated motion HTTP diagnostics: temporary SQLite and mocked transport."""
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module2-backend'))
_temporary = tempfile.TemporaryDirectory(prefix='saiv-video-diagnostics-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_temporary.name) / 'test.db')
os.environ['JWT_SECRET'] = 'isolated-video-diagnostics-secret'
os.environ['STRICT_SECURITY_MODE'] = 'false'
from fastapi.testclient import TestClient
from app import checkin_diagnostics as diag
from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal
from app.models import User, Course, Enrollment, CheckIn, Session as AttendanceSession
from app.motion import MotionPolicy, MotionChallenge
from app.face_service import face_service

SECRET = 'RAW_IMAGE_TEMPLATE_LANDMARK_TOKEN_NOT_FOR_LOGS'


@pytest.fixture
def world(monkeypatch, caplog):
    with SessionLocal() as db:
        user = User(email=f'{uuid.uuid4()}@example.test', full_name='Video test', role='student',
                    hashed_password='unused', camera_consent=True, geolocation_consent=True,
                    face_enrolled=True, face_embedding_hash='a' * 64)
        db.add(user); db.flush()
        course = Course(code=str(uuid.uuid4())[:8], name='Video test', semester='Test',
                        instructor_id=user.id, venue_latitude=1.3, venue_longitude=103.8)
        db.add(course); db.flush()
        now = datetime.utcnow()
        session = AttendanceSession(course_id=course.id, instructor_id=user.id, name='Video test', status='active',
            scheduled_start=now-timedelta(minutes=1), scheduled_end=now+timedelta(hours=1),
            checkin_opens_at=now-timedelta(minutes=1), checkin_closes_at=now+timedelta(hours=1),
            require_liveness_check=True, require_face_match=True)
        db.add(session); db.flush()
        db.add_all([Enrollment(student_id=user.id, course_id=course.id), MotionPolicy(session_id=session.id, required=True)])
        db.commit()
        uid, sid = user.id, session.id
    def auth():
        with SessionLocal() as db:
            yield db.get(User, uid)
    app.dependency_overrides[get_current_user] = auth
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', 'true')
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid)
    state = {'status': 200, 'outage': False, 'invalid': False, 'requests': [], 'body': {
        'passed': True, 'blink_count': 2, 'liveness_score': .96, 'face_match_score': .98,
        'image': SECRET, 'reference_template_hash': SECRET,
        'diagnostics': {'reason': 'passed', 'frame_count': 20, 'processed_frames': 20,
            'identity_checks': 5, 'liveness_threshold': .85, 'depth_threshold': .8, 'mesh_threshold': .8,
            'first_frame': {'evaluated': True, 'frame_index': 0, 'timestamp_ms': 0,
                'liveness_passed': True, 'liveness_score': .96, 'liveness_threshold': .85,
                'details': {'depth_score': .92, 'mesh_plausibility_score': .91,
                            'depth_passed': True, 'mesh_passed': True, 'landmarks': [SECRET], 'image': SECRET}},
            'last_frame': {'evaluated': True, 'frame_index': 19, 'timestamp_ms': 1520,
                'liveness_passed': True, 'liveness_score': .97,
                'details': {'depth_score': .94, 'mesh_plausibility_score': .93}},
            'frames': [SECRET], 'token': SECRET}}}
    def transport(request):
        state['requests'].append(request)
        if state['outage']:
            raise httpx.ConnectError(SECRET)
        if state['invalid']:
            return httpx.Response(200, text=SECRET)
        return httpx.Response(state['status'], json=state['body'])
    diag.logger.addHandler(caplog.handler)
    def records():
        return [json.loads(row.message[len(diag.PREFIX):]) for row in caplog.records
                if row.name == diag.logger.name and row.message.startswith(diag.PREFIX)]
    with httpx.Client(transport=httpx.MockTransport(transport), base_url='http://face.test') as service:
        monkeypatch.setattr(face_service, '_client', service)
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, uid, sid, state, records
    diag.logger.removeHandler(caplog.handler)
    app.dependency_overrides.clear()


def start(world):
    response = world[0].post('/api/v1/motion/challenges', json={'session_id': world[2]})
    assert response.status_code == 201, response.text
    return response.json()['challenge_id']


def verify(world, cid):
    return world[0].post(f'/api/v1/motion/challenges/{cid}/verify', json={
        'frames': [{'image': SECRET, 'timestamp_ms': i * 80} for i in range(20)]})


def test_scores_correlate_challenge_verification_and_committed_attendance(world):
    client, uid, sid, state, records = world
    cid = start(world)
    response = verify(world, cid)
    assert response.status_code == 200
    assert response.json() == {'passed': True, 'blink_count': 2, 'liveness_score': .96,
                               'face_match_score': .98, 'verification_id': cid}
    request = state['requests'][0]
    assert request.headers['X-SAIV-Diagnostic-Session-ID'] == sid
    assert set(json.loads(request.content)) == {'frames', 'reference_template_hash'}
    saved = client.post('/api/v1/checkins/', json={'session_id': sid, 'latitude': 1.3,
        'longitude': 103.8, 'device_fingerprint': 'untrusted-test-browser', 'motion_verification_id': cid})
    assert saved.status_code == 201, saved.text
    assert saved.json()['status'] == 'flagged'  # Preserve the existing unsigned-device policy.
    rows = records()
    assert [r['stage'] for r in rows] == ['motion_challenge_issued', 'motion_verification_started',
        'motion_sequence', 'motion_verified', 'attempt_started', 'decision', 'attendance_committed']
    assert {r['challenge_id'] for r in rows} == {cid}
    assert {r['session_id'] for r in rows} == {sid}
    assert len({r['diagnostic_id'] for r in rows}) == 3  # Issue, verify, and check-in HTTP requests.
    details = rows[2]['values']['diagnostics']
    assert details['first_frame']['details']['depth_score'] == .92
    assert details['last_frame']['details']['mesh_plausibility_score'] == .93
    assert rows[-1]['values']['checkin_id'] == saved.json()['id']
    assert SECRET not in json.dumps(rows)
    with SessionLocal() as db:
        challenge = db.get(MotionChallenge, cid)
        assert challenge.state == 'consumed'
        assert set(json.loads(challenge.result)) == {'passed', 'blink_count', 'liveness_score', 'face_match_score'}
        assert db.get(CheckIn, saved.json()['id']).student_id == uid
        assert SECRET not in challenge.result


def test_rejected_sequence_is_observed_without_attendance(world):
    _, uid, sid, state, records = world
    state['body'].update(passed=False, blink_count=0, liveness_score=0.)
    state['body']['diagnostics'].update(reason='passive_first_failed', last_frame={'evaluated': False})
    cid = start(world)
    response = verify(world, cid)
    assert response.status_code == 200 and response.json()['verification_id'] is None
    assert records()[-1]['stage'] == 'motion_verified' and records()[-1]['values']['passed'] is False
    assert records()[-2]['values']['diagnostics']['last_frame'] == {'evaluated': False}
    with SessionLocal() as db:
        assert db.get(MotionChallenge, cid).state == 'failed'
        assert db.query(CheckIn).filter_by(student_id=uid, session_id=sid).count() == 0


@pytest.mark.parametrize('kind', ['outage', 'non_200', 'invalid_json', 'invalid_result'])
def test_unavailable_or_invalid_results_never_become_rejection_or_success(world, kind):
    _, _, _, state, records = world
    cid = start(world)
    if kind == 'outage':
        state['outage'] = True
    elif kind == 'non_200':
        state['status'] = 503
        state['body']['diagnostics']['reason'] = 'unavailable'
    elif kind == 'invalid_json':
        state['invalid'] = True
    else:
        state['body']['passed'] = SECRET
    response = verify(world, cid)
    assert response.status_code == 503
    rows = records()
    assert rows[-1]['stage'] == 'motion_request_failed'
    assert not any(row['stage'] == 'motion_verified' for row in rows)
    assert SECRET not in json.dumps(rows)
    if kind == 'non_200':
        assert rows[-2]['values']['diagnostics']['first_frame']['details']['depth_score'] == .92
    with SessionLocal() as db:
        assert db.get(MotionChallenge, cid).state == 'failed'


@pytest.mark.parametrize('enabled,listed', [('false', True), ('true', False)])
def test_disabled_or_unlisted_motion_has_no_details_header_or_logs(world, monkeypatch, enabled, listed):
    _, _, sid, state, records = world
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', enabled)
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', sid if listed else str(uuid.uuid4()))
    cid = start(world)
    response = verify(world, cid)
    assert response.status_code == 200 and response.json()['passed'] is True
    assert records() == []
    assert 'X-SAIV-Diagnostic-Session-ID' not in state['requests'][0].headers
    assert 'diagnostics' not in response.json()


def test_expired_owned_challenge_is_an_inconclusive_request_failure(world):
    cid = start(world)
    with SessionLocal() as db:
        db.get(MotionChallenge, cid).expires_at = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
    response = verify(world, cid)
    assert response.status_code == 409
    assert world[4]()[-1]['stage'] == 'motion_request_failed'
    assert world[3]['requests'] == []


def test_foreign_challenge_does_not_disclose_diagnostics(world):
    cid = start(world)
    before = len(world[4]())
    with SessionLocal() as db:
        db.get(MotionChallenge, cid).user_id = str(uuid.uuid4())
        db.commit()
    response = verify(world, cid)
    assert response.status_code == 404
    assert len(world[4]()) == before


def test_log_sink_failure_does_not_change_verification(world, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError(SECRET)
    monkeypatch.setattr(diag.logger, 'info', broken)
    cid = start(world)
    response = verify(world, cid)
    assert response.status_code == 200 and response.json()['verification_id'] == cid


def test_nested_scopes_restore_the_correct_motion_correlation(monkeypatch):
    sessions = [str(uuid.uuid4()), str(uuid.uuid4())]
    challenges = [str(uuid.uuid4()), str(uuid.uuid4())]
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED', 'true')
    monkeypatch.setenv('CHECKIN_DIAGNOSTIC_SESSION_IDS', ','.join(sessions))
    with diag.capture(sessions[0], challenge_id=challenges[0]):
        with diag.capture(sessions[1], challenge_id=challenges[1]):
            assert diag.service_headers('/liveness/sequence') == {'X-SAIV-Diagnostic-Session-ID': sessions[1]}
        assert diag.service_headers('/liveness/sequence') == {'X-SAIV-Diagnostic-Session-ID': sessions[0]}
        assert diag.service_headers('/liveness/check') == {}
    assert diag.service_headers('/liveness/sequence') == {}
