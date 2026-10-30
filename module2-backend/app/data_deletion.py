"""Password-confirmed student deletion scheduling and audit-preserving cleanup."""
import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import inspect, Table, MetaData
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.auth import require_roles, verify_password, hash_password
from app.database import SessionLocal, get_db
from app.models import User, CheckIn, Device, Enrollment
from app.audit import create_audit_log

router = APIRouter(prefix='/api/v1/users/me/deletion-request', tags=['student privacy'])


class PasswordConfirmation(BaseModel):
    password: str = Field(min_length=1, max_length=72)


def confirm_password(user, password):
    try:
        valid = len(password.encode('utf-8')) <= 72 and verify_password(password, user.hashed_password)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(403, 'Your password is incorrect')


def result(user):
    return {'scheduled_deletion_at': user.scheduled_deletion_at}


@router.get('')
def deletion_status(user=Depends(require_roles('student'))):
    return result(user)


@router.post('')
def request_deletion(payload: PasswordConfirmation, db: Session = Depends(get_db), user=Depends(require_roles('student'))):
    from app.device_binding import lock_account
    from app.security import enforce_rate_limit
    enforce_rate_limit('privacy-confirmation', user.id, 10, 3600)
    lock_account(db, user.id)
    user = db.query(User).filter_by(id=user.id).populate_existing().one()
    if not user.is_active or user.role != 'student':
        raise HTTPException(403, 'An active student account is required')
    confirm_password(user, payload.password)
    if user.scheduled_deletion_at is None:
        user.scheduled_deletion_at = datetime.utcnow() + timedelta(days=30)
        create_audit_log(db, 'user_updated', user.id, user.id, details={'event': 'data_deletion_requested'})
        db.commit()
    return result(user)


@router.delete('')
def cancel_deletion(payload: PasswordConfirmation, db: Session = Depends(get_db), user=Depends(require_roles('student'))):
    from app.device_binding import lock_account
    from app.security import enforce_rate_limit
    enforce_rate_limit('privacy-confirmation', user.id, 10, 3600)
    lock_account(db, user.id)
    user = db.query(User).filter_by(id=user.id).populate_existing().one()
    if not user.is_active or user.role != 'student':
        raise HTTPException(403, 'An active student account is required')
    confirm_password(user, payload.password)
    if user.scheduled_deletion_at and user.scheduled_deletion_at <= datetime.utcnow():
        raise HTTPException(409, 'Deletion is already due and can no longer be cancelled')
    if user.scheduled_deletion_at:
        user.scheduled_deletion_at = None
        create_audit_log(db, 'user_updated', user.id, user.id, details={'event': 'data_deletion_cancelled'})
        db.commit()
    return result(user)


def purge_due_students(factory=SessionLocal, now=None):
    from app.device_binding import BrowserIdentity, BrowserRegistration, DeviceChallenge, RegistrationChallenge
    from app.device_rotation import KeyRotation
    from app.motion import MotionChallenge
    from app.push_notifications import PushSubscription, PushDelivery
    now = now or datetime.utcnow()
    with factory() as db:
        users = db.query(User).filter(User.scheduled_deletion_at <= now, User.role == 'student').order_by(User.id).limit(10).with_for_update(skip_locked=True).all()
        for user in users:
            subscription_ids = [row[0] for row in db.query(PushSubscription.id).filter_by(user_id=user.id)]
            checkin_ids = [row[0] for row in db.query(CheckIn.id).filter_by(student_id=user.id)]
            db.query(PushDelivery).filter(PushDelivery.subscription_id.in_(subscription_ids) | PushDelivery.checkin_id.in_(checkin_ids)).delete(synchronize_session=False)
            db.query(PushSubscription).filter_by(user_id=user.id).delete(synchronize_session=False)
            db.query(MotionChallenge).filter_by(user_id=user.id).delete(synchronize_session=False)
            db.query(KeyRotation).filter_by(user_id=user.id).delete(synchronize_session=False)
            db.query(DeviceChallenge).filter_by(user_id=user.id).delete(synchronize_session=False)
            db.query(RegistrationChallenge).filter_by(user_id=user.id).delete(synchronize_session=False)
            fingerprints = [row[0] for row in db.query(BrowserRegistration.browser_fingerprint).filter_by(user_id=user.id)]
            db.query(BrowserRegistration).filter_by(user_id=user.id).delete(synchronize_session=False)
            # Some deployments include the documented risk_signals table in
            # addition to the mapped models. Remove its child records first.
            if inspect(db.get_bind()).has_table('risk_signals'):
                signals = Table('risk_signals', MetaData(), autoload_with=db.connection())
                db.execute(signals.delete().where(signals.c.checkin_id.in_(checkin_ids)))
            db.query(CheckIn).filter_by(student_id=user.id).delete(synchronize_session=False)
            db.query(Device).filter_by(user_id=user.id).delete(synchronize_session=False)
            db.query(Enrollment).filter_by(student_id=user.id).delete(synchronize_session=False)
            # Retired invitation metadata can still exist in older deployments.
            if inspect(db.get_bind()).has_table('account_invitations'):
                legacy = Table('account_invitations', MetaData(), autoload_with=db.connection())
                db.execute(legacy.delete().where(legacy.c.user_id == user.id))
            for fingerprint in fingerprints:
                if not db.query(BrowserRegistration).filter_by(browser_fingerprint=fingerprint).first():
                    db.query(BrowserIdentity).filter_by(fingerprint=fingerprint).delete(synchronize_session=False)
            # Keep an anonymous FK anchor so immutable audit/reviewer history remains valid.
            user.email = f'deleted-{user.id}@deleted.invalid'
            user.full_name = 'Deleted student'
            user.hashed_password = hash_password(secrets.token_urlsafe(32))
            user.face_embedding_hash = None; user.face_enrolled = False
            user.camera_consent = False; user.geolocation_consent = False
            user.last_login_at = None; user.is_active = False; user.scheduled_deletion_at = None
            create_audit_log(db, 'user_updated', None, user.id, details={'event': 'student_data_deleted'})
        db.commit()
        return len(users)


async def deletion_clock():
    while True:
        try:
            await run_in_threadpool(purge_due_students)
        except Exception:
            logging.getLogger(__name__).warning('Scheduled data cleanup unavailable; retrying')
        await asyncio.sleep(60)
