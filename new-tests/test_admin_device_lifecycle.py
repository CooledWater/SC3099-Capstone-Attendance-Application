"""Device deactivation/removal contracts using disposable local test data."""
import json

import pytest

from test_device_binding import world, register, signed_register, approve, session, proof, checkin
from app import device_binding
from app.auth import create_access_token
from app.database import SessionLocal
from app.models import AuditLog, CheckIn, Device


def admin_devices(world, params=""):
    response = world[0].get('/api/v1/devices/?user_id=' + world[2][0] + params, headers={
        'Authorization': 'Bearer ' + create_access_token(world[2][1], 'admin'),
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_deactivation_preserves_trust_and_remains_visible_for_reactivation(world):
    device = register(world)
    approve(world, device)
    client, current, ids = world
    current[0] = ids[1]
    response = client.patch('/api/v1/devices/' + device[3], json={'is_active': False})
    assert response.status_code == 200
    assert response.json()['is_active'] is False
    assert response.json()['is_trusted'] is True
    assert response.json()['trust_score'] == 'high'
    assert response.json()['is_removed'] is False
    assert admin_devices(world, '&is_active=false')['items'][0]['id'] == device[3]
    current[0] = ids[0]
    sid = session(world)
    assert checkin(world, sid, {'device_fingerprint': device[2]}).status_code == 403
    current[0] = ids[1]
    response = client.patch('/api/v1/devices/' + device[3], json={'is_active': True})
    assert response.status_code == 200 and response.json()['is_trusted'] is True
    current[0] = ids[0]
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'approved'


@pytest.mark.parametrize('caller', ['owner', 'admin'])
def test_removal_hides_registration_and_preserves_checkins_audit_and_browser_history(world, caller):
    device = signed_register(world)
    approve(world, device)
    client, current, ids = world
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).status_code == 201
    unused_sid = session(world)
    outstanding = proof(world, device, unused_sid)
    before = client.get('/api/v1/checkins/my-checkins').json()
    with SessionLocal() as db:
        row = db.query(CheckIn).filter_by(session_id=sid).one()
        snapshot = {column.name: getattr(row, column.name) for column in CheckIn.__table__.columns}
        old_audits = {row.id: row.details for row in db.query(AuditLog).all()}
    current[0] = ids[1] if caller == 'admin' else ids[0]
    assert client.delete('/api/v1/devices/' + device[3]).status_code == 204
    assert admin_devices(world)['items'] == []
    assert admin_devices(world)['total'] == 0
    assert admin_devices(world, '&is_active=false')['items'] == []
    current[0] = ids[0]
    assert client.get('/api/v1/checkins/my-checkins').json() == before
    # Module 1 receives the inactive record and cannot automatically re-register it.
    tombstone = next(row for row in client.get('/api/v1/devices/my-devices').json() if row['id'] == device[3])
    assert tombstone['is_active'] is False and tombstone['is_removed'] is True
    assert tombstone['is_trusted'] is False and tombstone['trust_score'] == 'low'
    response = client.post('/api/v1/devices/register', json={'device_fingerprint': device[2], 'public_key': device[1]})
    assert response.status_code == 201
    assert response.json()['is_active'] is False and response.json()['is_removed'] is True
    assert checkin(world, unused_sid, outstanding).status_code == 403
    with SessionLocal() as db:
        row = db.get(CheckIn, snapshot['id'])
        assert {column.name: getattr(row, column.name) for column in CheckIn.__table__.columns} == snapshot
        assert db.get(device_binding.BrowserRegistration, device[3]).verified_at is not None
        assert db.get(device_binding.DeviceChallenge, outstanding['device_challenge_id']).state == 'revoked'
        assert all(db.get(AuditLog, aid).details == details for aid, details in old_audits.items())
        assert any(json.loads(row.details or '{}').get('event') == 'device_removed'
                   for row in db.query(AuditLog).filter_by(device_id=device[3]).all())


def test_admin_can_restore_archived_device_without_restoring_trust_or_old_proofs(world):
    device = register(world)
    approve(world, device)
    client, current, ids = world
    sid = session(world)
    old_proof = proof(world, device, sid)
    assert client.delete('/api/v1/devices/' + device[3]).status_code == 204
    current[0] = ids[1]
    response = client.patch('/api/v1/devices/' + device[3], json={'is_active': True})
    assert response.status_code == 200
    assert response.json()['is_removed'] is False and response.json()['is_trusted'] is False
    assert admin_devices(world)['items'][0]['id'] == device[3]
    current[0] = ids[0]
    assert checkin(world, sid, old_proof).status_code == 409


def test_remove_inactive_device_and_forbid_unrelated_user(world):
    device = register(world)
    client, current, ids = world
    assert client.patch('/api/v1/devices/' + device[3], json={'is_active': False}).status_code == 200
    current[0] = ids[2]
    assert client.delete('/api/v1/devices/' + device[3]).status_code == 403
    current[0] = ids[1]
    assert client.delete('/api/v1/devices/' + device[3]).status_code == 204
    assert admin_devices(world)['items'] == []


def test_restore_cannot_bypass_active_device_limit(world):
    device = register(world)
    client, current, ids = world
    assert client.delete('/api/v1/devices/' + device[3]).status_code == 204
    register(world)
    register(world)
    current[0] = ids[1]
    assert client.patch('/api/v1/devices/' + device[3], json={'is_active': True}).status_code == 409
    with SessionLocal() as db:
        assert device_binding.is_removed(db.get(Device, device[3]))
