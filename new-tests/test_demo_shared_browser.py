"""Demo sharing override, isolated SQLite; retains all browser associations."""
import pytest
from test_device_binding import world, key, signed_register, approve, session, proof, checkin
from app.database import SessionLocal
from app.models import CheckIn
from app import main
from app.face_service import LivenessResult


def shared_device(world):
    identity = key()
    first = signed_register(world, identity)
    approve(world, first)
    world[1][0] = world[2][2]
    signed_register(world, identity)
    world[1][0] = world[2][0]
    return first


def test_demo_bypasses_only_sharing_and_removing_override_restores_review(world, monkeypatch):
    monkeypatch.delenv('DEMO_ALLOW_SHARED_BROWSER', raising=False)
    device = shared_device(world)
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'flagged'
    monkeypatch.setenv('DEMO_ALLOW_SHARED_BROWSER', 'true')
    mine = world[0].get('/api/v1/devices/my-devices').json()[0]
    assert mine['shared_browser'] is True  # History remains intact.
    assert mine['shared_browser_review_required'] is False
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'approved'
    with SessionLocal() as db:
        row = db.query(CheckIn).filter_by(session_id=sid).one()
        assert 'device_shared' not in (row.risk_factors or '')
    monkeypatch.delenv('DEMO_ALLOW_SHARED_BROWSER')
    mine = world[0].get('/api/v1/devices/my-devices').json()[0]
    assert mine['shared_browser'] is True and mine['shared_browser_review_required'] is True
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'flagged'


def test_demo_still_requires_device_approval_and_signed_proof(world, monkeypatch):
    device = shared_device(world)
    monkeypatch.setenv('DEMO_ALLOW_SHARED_BROWSER', 'true')
    world[1][0] = world[2][1]
    assert world[0].patch('/api/v1/devices/' + device[3], json={'is_trusted': False}).status_code == 200
    world[1][0] = world[2][0]
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == 'flagged'
    approve(world, device)
    sid = session(world)
    payload = proof(world, device, sid)
    payload['device_signature'] = 'invalid'
    assert checkin(world, sid, payload).status_code == 403


@pytest.mark.parametrize('failed,expected', [(False, 'flagged'), (True, 'rejected')])
def test_demo_does_not_bypass_missing_or_failed_identity(world, monkeypatch, failed, expected):
    device = shared_device(world)
    monkeypatch.setenv('DEMO_ALLOW_SHARED_BROWSER', 'true')
    monkeypatch.setattr(main, '_run_biometric_verification', lambda *args: {
        'liveness': LivenessResult(False, .1, 'passive', None) if failed else None,
        'face_match': None, 'module3_risk': None, 'face_embedding_hash': None})
    sid = session(world)
    assert checkin(world, sid, proof(world, device, sid)).json()['status'] == expected
