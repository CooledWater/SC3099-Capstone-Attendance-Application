"""HTTP boundaries for the server-bound v2 challenge (isolated SQLite)."""
import itertools
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from backend_motion_cases import setup, frames, checkin
from app.database import SessionLocal
from app.models import User
from app.motion import MotionChallenge, MotionChallengeSpec, delete_challenges
from app.face_service import face_service


@pytest.mark.parametrize('target,direction,first', itertools.product((1, 2), ('left', 'right'), ('blink', 'head_turn')))
def test_all_issued_combinations_are_persisted_and_forwarded(setup, monkeypatch, target, direction, first):
    import app.motion as motion
    client, _, sid = setup
    choices = iter((target, direction, first))
    monkeypatch.setattr(motion.secrets, 'choice', lambda options: next(choices))
    response = client.post('/api/v1/motion/challenges', json={'session_id': sid})
    assert response.status_code == 201, response.text
    body = response.json()
    spec = dict(version=2, blink_target=target, turn_direction=direction, first_action=first)
    assert body['action'] == 'random_motion' and body['challenge'] == spec
    assert body['max_duration_ms'] == 8000 and body['max_frames'] == 120
    with SessionLocal() as db:
        assert db.get(MotionChallengeSpec, body['challenge_id']).descriptor() == spec
    captured = []
    def verify(path, payload, timeout):
        captured.append((path, payload, timeout))
        return SimpleNamespace(status_code=200, json=lambda: dict(
            passed=True, blink_count=target, turn_passed=True, completed_steps=2,
            challenge_version=2, liveness_score=.95, face_match_score=.98))
    monkeypatch.setattr(face_service, '_post', verify)
    result = client.post(f"/api/v1/motion/challenges/{body['challenge_id']}/verify", json=frames())
    assert result.status_code == 200, result.text
    assert result.json()['verification_id'] == body['challenge_id']
    assert captured[0][1]['challenge'] == spec
    attendance = client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=body['challenge_id']))
    assert attendance.status_code == 201, attendance.text
    assert attendance.json()['liveness_challenge_type'] == 'random_motion'


@pytest.mark.parametrize('extra', [{'challenge': {'version': 1}}, {'blink_target': 0}, {'action': 'blink_twice'}])
def test_client_cannot_select_requirements(setup, extra):
    client, _, sid = setup
    assert client.post('/api/v1/motion/challenges', json={'session_id': sid, **extra}).status_code == 422


def test_client_cannot_override_issued_requirements(setup):
    client, _, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json={**frames(), 'challenge': {'version': 1}}).status_code == 422


@pytest.mark.parametrize('state', ['issued', 'verified'])
def test_pending_legacy_challenges_cannot_verify_or_be_consumed(setup, state):
    client, uid, sid = setup
    with SessionLocal() as db:
        old = MotionChallenge(user_id=uid, session_id=sid, reference_hash='a'*64,
                              expires_at=datetime.utcnow()+timedelta(minutes=1), state=state,
                              result=json.dumps(dict(liveness_score=.95, face_match_score=.98)))
        db.add(old); db.commit(); cid = old.id
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 409
    assert client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid)).status_code == 409


@pytest.mark.parametrize('changes', [
    {'challenge_version': 1}, {'challenge_version': True}, {'turn_passed': False},
    {'turn_passed': 1}, {'completed_steps': 1}, {'completed_steps': True}, {'blink_count': 0},
    {'liveness_score': float('inf')},
])
def test_incomplete_or_malformed_service_success_never_issues_proof(setup, monkeypatch, changes):
    client, _, sid = setup
    body = dict(passed=True, blink_count=2, challenge_version=2, turn_passed=True,
                completed_steps=2, liveness_score=.95, face_match_score=.98)
    body.update(changes)
    monkeypatch.setattr(face_service, '_post', lambda *args: SimpleNamespace(status_code=200, json=lambda: body))
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 503
    assert client.post('/api/v1/checkins/', json=checkin(sid, motion_verification_id=cid)).status_code == 409


def test_retry_and_expiry_cleanup_remove_child_metadata(setup):
    client, _, sid = setup
    old = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    new = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with SessionLocal() as db:
        assert db.get(MotionChallengeSpec, old) is None
        db.get(MotionChallenge, new).expires_at = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
    current = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with SessionLocal() as db:
        assert db.get(MotionChallengeSpec, new) is None
        delete_challenges(db, db.query(MotionChallenge).filter_by(id=current)); db.commit()
        assert db.get(MotionChallengeSpec, current) is None


def test_enrollment_change_invalidates_spec_bound_verification(setup):
    client, uid, sid = setup
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with SessionLocal() as db:
        db.get(User, uid).face_embedding_hash = 'b'*64; db.commit()
    assert client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames()).status_code == 409


def test_concurrent_verification_claims_only_once(setup, monkeypatch):
    client, _, sid = setup
    entered, release = threading.Event(), threading.Event()
    original = face_service._post
    calls = []
    def delayed(*args, **kwargs):
        calls.append(True); entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(face_service, '_post', delayed)
    cid = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(client.post, f'/api/v1/motion/challenges/{cid}/verify', json=frames())
        assert entered.wait(5)
        try:
            second = client.post(f'/api/v1/motion/challenges/{cid}/verify', json=frames())
            assert second.status_code == 409, second.text
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200
    assert len(calls) == 1


def test_retry_during_verification_cannot_issue_old_proof(setup, monkeypatch):
    client, _, sid = setup
    entered, release = threading.Event(), threading.Event()
    original = face_service._post
    def delayed(*args, **kwargs):
        entered.set(); assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(face_service, '_post', delayed)
    old = client.post('/api/v1/motion/challenges', json={'session_id': sid}).json()['challenge_id']
    with ThreadPoolExecutor(2) as pool:
        verification = pool.submit(client.post, f'/api/v1/motion/challenges/{old}/verify', json=frames())
        assert entered.wait(5)
        try:
            fresh = client.post('/api/v1/motion/challenges', json={'session_id': sid})
            assert fresh.status_code == 201, fresh.text
        finally:
            release.set()
        assert verification.result(timeout=5).status_code == 409


def test_postgres_serializes_concurrent_issuance(setup):
    from app.database import engine
    if engine.dialect.name != 'postgresql':
        pytest.skip('Row-lock concurrency requires PostgreSQL')
    client, uid, sid = setup
    barrier = threading.Barrier(2)
    def issue():
        barrier.wait(timeout=5)
        return client.post('/api/v1/motion/challenges', json={'session_id': sid})
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: issue(), range(2)))
    assert [response.status_code for response in responses] == [201, 201]
    with SessionLocal() as db:
        current = db.query(MotionChallenge).filter_by(user_id=uid, session_id=sid).all()
        assert len(current) == 1
        assert db.query(MotionChallengeSpec).filter(MotionChallengeSpec.challenge_id.in_(
            [response.json()['challenge_id'] for response in responses])).count() == 1


def test_new_action_diagnostics_keep_only_allowed_scalar_fields():
    from app.checkin_diagnostics import sanitize, SERVICE_FIELDS
    result = sanitize({
        'challenge_version': 2, 'turn_passed': False, 'completed_steps': 1,
        'image': 'PRIVATE_IMAGE', 'challenge': {'reference_template_hash': 'PRIVATE_TEMPLATE'},
        'diagnostics': {'reason': 'wrong_direction', 'turn_passed': False,
                        'completed_steps': 1, 'pose_matrix': 'PRIVATE_LANDMARKS'},
    }, SERVICE_FIELDS['motion_sequence'])
    assert result == {'challenge_version': 2, 'turn_passed': False, 'completed_steps': 1,
                      'diagnostics': {'reason': 'wrong_direction', 'turn_passed': False, 'completed_steps': 1}}
