"""Dual-proof signing-key renewal without replacing a browser's account history."""
import uuid
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.auth import require_roles
from app.models import Device
from app.audit import create_audit_log
from app import device_binding as binding

KEY_LIFETIME = timedelta(days=90)


def key_expiry(device):
    if not device.public_key:
        return None
    return device.public_key_expires_at or (device.public_key_created_at or device.first_seen_at) + KEY_LIFETIME


class KeyRotation(Base):
    __tablename__ = 'device_key_rotations'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey('devices.id'), nullable=False)
    browser_fingerprint = Column(String(64), nullable=False)
    old_public_key = Column(String(1024), nullable=False)
    new_public_key = Column(String(1024), nullable=False)
    challenge = Column(String(512), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)


class RotationStart(BaseModel):
    device_fingerprint: str = Field(min_length=1, max_length=64)
    new_public_key: str = Field(min_length=1, max_length=1024)


class RotationComplete(BaseModel):
    challenge_id: str = Field(max_length=36)
    old_signature: str = Field(max_length=128)
    new_signature: str = Field(max_length=128)


def validate_browser_key(db, fingerprint, pem):
    actual = binding.key_fingerprint(pem)
    identity = db.get(binding.BrowserIdentity, fingerprint)
    if identity is not None:
        if identity.public_key != pem:
            raise HTTPException(400, 'Browser security key changed. Reload this app before continuing.')
    elif actual != fingerprint:
        raise HTTPException(400, 'Fingerprint must match the initial browser public key')


@binding.router.post('/key-rotation/challenges', status_code=201)
def start_rotation(payload: RotationStart, db: Session = Depends(get_db), user=Depends(require_roles('student'))):
    binding.enforce_rate_limit('key-renewal', user.id, 10, 3600)
    binding.lock_account(db, user.id)
    device = binding.find_device(db, user.id, payload.device_fingerprint)
    registration = db.get(binding.BrowserRegistration, device.id) if device else None
    if not device or not device.is_active or not device.public_key or not registration or not registration.verified_at:
        raise HTTPException(403, 'Register and verify this active browser before renewing its security key')
    identity = db.query(binding.BrowserIdentity).filter_by(fingerprint=registration.browser_fingerprint).with_for_update().one()
    new_fingerprint = binding.key_fingerprint(payload.new_public_key)
    if payload.new_public_key == identity.public_key or db.query(binding.BrowserIdentity).filter_by(public_key=payload.new_public_key).first():
        raise HTTPException(409, 'Generate a new browser security key')
    now = datetime.utcnow()
    db.query(KeyRotation).filter(KeyRotation.expires_at < now - timedelta(days=7)).delete(synchronize_session=False)
    item = KeyRotation(user_id=user.id, device_id=device.id, browser_fingerprint=identity.fingerprint,
        old_public_key=identity.public_key, new_public_key=payload.new_public_key,
        challenge=f'saiv-key-rotation-v1:{user.id}:{identity.fingerprint}:{new_fingerprint}:{uuid.uuid4()}',
        expires_at=now + timedelta(minutes=5))
    db.add(item); db.commit(); db.refresh(item)
    return {'challenge_id': item.id, 'challenge': item.challenge, 'expires_at': item.expires_at.isoformat() + 'Z'}


@binding.router.post('/key-rotation/complete')
def complete_rotation(payload: RotationComplete, db: Session = Depends(get_db), user=Depends(require_roles('student'))):
    binding.lock_account(db, user.id)
    item = db.query(KeyRotation).filter_by(id=payload.challenge_id, user_id=user.id).with_for_update().first()
    if item is None:
        raise HTTPException(404, 'Key renewal not found')
    identity = db.query(binding.BrowserIdentity).filter_by(fingerprint=item.browser_fingerprint).with_for_update().one()
    # Proof of both private keys is required, including retries after a lost response.
    binding.verify_signature(item.old_public_key, payload.old_signature, item.challenge)
    binding.verify_signature(item.new_public_key, payload.new_signature, item.challenge)
    if item.consumed_at:
        if identity.public_key != item.new_public_key:
            raise HTTPException(409, 'This browser key has already been renewed again')
        return {'rotated': True}
    now = datetime.utcnow()
    if item.expires_at <= now or identity.public_key != item.old_public_key:
        raise HTTPException(409, 'Key renewal expired or another tab already renewed it')
    device = db.get(Device, item.device_id)
    if not device or not device.is_active:
        raise HTTPException(403, 'This device registration is no longer active')
    rows = (db.query(Device).join(binding.BrowserRegistration, binding.BrowserRegistration.device_id == Device.id)
            .filter(binding.BrowserRegistration.browser_fingerprint == identity.fingerprint).order_by(Device.id)
            .with_for_update(of=Device).all())
    for row in rows:
        row.public_key = item.new_public_key
        row.public_key_created_at = now
        row.public_key_expires_at = now + KEY_LIFETIME
    identity.public_key = item.new_public_key
    ids = [row.id for row in rows]
    db.query(binding.DeviceChallenge).filter(binding.DeviceChallenge.device_id.in_(ids), binding.DeviceChallenge.state == 'issued').update({'state': 'revoked'}, synchronize_session=False)
    db.query(binding.RegistrationChallenge).filter_by(browser_fingerprint=identity.fingerprint, state='issued').update({'state': 'revoked'}, synchronize_session=False)
    item.consumed_at = now
    create_audit_log(db, 'device_registered', user.id, device.id, device_id=device.id, details={'event': 'security_key_rotated'})
    db.commit()
    return {'rotated': True}
