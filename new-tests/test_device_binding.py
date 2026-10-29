"""Isolated SQLite HTTP regressions; no live database or biometric service."""
import os
import sys
import tempfile
import uuid
import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

os.environ['DATABASE_URL'] = os.getenv('DEVICE_TEST_DATABASE_URL') or 'sqlite:///' + tempfile.mktemp(prefix='saiv-device-', suffix='.db')
os.environ['JWT_SECRET'] = 'isolated-device-test-secret'
os.environ['STRICT_SECURITY_MODE'] = 'false'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'module2-backend'))
from fastapi.testclient import TestClient
from app import main, device_binding
from app.database import SessionLocal
from app.auth import get_current_user
from app.models import User, Device, Course, Enrollment, CheckIn, Session as AttendanceSession
from app.face_service import LivenessResult, FaceMatchResult, RiskResult


def key():
    private = ec.generate_private_key(ec.SECP256R1())
    der = private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return private, pem, hashlib.sha256(der).hexdigest()


@pytest.fixture
def world(monkeypatch):
    with SessionLocal() as db:
        student = User(email=f'{uuid.uuid4()}@example.com', full_name='Student', role='student', hashed_password='unused', camera_consent=True, geolocation_consent=True)
        admin = User(email=f'{uuid.uuid4()}@example.com', full_name='Admin', role='admin', hashed_password='unused')
        other = User(email=f'{uuid.uuid4()}@example.com', full_name='Other', role='student', hashed_password='unused')
        db.add_all([student, admin, other]); db.flush()
        course = Course(code=str(uuid.uuid4())[:8], name='Course', semester='Test', instructor_id=admin.id, venue_latitude=1.3483, venue_longitude=103.6831)
        db.add(course); db.flush()
        db.add(Enrollment(student_id=student.id, course_id=course.id))
        ids = [student.id, admin.id, other.id, course.id]
        db.commit()
    current = [ids[0]]
    def auth():
        with SessionLocal() as db:
            yield db.get(User, current[0])
    main.app.dependency_overrides[get_current_user] = auth
    def biometrics(*args):
        return {'liveness': LivenessResult(True, .98, 'passive', None), 'face_match': FaceMatchResult(True, .98, None), 'module3_risk': RiskResult(.11, 'LOW', {'device': .1}, []), 'face_embedding_hash': None}
    monkeypatch.setattr(main, '_run_biometric_verification', biometrics)
    monkeypatch.setattr(main.motion, 'consume', biometrics)
    with TestClient(main.app) as client:
        yield client, current, ids
    main.app.dependency_overrides.clear()


def session(world):
    client, current, ids = world
    with SessionLocal() as db:
        now = datetime.utcnow()
        row = AttendanceSession(course_id=ids[3], instructor_id=ids[1], name='Open', status='active', scheduled_start=now-timedelta(minutes=1), scheduled_end=now+timedelta(hours=1), checkin_opens_at=now-timedelta(minutes=1), checkin_closes_at=now+timedelta(hours=1), require_liveness_check=True, require_face_match=True)
        db.add(row); db.commit(); db.refresh(row)
        return row.id


def register(world):
    private, pem, fingerprint = key()
    result = world[0].post('/api/v1/devices/register', json={'device_fingerprint': fingerprint, 'public_key': pem, 'platform': 'web', 'device_name': 'My browser'})
    assert result.status_code == 201, result.text
    return private, pem, fingerprint, result.json()['id']


def proof(world, device, sid):
    private, _, fingerprint, _ = device
    response = world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': fingerprint, 'session_id': sid})
    assert response.status_code == 201, response.text
    item = response.json()
    signature = private.sign(item['challenge'].encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(signature)
    signature = base64.b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).decode()
    return {'device_fingerprint': fingerprint, 'device_challenge_id': item['challenge_id'], 'device_signature': signature}


def checkin(world, sid, payload):
    return world[0].post('/api/v1/checkins/', json={'session_id': sid, 'latitude': 1.3483, 'longitude': 103.6831, **payload})


def approve(world, device):
    client, current, ids = world
    current[0] = ids[1]
    result = client.patch('/api/v1/devices/' + device[3], json={'is_trusted': True})
    current[0] = ids[0]
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('motion', [False, True])
def test_pending_flags_approved_passes_and_counts(world, motion):
    device = register(world)
    sid = session(world)
    payload = proof(world, device, sid)
    if motion: payload['motion_verification_id'] = str(uuid.uuid4())
    response = checkin(world, sid, payload)
    assert response.status_code == 201, response.text
    assert response.json()['status'] == 'flagged'
    approve(world, device)
    sid = session(world)
    response = checkin(world, sid, proof(world, device, sid))
    assert response.json()['status'] == 'approved', response.text
    with SessionLocal() as db:
        assert db.get(Device, device[3]).total_checkins == 2
        assert db.query(CheckIn).filter_by(session_id=sid).one().device_id == device[3]


def test_student_cannot_self_approve_or_edit_others(world):
    device = register(world)
    assert world[0].patch('/api/v1/devices/' + device[3], json={'is_trusted': True}).status_code == 403
    world[1][0] = world[2][2]
    assert world[0].patch('/api/v1/devices/' + device[3], json={'device_name': 'Stolen'}).status_code == 403
    assert world[0].delete('/api/v1/devices/' + device[3]).status_code == 403


def test_disable_remove_and_reregistration_never_restore_trust(world):
    device = register(world)
    approve(world, device)
    assert world[0].delete('/api/v1/devices/' + device[3]).status_code == 204
    response = world[0].post('/api/v1/devices/register', json={'device_fingerprint': device[2], 'public_key': device[1]})
    assert response.status_code == 201
    assert response.json()['is_active'] is False
    assert response.json()['is_trusted'] is False
    sid = session(world)
    assert checkin(world, sid, {'device_fingerprint': device[2]}).status_code == 403
    response = world[0].patch('/api/v1/devices/' + device[3], json={'is_active': True})
    assert response.json()['is_trusted'] is False


def test_signature_cannot_be_forged_replayed_or_moved_to_another_session(world):
    device = register(world)
    sid = session(world)
    payload = proof(world, device, sid)
    forged = {**payload, 'device_signature': base64.b64encode(b'x' * 64).decode()}
    assert checkin(world, sid, forged).status_code == 403
    other_sid = session(world)
    assert checkin(world, other_sid, payload).status_code == 403
    assert checkin(world, sid, payload).status_code == 201
    with SessionLocal() as db:
        # Remove only scratch attendance to exercise proof replay rather than duplicate guard.
        db.query(CheckIn).filter_by(session_id=sid).delete(); db.commit()
    assert checkin(world, sid, payload).status_code == 409


def test_expired_proof_rejected_and_claimed_trusted_fingerprint_not_enough(world):
    device = register(world)
    approve(world, device)
    sid = session(world)
    payload = proof(world, device, sid)
    with SessionLocal() as db:
        db.get(device_binding.DeviceChallenge, payload['device_challenge_id']).expires_at = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
    assert checkin(world, sid, payload).status_code == 409
    response = checkin(world, sid, {'device_fingerprint': device[2]})
    assert response.json()['status'] == 'flagged'


def test_multiple_devices_and_registration_is_idempotent(world):
    first = register(world); second = register(world)
    response = world[0].post('/api/v1/devices/register', json={'device_fingerprint': first[2], 'public_key': first[1]})
    assert response.json()['id'] == first[3]
    assert len(world[0].get('/api/v1/devices/my-devices').json()) == 2
    assert first[3] != second[3]


def test_untrusted_device_does_not_override_biometric_rejection(world, monkeypatch):
    device = register(world)
    monkeypatch.setattr(main, '_run_biometric_verification', lambda *args: {'liveness': LivenessResult(False, .1, 'passive', None), 'face_match': None, 'module3_risk': None, 'face_embedding_hash': None})
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'rejected'


def test_trusted_device_cannot_bypass_missing_identity_evidence(world, monkeypatch):
    device = register(world); approve(world, device)
    monkeypatch.setattr(main, '_run_biometric_verification', lambda *args: {'liveness': None, 'face_match': None, 'module3_risk': None, 'face_embedding_hash': None})
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'flagged'


def test_key_substitution_and_cross_account_proof_fail(world):
    device = register(world)
    _, different_pem, _ = key()
    assert world[0].post('/api/v1/devices/register', json={'device_fingerprint': device[2], 'public_key': different_pem}).status_code == 400
    sid = session(world)
    payload = proof(world, device, sid)
    world[1][0] = world[2][2]
    assert world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': device[2], 'session_id': sid}).status_code == 403
    assert world[0].patch('/api/v1/devices/' + device[3], json={'is_active': False}).status_code == 403


def sign(private, challenge):
    der = private.sign(challenge.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return base64.b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).decode()


def signed_register(world, identity=None):
    private, pem, fingerprint = identity or key()
    response = world[0].post('/api/v1/devices/registration-challenges', json={'device_fingerprint': fingerprint, 'public_key': pem})
    assert response.status_code == 201, response.text
    nonce = response.json()
    response = world[0].post('/api/v1/devices/register', json={'device_fingerprint': fingerprint, 'public_key': pem, 'device_name': 'Browser',
        'registration_challenge_id': nonce['challenge_id'], 'registration_signature': sign(private, nonce['challenge'])})
    assert response.status_code == 201, response.text
    assert response.json()['browser_fingerprint'] == fingerprint
    assert response.json()['browser_identity_verified'] is True
    return (private, pem, fingerprint, response.json()['id'])


def test_third_registration_blocked_but_management_and_existing_checkins_work(world):
    first = register(world); second = register(world)
    private, pem, fingerprint = key()
    response = world[0].post('/api/v1/devices/register', json={'device_fingerprint': fingerprint, 'public_key': pem})
    assert response.status_code == 409
    assert 'two active devices' in response.json()['detail']
    assert len(world[0].get('/api/v1/devices/my-devices').json()) == 2
    sid = session(world)
    assert checkin(world, sid, {'device_fingerprint': fingerprint}).status_code == 403
    assert checkin(world, sid, {'device_fingerprint': first[2]}).status_code == 403
    assert checkin(world, sid, proof(world, first, sid)).status_code == 201
    assert world[0].patch('/api/v1/devices/' + second[3], json={'is_active': False}).status_code == 200
    third = signed_register(world, (private, pem, fingerprint))
    assert world[0].patch('/api/v1/devices/' + second[3], json={'is_active': True}).status_code == 409
    assert world[0].delete('/api/v1/devices/' + third[3]).status_code == 204
    response = world[0].patch('/api/v1/devices/' + second[3], json={'is_active': True})
    assert response.status_code == 200
    assert response.json()['is_trusted'] is False


def test_shared_browser_has_separate_account_approvals_but_flags_both(world):
    identity = key()
    first = signed_register(world, identity)
    approve(world, first)
    world[1][0] = world[2][2]  # Other student proves possession of the SAME browser key.
    second = signed_register(world, identity)
    assert second[3] != first[3]
    mine = world[0].get('/api/v1/devices/my-devices').json()
    assert len(mine) == 1 and mine[0]['shared_browser'] is True
    assert mine[0]['is_trusted'] is False  # Never inherit another account's approval.
    assert 'user_email' not in mine[0]
    world[1][0] = world[2][0]
    sid = session(world)
    result = checkin(world, sid, proof(world, first, sid))
    assert result.status_code == 201, result.text
    assert result.json()['status'] == 'flagged'
    with SessionLocal() as db:
        row = db.query(CheckIn).filter_by(session_id=sid).one()
        assert 'device_shared' in row.risk_factors
    # Disabling/removing the second account's registration cannot erase proven sharing history.
    world[1][0] = world[2][2]
    assert world[0].delete('/api/v1/devices/' + second[3]).status_code == 204
    world[1][0] = world[2][0]
    mine = world[0].get('/api/v1/devices/my-devices').json()
    assert mine[0]['shared_browser'] is True


def test_copying_public_key_without_signature_cannot_falsely_mark_browser_shared(world):
    first = signed_register(world)
    approve(world, first)
    world[1][0] = world[2][2]
    response = world[0].post('/api/v1/devices/register', json={'device_fingerprint': first[2], 'public_key': first[1]})
    assert response.status_code == 201
    assert response.json()['browser_identity_verified'] is False
    world[1][0] = world[2][0]
    assert world[0].get('/api/v1/devices/my-devices').json()[0]['shared_browser'] is False
    sid = session(world)
    assert checkin(world, sid, proof(world, first, sid)).json()['status'] == 'approved'


def test_registration_proof_is_account_bound_expiring_and_single_use(world):
    private, pem, fingerprint = key()
    nonce = world[0].post('/api/v1/devices/registration-challenges', json={'device_fingerprint': fingerprint, 'public_key': pem}).json()
    payload = {'device_fingerprint': fingerprint, 'public_key': pem, 'registration_challenge_id': nonce['challenge_id'], 'registration_signature': sign(private, nonce['challenge'])}
    world[1][0] = world[2][2]
    assert world[0].post('/api/v1/devices/register', json=payload).status_code == 403
    world[1][0] = world[2][0]
    assert world[0].post('/api/v1/devices/register', json=payload).status_code == 201
    assert world[0].post('/api/v1/devices/register', json=payload).status_code == 409
    nonce = world[0].post('/api/v1/devices/registration-challenges', json={'device_fingerprint': fingerprint, 'public_key': pem}).json()
    payload.update(registration_challenge_id=nonce['challenge_id'], registration_signature=sign(private, nonce['challenge']))
    with SessionLocal() as db:
        db.get(device_binding.RegistrationChallenge, nonce['challenge_id']).expires_at = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
    assert world[0].post('/api/v1/devices/register', json=payload).status_code == 409


@pytest.mark.skipif(not os.getenv('DEVICE_TEST_DATABASE_URL', '').startswith('postgres'), reason='PostgreSQL row-lock concurrency test')
def test_concurrent_registration_cannot_exceed_two_slots(world):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    register(world)
    identities = [key(), key()]
    barrier = Barrier(2)
    def request(identity):
        barrier.wait(timeout=10)
        return world[0].post('/api/v1/devices/register', json={'device_fingerprint': identity[2], 'public_key': identity[1]}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(request, identities))
    assert sorted(results) == [201, 409]
    with SessionLocal() as db:
        assert device_binding.active_count(db, world[2][0]) == 2


@pytest.mark.skipif(not os.getenv('DEVICE_TEST_DATABASE_URL', '').startswith('postgres'), reason='PostgreSQL row-lock concurrency test')
def test_concurrent_reactivation_cannot_exceed_two_slots(world):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    first = register(world); second = register(world)
    for device in (first, second):
        assert world[0].patch('/api/v1/devices/' + device[3], json={'is_active': False}).status_code == 200
    register(world)
    barrier = Barrier(2)
    def request(device):
        barrier.wait(timeout=10)
        return world[0].patch('/api/v1/devices/' + device[3], json={'is_active': True}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(request, [first, second]))
    assert sorted(results) == [200, 409]
    with SessionLocal() as db:
        assert device_binding.active_count(db, world[2][0]) == 2
