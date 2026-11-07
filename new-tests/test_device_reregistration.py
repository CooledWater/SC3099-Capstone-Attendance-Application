"""Removed-device re-registration uses isolated SQLite, never the live database."""
import json
from test_device_binding import world, signed_register, sign, approve, session, proof, checkin
from app.database import SessionLocal
from app.models import AuditLog
from app import device_binding


def request(world, device):
    nonce = world[0].post('/api/v1/devices/registration-challenges', json={
        'device_fingerprint': device[2], 'public_key': device[1]})
    assert nonce.status_code == 201, nonce.text
    data = nonce.json()
    return {'device_fingerprint': device[2], 'public_key': device[1], 'reregister_removed': True,
            'registration_challenge_id': data['challenge_id'],
            'registration_signature': sign(device[0], data['challenge'])}


def test_removed_browser_returns_pending_preserving_history_and_revoked_proofs(world):
    client = world[0]
    device = signed_register(world)
    approve(world, device)
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).status_code == 201
    previous = client.get('/api/v1/checkins/my-checkins').json()
    other_session = session(world)
    old_proof = proof(world, device, other_session)
    assert client.delete('/api/v1/devices/' + device[3]).status_code == 204
    payload = request(world, device)
    response = client.post('/api/v1/devices/register', json=payload)
    assert response.status_code == 201, response.text
    restored = response.json()
    assert restored['id'] == device[3]
    assert restored['is_active'] is True and restored['is_removed'] is False
    assert restored['is_trusted'] is False and restored['approval_status'] == 'pending'
    assert client.get('/api/v1/checkins/my-checkins').json() == previous
    assert client.post('/api/v1/devices/register', json=payload).status_code == 409
    assert checkin(world, other_session, old_proof).status_code == 409
    assert checkin(world, other_session, proof(world, device, other_session)).json()['status'] == 'flagged'
    with SessionLocal() as db:
        assert db.get(device_binding.DeviceChallenge, old_proof['device_challenge_id']).state == 'revoked'
        assert any(json.loads(row.details or '{}').get('event') == 'device_reregistered'
                   for row in db.query(AuditLog).filter_by(device_id=device[3]))


def test_unsigned_request_cannot_restore_removed_device(world):
    device = signed_register(world)
    assert world[0].delete('/api/v1/devices/' + device[3]).status_code == 204
    response = world[0].post('/api/v1/devices/register', json={
        'device_fingerprint': device[2], 'public_key': device[1], 'reregister_removed': True})
    assert response.status_code == 403
    assert world[0].get('/api/v1/devices/my-devices').json()[0]['is_removed'] is True


def test_reregistration_cannot_exceed_device_limit(world):
    device = signed_register(world)
    assert world[0].delete('/api/v1/devices/' + device[3]).status_code == 204
    signed_register(world)
    signed_register(world)
    response = world[0].post('/api/v1/devices/register', json=request(world, device))
    assert response.status_code == 409
    rows = world[0].get('/api/v1/devices/my-devices').json()
    assert sum(row['is_active'] for row in rows) == 2
    assert next(row for row in rows if row['id'] == device[3])['is_removed'] is True


def test_explicit_reregistration_does_not_undo_admin_deactivation(world):
    client, current, ids = world
    device = signed_register(world)
    current[0] = ids[1]
    assert client.patch('/api/v1/devices/' + device[3], json={'is_active': False}).status_code == 200
    current[0] = ids[0]
    response = client.post('/api/v1/devices/register', json=request(world, device))
    assert response.status_code == 201
    assert response.json()['is_active'] is False
