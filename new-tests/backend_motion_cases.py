"""Isolated HTTP tests: temporary SQLite DB, mocked Module 3 transport only."""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(prefix='saiv-motion-', suffix='.db')
os.environ['JWT_SECRET'] = 'isolated-test-secret'
sys.path.insert(0, str(ROOT / 'module2-backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal
from app.models import User, Course, Enrollment, Session as AttendanceSession
from app.motion import MotionPolicy, MotionChallenge
from app.face_service import face_service

@pytest.fixture
def setup(monkeypatch):
    import uuid
    with SessionLocal() as db:
        user = User(email=f'{uuid.uuid4()}@example.com', full_name='Test', hashed_password='unused', role='student', camera_consent=True, face_enrolled=True, face_embedding_hash='a'*64)
        db.add(user); db.flush()
        course = Course(code=str(uuid.uuid4())[:8], name='Test', semester='Test', instructor_id=user.id, venue_latitude=1.3483, venue_longitude=103.6831)
        db.add(course); db.flush()
        now = datetime.utcnow()
        session = AttendanceSession(course_id=course.id, instructor_id=user.id, name='Test', status='active', scheduled_start=now, scheduled_end=now+timedelta(hours=1), checkin_opens_at=now-timedelta(minutes=1), checkin_closes_at=now+timedelta(hours=1), require_liveness_check=True)
        db.add(session); db.flush()
        db.add(Enrollment(student_id=user.id, course_id=course.id))
        db.commit(); db.refresh(user); db.refresh(session)
        uid, sid = user.id, session.id
    def auth():
        with SessionLocal() as db:
            yield db.get(User, uid)
    app.dependency_overrides[get_current_user] = auth
    monkeypatch.setattr(face_service, '_post', lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {'passed': True, 'blink_count': 2, 'liveness_score': .95, 'face_match_score': .98}))
    with TestClient(app) as client:
        yield client, uid, sid
    app.dependency_overrides.clear()


def frames():
    return {'frames': [{'timestamp_ms': i*80, 'image': 'aGVsbG8='} for i in range(20)]}

def checkin(sid, **kwargs):
    return {'session_id': sid, 'latitude': 1.3483, 'longitude': 103.6831, 'device_fingerprint': 'test', **kwargs}

def test_legacy_checkin_without_image_still_works(setup):
    client, _, sid = setup
    response = client.post('/api/v1/checkins/', json=checkin(sid))
    assert response.status_code == 201, response.text
    assert response.json()['liveness_passed'] is None


def test_required_motion_cannot_be_bypassed(setup):
    client, _, sid = setup
    with SessionLocal() as db:
        db.add(MotionPolicy(session_id=sid, required=True)); db.commit()
    response = client.post('/api/v1/checkins/', json=checkin(sid))
    assert response.status_code == 400


def test_sequence_then_checkin_and_no_reuse(setup):
    client, _, sid = setup
    start = client.post('/api/v1/motion/challenges', json={'session_id': sid})
    assert start.status_code == 201, start.text
    cid = start.json()['challenge_id']
    verified = client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames())
    assert verified.status_code == 200, verified.text
    assert verified.json()['verification_id'] == cid
    repeated = client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames())
    assert repeated.status_code == 409
    response = client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid))
    assert response.status_code == 201, response.text
    assert response.json()['liveness_passed'] is True
    assert response.json()['face_match_passed'] is True
    with SessionLocal() as db:
        assert db.get(MotionChallenge, cid).state == 'consumed'
        assert 'image' not in db.get(MotionChallenge, cid).result


def test_expired_and_wrong_owner(setup):
    client, uid, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with SessionLocal() as db:
        item = db.get(MotionChallenge, cid); item.expires_at = datetime.utcnow()-timedelta(seconds=1); db.commit()
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 409


def test_outage_never_issues_verification(setup, monkeypatch):
    import httpx
    client, _, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    def unavailable(*args): raise httpx.ConnectError('offline')
    monkeypatch.setattr(face_service, '_post', unavailable)
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 503
    assert client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid)).status_code == 409


def test_invalid_frame_order_rejected_without_pixels(setup):
    client, _, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    payload = frames(); payload['frames'][1]['timestamp_ms'] = 0
    response = client.post(f'/api/v1/motion/challenges/{cid}/verify', json=payload)
    assert response.status_code == 422
    assert 'aGVsbG8=' not in response.text


def test_wrong_owner_and_session_proof_rejected(setup):
    client, uid, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with SessionLocal() as db:
        item = db.get(MotionChallenge, cid)
        item.user_id = 'someone-else'; db.commit()
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 404
    assert client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid)).status_code == 400
    with SessionLocal() as db:
        item = db.get(MotionChallenge, cid); item.user_id = uid; item.session_id = 'another-session'; db.commit()
    assert client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid)).status_code == 400


def test_new_attempt_invalidates_previous(setup):
    client, _, sid = setup
    old = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    new = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    assert new != old
    assert client.post(f'/api/v1/motion/challenges/{old}/verify', json=frames()).status_code == 404


def test_failed_sequence_cannot_be_used(setup, monkeypatch):
    client, _, sid = setup
    monkeypatch.setattr(face_service, '_post', lambda *a: SimpleNamespace(status_code=200, json=lambda: {'passed': False, 'blink_count': 1, 'liveness_score': .7, 'face_match_score': .9}))
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    response = client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames())
    assert response.status_code == 200
    assert response.json()['verification_id'] is None
    assert client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid)).status_code == 409


def test_consent_and_enrollment_are_required(setup):
    client, uid, sid = setup
    with SessionLocal() as db:
        db.get(User, uid).camera_consent = False; db.commit()
    assert client.post('/api/v1/motion/challenges', json={'session_id': sid}).status_code == 400
    with SessionLocal() as db:
        user = db.get(User, uid); user.camera_consent = True; user.face_enrolled = False; db.commit()
    assert client.post('/api/v1/motion/challenges', json={'session_id': sid}).status_code == 400


def test_instructor_can_enable_and_disable_motion_policy(setup):
    client, uid, sid = setup
    with SessionLocal() as db:
        db.get(User, uid).role = 'instructor'; db.commit()
    response = client.patch(f'/api/v1/sessions/{sid}', json={'require_motion_check':True})
    assert response.status_code == 200, response.text
    assert response.json()['require_motion_check'] is True
    response = client.patch(f'/api/v1/sessions/{sid}', json={'require_motion_check':False})
    assert response.status_code == 200
    assert response.json()['require_motion_check'] is False


def test_oversized_upload_rejected_before_json_parsing(setup):
    client, _, _ = setup
    response = client.post('/api/v1/motion/challenges/unused/verify', content=b' '*6_200_001, headers={'content-type':'application/json'})
    assert response.status_code == 413


def test_consumption_rolls_back_with_attendance_transaction(setup):
    from app.motion import consume
    client, uid, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id':sid}).json()['challenge_id']
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 200
    with SessionLocal() as db:
        consume(db, db.get(User, uid), sid, cid)
        db.rollback()
    with SessionLocal() as db:
        assert db.get(MotionChallenge, cid).state == 'verified'


def test_checkin_query_budget_with_real_auth(setup):
    from sqlalchemy import event
    from app.database import engine
    from app.auth import create_access_token
    client, uid, sid = setup
    app.dependency_overrides.clear()
    statements = []
    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        response = client.post('/api/v1/checkins/', json=checkin(sid), headers={
            'Authorization': 'Bearer '+create_access_token(uid, 'student')})
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert response.status_code == 201, response.text
    assert response.json()['student_id'] == uid
    assert len(statements) == 3, statements


@pytest.mark.parametrize('role,active,token_kind,expected', [
    ('instructor', True, 'access', 200), ('ta', True, 'access', 200),
    ('admin', True, 'access', 200), ('student', True, 'access', 403),
    ('instructor', False, 'access', 401), ('instructor', True, 'refresh', 401),
    ('instructor', True, 'invalid', 401), ('instructor', True, 'missing', 403),
])
def test_session_list_preserves_authentication(setup, role, active, token_kind, expected):
    from app.auth import create_access_token, create_refresh_token
    client, uid, sid = setup
    with SessionLocal() as db:
        user = db.get(User, uid); user.role = role; user.is_active = active; db.commit()
    app.dependency_overrides.clear()
    token = create_access_token(uid, role) if token_kind == 'access' else create_refresh_token(uid,role) if token_kind == 'refresh' else 'invalid'
    headers = {} if token_kind == 'missing' else {'Authorization': 'Bearer '+token}
    response = client.get(f'/api/v1/checkins/session/{sid}', headers=headers)
    assert response.status_code == expected, response.text


@pytest.mark.parametrize('count', [0, 1, 20])
def test_session_list_constant_query_count(setup, count):
    from app.models import CheckIn
    from app.auth import create_access_token
    from app.database import engine
    from sqlalchemy import event
    import uuid
    client, uid, sid = setup
    with SessionLocal() as db:
        db.get(User, uid).role = 'instructor'
        for i in range(count):
            student = User(email=f'{uuid.uuid4()}@example.com',full_name='Listed student',hashed_password='unused',role='student')
            db.add(student); db.flush()
            db.add(CheckIn(session_id=sid,student_id=student.id,status='approved',risk_score=0.0))
        db.commit()
    app.dependency_overrides.clear()
    statements = []
    def record(conn,cursor,statement,parameters,context,many): statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:
        response = client.get(f'/api/v1/checkins/session/{sid}',headers={'Authorization':'Bearer '+create_access_token(uid,'instructor')})
    finally: event.remove(engine,'before_cursor_execute',record)
    assert response.status_code == 200, response.text
    assert len(response.json()) == count
    assert len(statements) == 2, statements


def test_session_list_missing_session_keeps_404(setup):
    from app.auth import create_access_token
    client,uid,_=setup
    with SessionLocal() as db: db.get(User,uid).role='instructor'; db.commit()
    app.dependency_overrides.clear()
    response=client.get('/api/v1/checkins/session/not-present',headers={'Authorization':'Bearer '+create_access_token(uid,'instructor')})
    assert response.status_code == 404


def test_read_mode_is_scoped_and_write_rollback_still_works(setup):
    from app.database import engine, ReadSessionLocal
    from app.auth import create_access_token
    from sqlalchemy import event
    client, uid, sid = setup
    with SessionLocal() as db:
        db.get(User, uid).role = 'instructor'; db.commit()
    app.dependency_overrides.clear()
    modes = []
    def record(conn,cursor,statement,parameters,context,many):
        modes.append(conn.get_execution_options().get('isolation_level'))
    event.listen(engine,'before_cursor_execute',record)
    try:
        response = client.get(f'/api/v1/checkins/session/{sid}', headers={'Authorization':'Bearer '+create_access_token(uid,'instructor')})
    finally: event.remove(engine,'before_cursor_execute',record)
    assert response.status_code == 200
    assert modes == ['AUTOCOMMIT', 'AUTOCOMMIT']
    with SessionLocal() as db:
        user = db.get(User,uid); original = user.full_name
        user.full_name = 'must rollback'; db.flush(); db.rollback()
    with SessionLocal() as db: assert db.get(User,uid).full_name == original


def test_session_list_uses_database_role_not_token_claim(setup):
    from app.auth import create_access_token
    client,uid,sid = setup
    app.dependency_overrides.clear()
    response = client.get(f'/api/v1/checkins/session/{sid}',headers={'Authorization':'Bearer '+create_access_token(uid,'admin')})
    assert response.status_code == 403
