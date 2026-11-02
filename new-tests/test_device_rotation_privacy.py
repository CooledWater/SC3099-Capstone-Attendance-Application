"""Isolated renewal and scheduled deletion regressions; never touches the live DB."""
from datetime import datetime, timedelta
import pytest
from test_device_binding import world, signed_register, key, sign, session
from app.database import SessionLocal
from app.models import User, Device, CheckIn, AuditLog, Enrollment
from app.device_binding import BrowserRegistration, DeviceChallenge
from app.device_rotation import KeyRotation
from app.data_deletion import purge_due_students
from app.auth import hash_password


def start(world, device, new_key):
    response = world[0].post('/api/v1/devices/key-rotation/challenges', json={'device_fingerprint': device[2], 'new_public_key': new_key[1]})
    assert response.status_code == 201, response.text
    item = response.json()
    return {'challenge_id': item['challenge_id'], 'old_signature': sign(device[0], item['challenge']), 'new_signature': sign(new_key[0], item['challenge'])}


def test_rotation_keeps_approvals_shared_history_and_rejects_old_proofs(world):
    device = signed_register(world)
    sid = session(world)
    issued = world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': device[2], 'session_id': sid}).json()
    world[1][0] = world[2][2]
    other = signed_register(world, device[:3])
    world[1][0] = world[2][0]
    with SessionLocal() as db:
        db.get(Device, device[3]).is_trusted = True
        db.commit()
    new_key = key()
    payload = start(world, device, new_key)
    assert world[0].post('/api/v1/devices/key-rotation/complete', json=payload).status_code == 200
    # Retrying a response lost over the network is idempotent.
    assert world[0].post('/api/v1/devices/key-rotation/complete', json=payload).status_code == 200
    with SessionLocal() as db:
        assert db.get(Device, device[3]).is_trusted is True
        assert db.get(Device, other[3]).is_trusted is False
        assert db.get(Device, device[3]).public_key == new_key[1]
        assert db.get(Device, other[3]).public_key == new_key[1]
        assert db.get(Device, device[3]).public_key_expires_at > datetime.utcnow() + timedelta(days=89)
        assert db.get(BrowserRegistration, device[3]).browser_fingerprint == device[2]
        assert db.get(DeviceChallenge, issued['challenge_id']).state == 'revoked'
    rows = world[0].get('/api/v1/devices/my-devices').json()
    assert rows[0]['shared_browser'] is True
    assert world[0].post('/api/v1/devices/registration-challenges', json={'device_fingerprint': device[2], 'public_key': device[1]}).status_code == 400
    # New signing key works with the stable browser identity, including account registration.
    signed_register(world, (new_key[0], new_key[1], device[2]))
    fresh = world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': device[2], 'session_id': sid}).json()
    response = world[0].post('/api/v1/checkins/', json={'session_id': sid, 'latitude': 1.3483, 'longitude': 103.6831,
        'device_fingerprint': device[2], 'device_challenge_id': fresh['challenge_id'], 'device_signature': sign(new_key[0], fresh['challenge'])})
    assert response.status_code == 201, response.text


def test_rotation_rejects_wrong_keys_other_accounts_and_expired_challenge(world):
    device = signed_register(world)
    replacement = key()
    payload = start(world, device, replacement)
    invalid = {**payload, 'old_signature': payload['new_signature']}
    assert world[0].post('/api/v1/devices/key-rotation/complete', json=invalid).status_code == 403
    world[1][0] = world[2][2]
    assert world[0].post('/api/v1/devices/key-rotation/complete', json=payload).status_code == 404
    world[1][0] = world[2][0]
    with SessionLocal() as db:
        db.get(KeyRotation, payload['challenge_id']).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert world[0].post('/api/v1/devices/key-rotation/complete', json=payload).status_code == 409
    with SessionLocal() as db:
        assert db.get(Device, device[3]).public_key == device[1]


def test_expired_key_blocks_checkin_but_allows_secure_renewal(world):
    device = signed_register(world)
    sid = session(world)
    with SessionLocal() as db:
        db.get(Device, device[3]).public_key_expires_at = datetime.utcnow() - timedelta(days=1)
        db.commit()
    assert world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': device[2], 'session_id': sid}).status_code == 403
    payload = start(world, device, key())
    assert world[0].post('/api/v1/devices/key-rotation/complete', json=payload).status_code == 200
    assert world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': device[2], 'session_id': sid}).status_code == 201


def password(world):
    with SessionLocal() as db:
        db.get(User, world[2][0]).hashed_password = hash_password('testpass123')
        db.commit()
    return {'password': 'testpass123'}


def test_deletion_requires_password_is_idempotent_and_cancellable(world):
    credentials = password(world)
    assert world[0].post('/api/v1/users/me/deletion-request', json={'password': 'wrong'}).status_code == 403
    response = world[0].post('/api/v1/users/me/deletion-request', json=credentials)
    assert response.status_code == 200, response.text
    date = response.json()['scheduled_deletion_at']
    assert datetime.fromisoformat(date) > datetime.utcnow() + timedelta(days=29)
    assert world[0].post('/api/v1/users/me/deletion-request', json=credentials).json()['scheduled_deletion_at'] == date
    assert world[0].get('/api/v1/users/me/deletion-request').json()['scheduled_deletion_at'] == date
    assert world[0].request('DELETE', '/api/v1/users/me/deletion-request', json=credentials).json()['scheduled_deletion_at'] is None
    world[1][0] = world[2][1]
    assert world[0].get('/api/v1/users/me/deletion-request').status_code == 403


def test_due_deletion_removes_personal_data_and_preserves_audit(world):
    credentials = password(world)
    device = signed_register(world)
    payload = start(world, device, key())
    sid = session(world)
    with SessionLocal() as db:
        db.add(CheckIn(student_id=world[2][0], session_id=sid, status='approved', risk_score=.1, latitude=1, longitude=2))
        db.commit()
        before = db.query(AuditLog).count()
    assert world[0].post('/api/v1/users/me/deletion-request', json=credentials).status_code == 200
    assert purge_due_students() == 0
    assert purge_due_students(now=datetime.utcnow() + timedelta(days=31)) == 1
    with SessionLocal() as db:
        user = db.get(User, world[2][0])
        assert user.is_active is False and user.full_name == 'Deleted student'
        assert user.email.endswith('@deleted.invalid') and user.face_embedding_hash is None
        assert not db.query(CheckIn).filter_by(student_id=user.id).count()
        assert not db.query(Device).filter_by(user_id=user.id).count()
        assert not db.query(KeyRotation).filter_by(user_id=user.id).count()
        assert not db.query(Enrollment).filter_by(student_id=user.id).count()
        assert db.query(AuditLog).count() >= before
        assert db.get(User, world[2][2]).is_active is True
    assert purge_due_students(now=datetime.utcnow() + timedelta(days=32)) == 0
