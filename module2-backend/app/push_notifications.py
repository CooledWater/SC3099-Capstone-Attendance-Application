"""Opt-in Web Push subscriptions and a transactional approval delivery outbox."""
import asyncio
import base64
import hashlib
import html
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, or_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import require_roles
from app.database import Base, SessionLocal, get_db
from app.models import CheckIn, User

router = APIRouter(prefix='/api/v1/push', tags=['push notifications'])
logger = logging.getLogger(__name__)


class PushSubscription(Base):
    __tablename__ = 'push_subscriptions'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    endpoint_hash = Column(String(64), unique=True, nullable=False)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(128), nullable=False)
    auth = Column(String(32), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PushDelivery(Base):
    __tablename__ = 'push_deliveries'
    __table_args__ = (UniqueConstraint('checkin_id', 'subscription_id'),)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    checkin_id = Column(String(36), ForeignKey('checkins.id', ondelete='CASCADE'), nullable=False)
    subscription_id = Column(String(36), ForeignKey('push_subscriptions.id', ondelete='CASCADE'), nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    claimed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def configuration():
    public = os.getenv('VAPID_PUBLIC_KEY', '')
    private = os.getenv('VAPID_PRIVATE_KEY', '')
    subject = os.getenv('VAPID_SUBJECT', '')
    return public, private, subject


def configured():
    return all(configuration())


def validate_endpoint(value):
    """Only browser push providers; never send user-chosen URLs to our network."""
    try:
        url = urlsplit(value)
        host = url.hostname or ''
        allowed = (host in ('fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com')
                   or host.endswith('.push.services.mozilla.com') or host.endswith('.push.apple.com')
                   or host.endswith('.notify.windows.com'))
        if (url.scheme != 'https' or not allowed or url.port not in (None, 443)
                or url.username or url.password or url.fragment or not url.path or '\\' in value):
            raise ValueError()
    except ValueError:
        raise ValueError('Use a supported HTTPS browser push endpoint') from None
    return value


def decode_key(value, length):
    try:
        raw = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
        if len(raw) != length:
            raise ValueError()
        return raw
    except (ValueError, TypeError):
        raise ValueError('Invalid push subscription key') from None


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=128)
    auth: str = Field(max_length=32)

    @field_validator('p256dh')
    @classmethod
    def public_key(cls, value):
        try:
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decode_key(value, 65))
        except ValueError:
            raise ValueError('Invalid push public key') from None
        return value

    @field_validator('auth')
    @classmethod
    def auth_key(cls, value):
        decode_key(value, 16)
        return value


class EndpointRequest(BaseModel):
    endpoint: str = Field(max_length=4096)

    @field_validator('endpoint')
    @classmethod
    def endpoint_url(cls, value):
        return validate_endpoint(value)


class SubscriptionRequest(EndpointRequest):
    keys: SubscriptionKeys


@router.get('/config')
def push_config(user=Depends(require_roles('student'))):
    return {'enabled': bool(configured()), 'public_key': configuration()[0] if configured() else None}


def delete_subscription(db, subscription):
    db.query(PushDelivery).filter_by(subscription_id=subscription.id).delete(synchronize_session=False)
    db.delete(subscription)
    db.flush()


@router.put('/subscriptions', status_code=204)
def subscribe(payload: SubscriptionRequest, db: Session = Depends(get_db), user=Depends(require_roles('student'))):
    if not configured():
        raise HTTPException(503, 'Push notifications are not configured')
    # Serialize per-account changes and bound registrations without limiting attendance devices.
    db.query(User).filter_by(id=user.id).with_for_update().first()
    digest = hashlib.sha256(payload.endpoint.encode()).hexdigest()
    current = db.query(PushSubscription).filter_by(endpoint_hash=digest).with_for_update().first()
    if current and (current.user_id != user.id or current.p256dh != payload.keys.p256dh or current.auth != payload.keys.auth):
        # A shared browser belongs only to the latest explicitly opted-in account.
        delete_subscription(db, current)
        current = None
    if current is None:
        if db.query(PushSubscription).filter_by(user_id=user.id).count() >= 10:
            raise HTTPException(409, 'Notification device limit reached. Disable notifications on another browser first.')
        current = PushSubscription(user_id=user.id, endpoint_hash=digest, endpoint=payload.endpoint,
                                   p256dh=payload.keys.p256dh, auth=payload.keys.auth)
        db.add(current)
    current.updated_at = datetime.utcnow()
    db.commit()
    return Response(status_code=204)


@router.post('/subscriptions/remove', status_code=204)
def unsubscribe(payload: EndpointRequest, db: Session = Depends(get_db), user=Depends(require_roles('student'))):
    current = db.query(PushSubscription).filter_by(
        endpoint_hash=hashlib.sha256(payload.endpoint.encode()).hexdigest(), user_id=user.id
    ).with_for_update().first()
    if current:
        delete_subscription(db, current)
    db.commit()
    return Response(status_code=204)


def queue_approval(db, checkin):
    """Called before review commit: approval and delivery jobs succeed together."""
    for subscription in db.query(PushSubscription).filter_by(user_id=checkin.student_id).all():
        db.add(PushDelivery(checkin_id=checkin.id, subscription_id=subscription.id))


def send_push(subscription, payload):
    from pywebpush import webpush
    from requests import Session as HTTPSession

    class NoRedirectSession(HTTPSession):
        def request(self, method, url, **kwargs):
            kwargs['allow_redirects'] = False
            return super().request(method, url, **kwargs)

    # Revalidate stored endpoints too; do not expose endpoints/keys in error logs.
    validate_endpoint(subscription['endpoint'])
    _, private, subject = configuration()
    with NoRedirectSession() as transport:
        response = webpush(subscription_info=subscription, data=json.dumps(payload, ensure_ascii=False),
                           vapid_private_key=private, vapid_claims={'sub': subject},
                           ttl=86400, timeout=10, requests_session=transport)
        if response.status_code >= 300:
            raise RuntimeError('Push provider did not accept delivery')


def provider_error_reason(error):
    """Retain known provider codes without logging arbitrary response contents."""
    response = getattr(error, 'response', None)
    try:
        reason = response.json().get('reason') if response is not None else None
    except (ValueError, AttributeError, TypeError):
        return 'unknown'
    known = {'BadJwtToken', 'BadVapidPublicKey', 'VapidPkHashMismatch',
             'BadAuthorizationHeader', 'BadTtl', 'BadWebPushRequest',
             'ExpiredToken', 'Unregistered'}
    return reason if isinstance(reason, str) and reason in known else 'unknown'


def deliver_one(factory=SessionLocal, sender=send_push, now=None):
    now = now or datetime.utcnow()
    if not configured():
        return False
    with factory() as db:
        job = db.query(PushDelivery).filter(
            PushDelivery.completed_at.is_(None), PushDelivery.available_at <= now,
            or_(PushDelivery.claimed_at.is_(None), PushDelivery.claimed_at < now - timedelta(minutes=2))
        ).order_by(PushDelivery.available_at).with_for_update(skip_locked=True).first()
        if job is None:
            return False
        subscription = db.get(PushSubscription, job.subscription_id)
        checkin = db.get(CheckIn, job.checkin_id)
        user = db.get(User, subscription.user_id) if subscription else None
        if (not subscription or not user or not user.is_active or not checkin or checkin.status != 'approved'
                or checkin.student_id != subscription.user_id or job.created_at < now - timedelta(days=1)):
            job.completed_at = now
            db.commit()
            return True
        job.claimed_at = now
        job.attempts += 1
        job_id, subscription_id, attempts = job.id, subscription.id, job.attempts
        info = {'endpoint': subscription.endpoint, 'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth}}
        payload = {'type': 'attendance-approved', 'user_id': subscription.user_id, 'checkin_id': checkin.id,
                   'title': 'Attendance approved',
                   'body': html.unescape(checkin.review_notes or '').strip()[:500]
                   or 'Your attendance has been approved. Tap to view your attendance.',
                   'url': '/dashboard/'}
        db.commit()
    # Release pooled DB connections while contacting the push provider.
    code = None
    succeeded = False
    try:
        sender(info, payload)
        succeeded = True
    except Exception as error:
        response = getattr(error, 'response', None)
        code = getattr(response, 'status_code', None)
        logger.warning('Push delivery failed; attempt=%s status=%s reason=%s',
                       attempts, code, provider_error_reason(error))
    with factory() as db:
        job = db.get(PushDelivery, job_id)
        if job is None:
            return True  # Disabled or switched accounts while delivery was in flight.
        if code in (404, 410):
            subscription = db.get(PushSubscription, subscription_id)
            if subscription:
                delete_subscription(db, subscription)
        elif succeeded or attempts >= 6:
            job.completed_at = now
        else:
            job.available_at = now + timedelta(seconds=min(3600, 30 * 2 ** (attempts - 1)))
            job.claimed_at = None
        db.commit()
    return True


async def push_clock():
    while True:
        try:
            for _ in range(20):
                if not await run_in_threadpool(deliver_one):
                    break
            with SessionLocal() as db:
                db.query(PushDelivery).filter(PushDelivery.created_at < datetime.utcnow() - timedelta(days=7)).delete()
                db.commit()
        except Exception:
            # Never log provider responses, subscription URLs, keys or payloads.
            logger.warning('Push outbox unavailable; retrying')
        await asyncio.sleep(5)
