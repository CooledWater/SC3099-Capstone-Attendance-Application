"""Push ownership, atomic review jobs and retry regressions; no real push services."""
import base64
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import sessionmaker

from test_instructor_strict_scope import api
from app.main import app
from app.database import get_db
from app.models import CheckIn, User
from app import push_notifications as push


def encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def subscription(suffix='one'):
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    return {'endpoint': f'https://fcm.googleapis.com/fcm/send/{suffix}',
            'keys': {'p256dh': encode(key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)),
                     'auth': encode(b'a' * 16)}}


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv('VAPID_PUBLIC_KEY', 'public-test-key')
    monkeypatch.setenv('VAPID_PRIVATE_KEY', 'private-test-key')
    monkeypatch.setenv('VAPID_SUBJECT', 'mailto:test@example.com')


def database():
    return next(app.dependency_overrides[get_db]())


def approve(api, cid='c_a', uid='ia'):
    return api('POST', uid, f'/checkins/{cid}/review', json={'status': 'approved'})


def test_subscription_requires_student_auth_and_returns_no_secrets(api):
    assert api('GET', 'sa', '/push/config').json() == {'enabled': True, 'public_key': 'public-test-key'}
    assert api('PUT', 'ia', '/push/subscriptions', json=subscription()).status_code == 403
    payload = subscription()
    assert api('PUT', 'sa', '/push/subscriptions', json=payload).status_code == 204
    assert api('PUT', 'sa', '/push/subscriptions', json=payload).status_code == 204
    assert database().query(push.PushSubscription).count() == 1


@pytest.mark.parametrize('endpoint', ['http://fcm.googleapis.com/send/x', 'https://127.0.0.1/x',
    'https://fcm.googleapis.com.evil.test/x', 'https://user@fcm.googleapis.com/x',
    'https://fcm.googleapis.com:8000/x', 'https://fcm.googleapis.com/x#fragment'])
def test_push_endpoints_cannot_target_internal_or_arbitrary_services(api, endpoint):
    payload = subscription()
    payload['endpoint'] = endpoint
    response = api('PUT', 'sa', '/push/subscriptions', json=payload)
    assert response.status_code == 422
    assert payload['keys']['auth'] not in response.text


def test_invalid_subscription_keys_rejected(api):
    payload = subscription()
    payload['keys']['p256dh'] = encode(b'x' * 65)
    assert api('PUT', 'sa', '/push/subscriptions', json=payload).status_code == 422
    payload = subscription()
    payload['keys']['auth'] = 'bad'
    assert api('PUT', 'sa', '/push/subscriptions', json=payload).status_code == 422


def test_only_approval_of_subscribed_owner_creates_one_job_per_device(api):
    for owner, suffix in [('sa', 'one'), ('sa', 'two'), ('sb', 'other')]:
        assert api('PUT', owner, '/push/subscriptions', json=subscription(suffix)).status_code == 204
    assert approve(api).status_code == 200
    assert approve(api).status_code == 400
    db = database()
    assert db.query(push.PushDelivery).count() == 2
    assert all(row.checkin_id == 'c_a' for row in db.query(push.PushDelivery))
    assert api('POST', 'ia', '/checkins/c_c/review', json={'status': 'rejected'}).status_code == 200
    assert db.query(push.PushDelivery).count() == 2


def test_appeal_then_admin_approval_queues_push(api):
    db = database()
    checkin = db.get(CheckIn, 'c_a')
    checkin.status = 'rejected'
    checkin.checked_in_at = datetime.utcnow()
    db.commit()
    api('PUT', 'sa', '/push/subscriptions', json=subscription())
    assert api('POST', 'sa', '/checkins/c_a/appeal', json={'appeal_reason': 'GPS was inaccurate inside the lecture hall'}).status_code == 200
    assert db.query(push.PushDelivery).count() == 0
    assert approve(api, uid='admin').status_code == 200
    assert db.query(push.PushDelivery).count() == 1


def test_unauthorised_review_and_unsubscribed_students_never_queue(api):
    api('PUT', 'sa', '/push/subscriptions', json=subscription())
    assert approve(api, uid='ib').status_code == 403
    assert database().query(push.PushDelivery).count() == 0
    assert approve(api, cid='c_b', uid='ib').status_code == 200
    assert database().query(push.PushDelivery).count() == 0


def test_shared_browser_transfer_and_owner_only_unsubscribe_cancel_old_jobs(api):
    payload = subscription()
    api('PUT', 'sa', '/push/subscriptions', json=payload)
    approve(api)
    assert database().query(push.PushDelivery).count() == 1
    assert api('POST', 'sb', '/push/subscriptions/remove', json={'endpoint': payload['endpoint']}).status_code == 204
    assert database().query(push.PushSubscription).count() == 1
    assert api('PUT', 'sb', '/push/subscriptions', json=payload).status_code == 204
    db = database()
    assert db.query(push.PushSubscription).one().user_id == 'sb'
    assert db.query(push.PushDelivery).count() == 0
    api('POST', 'sb', '/push/subscriptions/remove', json={'endpoint': payload['endpoint']})
    assert db.query(push.PushSubscription).count() == 0


def test_delivery_payload_retry_and_success_survive_new_db_sessions(api):
    api('PUT', 'sa', '/push/subscriptions', json=subscription())
    approve(api)
    db = database()
    factory = sessionmaker(bind=db.get_bind())
    now = datetime.utcnow() + timedelta(seconds=1)
    calls = []
    def failure(info, payload):
        calls.append(payload)
        raise TimeoutError()
    assert push.deliver_one(factory, failure, now)
    db.expire_all()
    job = db.query(push.PushDelivery).one()
    assert job.attempts == 1 and job.completed_at is None
    assert not push.deliver_one(factory, failure, now + timedelta(seconds=1))
    assert push.deliver_one(factory, lambda info, payload: calls.append(payload), now + timedelta(seconds=31))
    db.expire_all()
    assert db.query(push.PushDelivery).one().completed_at is not None
    assert calls[0]['user_id'] == 'sa'
    assert calls[0]['type'] == 'attendance-approved'
    assert calls[0]['url'] == '/dashboard/'
    assert not any(key in calls[0] for key in ('email', 'review_notes', 'risk_factors', 'appeal_reason'))


@pytest.mark.parametrize('code', [404, 410])
def test_expired_provider_subscription_is_removed(api, code):
    api('PUT', 'sa', '/push/subscriptions', json=subscription())
    approve(api)
    db = database()
    def expired(info, payload):
        error = RuntimeError('Provider rejected endpoint')
        error.response = SimpleNamespace(status_code=code)
        raise error
    assert push.deliver_one(sessionmaker(bind=db.get_bind()), expired, datetime.utcnow() + timedelta(seconds=1))
    db.expire_all()
    assert db.query(push.PushSubscription).count() == 0
    assert db.query(push.PushDelivery).count() == 0


def test_approval_and_job_roll_back_together(api, monkeypatch):
    api('PUT', 'sa', '/push/subscriptions', json=subscription())
    db = database()
    real = push.queue_approval
    def failure(db, checkin):
        real(db, checkin)
        raise RuntimeError('Database failure before commit')
    monkeypatch.setattr(push, 'queue_approval', failure)
    with pytest.raises(RuntimeError):
        approve(api)
    db.rollback()
    assert db.get(CheckIn, 'c_a').status == 'flagged'
    assert db.query(push.PushDelivery).count() == 0


def test_disabled_configuration_does_not_accept_subscriptions(api, monkeypatch):
    monkeypatch.delenv('VAPID_PRIVATE_KEY')
    assert api('GET', 'sa', '/push/config').json() == {'enabled': False, 'public_key': None}
    assert api('PUT', 'sa', '/push/subscriptions', json=subscription()).status_code == 503


def test_real_webpush_encrypts_and_signs_without_following_redirects(monkeypatch):
    pytest.importorskip('pywebpush')
    import json
    import http_ece
    import requests
    receiver = ec.generate_private_key(ec.SECP256R1())
    signing = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setenv('VAPID_PRIVATE_KEY', encode(signing.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())))
    info = subscription()
    info['keys']['p256dh'] = encode(receiver.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    captured = []
    def transport(self, request, **kwargs):
        assert kwargs['allow_redirects'] is False
        assert kwargs['timeout'] == 10
        captured.append(request)
        response = requests.Response()
        response.status_code = 201
        response._content = b''
        return response
    monkeypatch.setattr(requests.Session, 'send', transport)
    push.send_push(info, {'type': 'attendance-approved', 'user_id': 'sa'})
    request = captured[0]
    assert request.headers['Authorization'].startswith('vapid ')
    assert request.headers['TTL'] == '86400'
    decoded = http_ece.decrypt(request.body, private_key=receiver, auth_secret=b'a' * 16, version='aes128gcm')
    assert json.loads(decoded) == {'type': 'attendance-approved', 'user_id': 'sa'}


def test_provider_error_reason_preserves_only_known_codes():
    error = RuntimeError()
    error.response = SimpleNamespace(json=lambda: {'reason': 'BadJwtToken'})
    assert push.provider_error_reason(error) == 'BadJwtToken'
    error.response = SimpleNamespace(json=lambda: {'reason': 'secret endpoint or key'})
    assert push.provider_error_reason(error) == 'unknown'
    error.response = SimpleNamespace(json=lambda: ['not-an-object'])
    assert push.provider_error_reason(error) == 'unknown'
    assert push.provider_error_reason(TimeoutError()) == 'unknown'


def test_setup_replaces_placeholder_without_rotating_keys(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    env = tmp_path / '.env'
    env.write_text('VAPID_PUBLIC_KEY=keep-public\nVAPID_PRIVATE_KEY=keep-private\n'
                   'VAPID_SUBJECT=mailto:attendance@example.test\nOTHER_SETTING=keep-me\n')
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'configure-push.py'
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, check=True, capture_output=True, text=True)
    settings = dict(line.split('=', 1) for line in env.read_text().splitlines() if '=' in line)
    assert settings['VAPID_PUBLIC_KEY'] == 'keep-public'
    assert settings['VAPID_PRIVATE_KEY'] == 'keep-private'
    assert settings['OTHER_SETTING'] == 'keep-me'
    assert settings['VAPID_SUBJECT'] == 'https://github.com/CooledWater/SC3099-Capstone-Attendance-Application'
    assert 'keep-private' not in result.stdout


@pytest.mark.parametrize('notes,expected', [
    (None, 'Your attendance has been approved. Tap to view your attendance.'),
    ('   ', 'Your attendance has been approved. Tap to view your attendance.'),
    ('GPS issue confirmed &amp; approved.', 'GPS issue confirmed & approved.'),
    ('Great work! ' + '🙂' * 600, ('Great work! ' + '🙂' * 600)[:500]),
])
def test_approval_body_uses_review_message_or_default(api, notes, expected):
    api('PUT', 'sa', '/push/subscriptions', json=subscription())
    assert approve(api).status_code == 200
    db = database()
    db.get(CheckIn, 'c_a').review_notes = notes
    db.commit()
    sent = []
    assert push.deliver_one(sessionmaker(bind=db.get_bind()), lambda info, payload: sent.append(payload),
                            datetime.utcnow() + timedelta(seconds=1))
    assert sent[0]['body'] == expected
    assert sent[0]['title'] == 'Attendance approved'
