"""Device trust/approval rules on isolated SQLite (no live database).

1st device: HIGH, auto-approved. 2nd: LOW, pending until an admin approves (then HIGH).
3rd onwards: LOW, rejected by the two-device limit unless an admin explicitly overrides it.
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest

from test_device_binding import world, key, register, signed_register, approve, session, proof, checkin
from app import device_binding
from app.auth import create_access_token
from app.database import SessionLocal
from app.models import AuditLog, CheckIn, Course, Device, User, Session as AttendanceSession


def as_user(world, user_id):
    world[1][0] = user_id


def mine(world):
    return world[0].get('/api/v1/devices/my-devices').json()


def try_register(world, identity=None):
    _, pem, fingerprint = identity or key()
    return world[0].post('/api/v1/devices/register', json={'device_fingerprint': fingerprint, 'public_key': pem})


def list_as(world, user_id, role, params=''):
    # GET /devices/ authenticates through its read-only dependency, so send a real token.
    return world[0].get('/api/v1/devices/?user_id=' + world[2][0] + params,
                        headers={'Authorization': 'Bearer ' + create_access_token(user_id, role)})


def admin_list(world, params):
    response = list_as(world, world[2][1], 'admin', params)
    assert response.status_code == 200, response.text
    return response.json()


def staff_user(role):
    with SessionLocal() as db:
        user = User(email=f'{uuid.uuid4()}@example.com', full_name=role, role=role, hashed_password='unused')
        db.add(user); db.commit()
        return user.id


def third_device(world):
    while len([d for d in mine(world) if d['is_active']]) < device_binding.MAX_ACTIVE_DEVICES:
        register(world)
    identity = key()
    response = try_register(world, identity)
    assert response.status_code == 409
    assert 'two active devices' in response.json()['detail']
    with SessionLocal() as db:
        row = db.query(Device).filter_by(user_id=world[2][0], revocation_reason=device_binding.LIMIT_REASON).one()
        return (*identity, row.id)


def test_first_device_is_high_and_auto_approved(world):
    device = register(world)
    row = mine(world)[0]
    assert (row['is_trusted'], row['trust_score'], row['approval_status'], row['is_active']) == (True, 'high', 'approved', True)
    sid = session(world)
    response = checkin(world, sid, proof(world, device, sid))
    assert response.status_code == 201 and response.json()['status'] == 'approved', response.text


def test_first_device_auto_approval_applies_to_legacy_registration(world):
    # Same shape as the graded test_device fixture: no public key.
    response = world[0].post('/api/v1/devices/', json={'device_fingerprint': 'legacy_' + uuid.uuid4().hex[:8], 'device_name': 'Test Device', 'platform': 'web'})
    assert response.status_code == 201
    assert response.json()['trust_score'] == 'high' and response.json()['approval_status'] == 'approved'


def test_second_device_is_low_pending_and_becomes_high_when_approved(world):
    register(world)
    second = register(world)
    row = next(d for d in mine(world) if d['id'] == second[3])
    assert (row['is_trusted'], row['trust_score'], row['approval_status'], row['is_active']) == (False, 'low', 'pending', True)
    assert [d['id'] for d in admin_list(world, '&approval_status=pending')['items']] == [second[3]]
    # While pending, signed check-ins are accepted but flagged for low device trust.
    sid = session(world)
    response = checkin(world, sid, proof(world, second, sid))
    assert response.status_code == 201 and response.json()['status'] == 'flagged', response.text
    with SessionLocal() as db:
        row = db.query(CheckIn).filter_by(session_id=sid).one()
        assert 'device_unknown' in row.risk_factors
    approve(world, second)
    row = next(d for d in mine(world) if d['id'] == second[3])
    assert (row['is_trusted'], row['trust_score'], row['approval_status']) == (True, 'high', 'approved')
    # After approval, device trust no longer flags the check-in.
    sid = session(world)
    response = checkin(world, sid, proof(world, second, sid))
    assert response.status_code == 201 and response.json()['status'] == 'approved', response.text


def test_third_and_later_devices_are_rejected_but_kept_for_review(world):
    third = third_device(world)
    fourth = try_register(world)
    assert fourth.status_code == 409
    rows = {d['id']: d for d in mine(world)}
    assert len(rows) == 4
    assert (rows[third[3]]['trust_score'], rows[third[3]]['is_trusted'], rows[third[3]]['is_active'], rows[third[3]]['approval_status']) == ('low', False, False, 'rejected')
    assert admin_list(world, '&approval_status=rejected')['total'] == 2
    assert admin_list(world, '&approval_status=inactive')['total'] == 0
    with SessionLocal() as db:
        assert device_binding.active_count(db, world[2][0]) == 2
        logs = db.query(AuditLog).filter_by(device_id=third[3]).all()
        assert any('device_limit_rejected' in (log.details or '') for log in logs)


def test_limit_rejection_queue_is_capped(world):
    register(world); register(world)
    for _ in range(device_binding.MAX_LIMIT_REJECTIONS + 2):
        assert try_register(world).status_code == 409
    _, pem, fingerprint = key()
    assert world[0].post('/api/v1/devices/registration-challenges', json={'device_fingerprint': fingerprint, 'public_key': pem}).status_code == 409
    with SessionLocal() as db:
        assert device_binding.limit_rejection_count(db, world[2][0]) == device_binding.MAX_LIMIT_REJECTIONS


def test_repeated_registration_from_same_device_does_not_increase_count(world):
    private, pem, fingerprint = key()
    for _ in range(3):
        response = world[0].post('/api/v1/devices/register', json={'device_fingerprint': fingerprint, 'public_key': pem})
        assert response.status_code == 201
    signed_register(world, (private, pem, fingerprint))  # A later login re-runs signed registration.
    assert len(mine(world)) == 1
    second = register(world)
    assert next(d for d in mine(world) if d['id'] == second[3])['approval_status'] == 'pending'
    third = key()
    assert try_register(world, third).status_code == 409
    assert try_register(world, third).status_code == 409  # Retrying the rejected browser adds no row.
    assert len(mine(world)) == 3


def test_rejected_third_device_cannot_check_in_but_pending_second_can(world):
    first = register(world)
    second = register(world)
    third = key()
    assert try_register(world, third).status_code == 409
    sid = session(world)
    challenge = lambda fp: world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': fp, 'session_id': sid})
    assert challenge(third[2]).status_code == 403
    assert 'rejected' in challenge(third[2]).json()['detail']
    assert checkin(world, sid, {'device_fingerprint': third[2]}).status_code == 403
    assert checkin(world, sid, {'device_fingerprint': 'unregistered'}).status_code == 403
    # Unsigned check-ins stay blocked when both slots are in use (HEAD rule).
    assert checkin(world, sid, {'device_fingerprint': second[2]}).status_code == 403
    response = checkin(world, sid, proof(world, second, sid))
    assert response.status_code == 201 and response.json()['status'] == 'flagged', response.text
    sid = session(world)
    response = checkin(world, sid, proof(world, first, sid))
    assert response.status_code == 201 and response.json()['status'] == 'approved', response.text


def test_admin_deactivated_pending_device_cannot_check_in(world):
    register(world)
    second = register(world)
    client, current, ids = world
    current[0] = ids[1]
    assert client.patch('/api/v1/devices/' + second[3], json={'is_active': False}).status_code == 200
    current[0] = ids[0]
    sid = session(world)
    assert checkin(world, sid, {'device_fingerprint': second[2]}).status_code == 403


def test_rejected_request_becomes_pending_when_a_slot_frees(world):
    register(world)
    second = register(world)
    third = key()
    assert try_register(world, third).status_code == 409
    assert world[0].patch('/api/v1/devices/' + second[3], json={'is_active': False}).status_code == 200
    response = try_register(world, third)
    assert response.status_code == 201
    assert (response.json()['approval_status'], response.json()['trust_score']) == ('pending', 'low')
    # The replacement device behaves like any pending second device: allowed, but flagged.
    sid = session(world)
    response = checkin(world, sid, proof(world, third + (response.json()['id'],), sid))
    assert response.status_code == 201 and response.json()['status'] == 'flagged', response.text


def test_admin_override_approves_third_device_with_high_trust(world):
    first = register(world)
    third = third_device(world)
    client, current, ids = world
    current[0] = ids[1]
    # Without an explicit override, the two-device limit still applies.
    assert client.patch('/api/v1/devices/' + third[3], json={'is_active': True}).status_code == 409
    assert client.patch('/api/v1/devices/' + third[3], json={'is_active': True, 'is_trusted': True}).status_code == 409
    assert client.patch('/api/v1/devices/' + third[3], json={'override_device_limit': True}).status_code == 400
    response = client.patch('/api/v1/devices/' + third[3], json={'is_trusted': True, 'override_device_limit': True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body['is_active'], body['is_trusted'], body['trust_score'], body['approval_status']) == (True, True, 'high', 'approved')
    current[0] = ids[0]
    with SessionLocal() as db:
        assert device_binding.active_count(db, ids[0]) == 3
        logs = db.query(AuditLog).filter_by(device_id=third[3], user_id=ids[1]).all()
        assert sum('device_limit_override' in (log.details or '') for log in logs) == 1
    sid = session(world)
    response = checkin(world, sid, proof(world, third, sid))
    assert response.status_code == 201 and response.json()['status'] == 'approved', response.text
    # The approved exception does not lock the student's other approved device out.
    sid = session(world)
    assert checkin(world, sid, proof(world, first, sid)).status_code == 201
    # Students still cannot add another device through normal registration.
    assert try_register(world).status_code == 409


@pytest.mark.parametrize('role', ['student_owner', 'other_student', 'instructor', 'ta'])
def test_non_admins_cannot_approve_or_override(world, role):
    register(world)
    second = register(world)
    third = third_device(world) if role == 'student_owner' else None
    client, current, ids = world
    if role == 'other_student':
        current[0] = ids[2]
    elif role in ('instructor', 'ta'):
        current[0] = staff_user(role)
    for target in filter(None, [second, third]):
        assert client.patch('/api/v1/devices/' + target[3], json={'is_trusted': True}).status_code == 403
        assert client.patch('/api/v1/devices/' + target[3], json={'is_trusted': True, 'override_device_limit': True}).status_code == 403
    response = list_as(world, current[0], 'student' if 'student' in role else role, '&approval_status=pending')
    assert response.status_code == 403 and response.json()['detail'] != 'Not authenticated'
    with SessionLocal() as db:
        assert db.get(Device, second[3]).is_trusted is False


def test_owner_override_flag_is_admin_only_even_when_not_approving(world):
    device = register(world)
    response = world[0].patch('/api/v1/devices/' + device[3], json={'device_name': 'x', 'override_device_limit': False})
    assert response.status_code == 403


def test_device_approval_grants_no_course_access(world):
    device = register(world)
    client, current, ids = world
    with SessionLocal() as db:
        course = Course(code=str(uuid.uuid4())[:8], name='Other', semester='Test', instructor_id=ids[1], venue_latitude=1.3483, venue_longitude=103.6831)
        db.add(course); db.flush()
        now = datetime.utcnow()
        row = AttendanceSession(course_id=course.id, instructor_id=ids[1], name='Other', status='active', scheduled_start=now - timedelta(minutes=1),
            scheduled_end=now + timedelta(hours=1), checkin_opens_at=now - timedelta(minutes=1), checkin_closes_at=now + timedelta(hours=1))
        db.add(row); db.commit()
        sid = row.id
    response = world[0].post('/api/v1/devices/challenges', json={'device_fingerprint': device[2], 'session_id': sid})
    assert response.status_code == 403 and 'not enrolled' in response.json()['detail']
    assert checkin(world, sid, {'device_fingerprint': device[2]}).status_code == 400


def test_student_with_no_devices_keeps_legacy_checkin(world):
    # Graded tests check in with an unregistered fingerprint for a brand-new student.
    sid = session(world)
    response = checkin(world, sid, {'device_fingerprint': 'test_device_' + uuid.uuid4().hex[:8]})
    assert response.status_code == 201
    assert response.json()['status'] in ('pending', 'approved', 'flagged')
    assert mine(world) == []


postgres_only = pytest.mark.skipif(not os.getenv('DEVICE_TEST_DATABASE_URL', '').startswith('postgres'), reason='PostgreSQL row-lock concurrency test')


@postgres_only
def test_concurrent_first_registrations_produce_one_high_device(world):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    def request(identity):
        barrier.wait(timeout=10)
        return try_register(world, identity).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(request, [key(), key()])) == [201, 201]
    with SessionLocal() as db:
        rows = db.query(Device).filter_by(user_id=world[2][0]).all()
        assert sorted(row.trust_score for row in rows) == ['high', 'low']
        assert sum(row.is_trusted for row in rows) == 1


@postgres_only
def test_concurrent_registrations_at_limit_cannot_add_active_devices(world):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    register(world); register(world)
    # Two concurrent requests, like the other lock tests: each test request holds two pooled
    # connections (auth + handler) and the PostgreSQL pool is capped at three.
    barrier = Barrier(2)
    def request(identity):
        barrier.wait(timeout=10)
        return try_register(world, identity).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(request, [key(), key()])) == [409, 409]
    with SessionLocal() as db:
        assert device_binding.active_count(db, world[2][0]) == 2
        assert device_binding.limit_rejection_count(db, world[2][0]) == 2
