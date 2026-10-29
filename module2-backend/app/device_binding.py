"""Shared browser identities with per-account approval and single-use key proofs."""
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, or_, func
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.exceptions import InvalidSignature

from app.database import Base, get_db
from app.security import enforce_rate_limit
from app.auth import require_roles
from app.models import Device, User, Session as AttendanceSession, Enrollment


class DeviceChallenge(Base):
    __tablename__ = 'device_challenges'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey('devices.id'), nullable=False)
    session_id = Column(String(36), ForeignKey('sessions.id'), nullable=False)
    challenge = Column(String(512), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    state = Column(String(16), nullable=False, default='issued')


MAX_ACTIVE_DEVICES = 2
REMOVED_REASON = 'device_removed'


def is_removed(device):
    return device.revocation_reason == REMOVED_REASON


def managed_devices():
    # Keep historical device/browser associations while excluding removals from
    # management lists. Inactive registrations remain available for reactivation.
    return or_(Device.revocation_reason.is_(None), Device.revocation_reason != REMOVED_REASON)


LIMIT_MESSAGE = 'Your account already has two active devices. Login is allowed, but disable a device in Profile → My devices before registering or checking in on this browser.'


class BrowserIdentity(Base):
    __tablename__ = 'browser_identities'
    fingerprint = Column(String(64), primary_key=True)
    public_key = Column(String(1024), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BrowserRegistration(Base):
    __tablename__ = 'browser_registrations'
    device_id = Column(String(36), ForeignKey('devices.id'), primary_key=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    browser_fingerprint = Column(String(64), ForeignKey('browser_identities.fingerprint'), nullable=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint('user_id', 'browser_fingerprint', name='uq_browser_registration_account'),)


class RegistrationChallenge(Base):
    __tablename__ = 'device_registration_challenges'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    browser_fingerprint = Column(String(64), nullable=False)
    challenge = Column(String(512), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    state = Column(String(16), nullable=False, default='issued')


def account_fingerprint(user_id, browser_fingerprint):
    # Keep the existing globally unique device registration IDs and historical rows.
    # Cross-account linkage is stored separately in browser_registrations.
    return hashlib.sha256(f'saiv-account-device-v1:{user_id}:{browser_fingerprint}'.encode()).hexdigest()


def lock_account(db, user_id):
    # PostgreSQL serializes registration/reactivation for the same account.
    db.query(User).filter_by(id=user_id).with_for_update().one()


def active_count(db, user_id):
    return db.query(Device).filter_by(user_id=user_id, is_active=True).count()


def require_slot(db, user_id):
    if active_count(db, user_id) >= MAX_ACTIVE_DEVICES:
        raise HTTPException(409, LIMIT_MESSAGE)


def find_device(db, user_id, fingerprint):
    return (db.query(Device).outerjoin(BrowserRegistration, BrowserRegistration.device_id == Device.id)
            .filter(Device.user_id == user_id, or_(
                BrowserRegistration.browser_fingerprint == fingerprint,
                Device.device_fingerprint == fingerprint,
                Device.device_fingerprint == account_fingerprint(user_id, fingerprint)))
            .first())


def attach_browser(db, device, fingerprint, pem, verified=False):
    from sqlalchemy.exc import IntegrityError
    identity = db.get(BrowserIdentity, fingerprint)
    if identity is None:
        try:
            with db.begin_nested():
                db.add(BrowserIdentity(fingerprint=fingerprint, public_key=pem))
                db.flush()
        except IntegrityError:
            pass  # Another account registered this browser concurrently.
    # Serialize verified account associations for a shared browser.
    db.query(BrowserIdentity).filter_by(fingerprint=fingerprint).with_for_update().one()
    registration = db.get(BrowserRegistration, device.id)
    if registration is None:
        registration = BrowserRegistration(device_id=device.id, user_id=device.user_id, browser_fingerprint=fingerprint)
        db.add(registration)
    elif registration.browser_fingerprint != fingerprint:
        raise HTTPException(409, 'A registration cannot be moved to another browser identity')
    if verified:
        registration.verified_at = datetime.utcnow()
    db.flush()


def shared_fingerprints(db, fingerprints):
    if not fingerprints:
        return set()
    rows = (db.query(BrowserRegistration.browser_fingerprint)
            .join(User, User.id == BrowserRegistration.user_id)
            .filter(BrowserRegistration.browser_fingerprint.in_(fingerprints),
                    BrowserRegistration.verified_at.isnot(None), User.role == 'student')
            .group_by(BrowserRegistration.browser_fingerprint)
            .having(func.count(func.distinct(BrowserRegistration.user_id)) > 1).all())
    # Retain verified history even if a registration is later disabled.
    return {row[0] for row in rows}


def browser_metadata(db, devices):
    if not devices:
        return {}
    registrations = db.query(BrowserRegistration).filter(BrowserRegistration.device_id.in_([d.id for d in devices])).all()
    shared = shared_fingerprints(db, {item.browser_fingerprint for item in registrations})
    return {item.device_id: {'browser_fingerprint': item.browser_fingerprint,
                            'shared_browser': item.browser_fingerprint in shared,
                            'browser_identity_verified': item.verified_at is not None} for item in registrations}


def verify_signature(pem, signature_text, challenge):
    try:
        signature = base64.b64decode(signature_text, validate=True)
        if len(signature) != 64:
            raise ValueError('Invalid signature length')
        signature = utils.encode_dss_signature(int.from_bytes(signature[:32], 'big'), int.from_bytes(signature[32:], 'big'))
        key_fingerprint(pem)
        key = serialization.load_pem_public_key(pem.encode('ascii'))
        key.verify(signature, challenge.encode(), ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature):
        raise HTTPException(403, 'Device signature is invalid')


def consume_registration_proof(db, user_id, payload):
    if not payload.registration_challenge_id and not payload.registration_signature:
        return False  # Legacy registration never counts as proven account sharing.
    if not payload.registration_challenge_id or not payload.registration_signature or not payload.public_key:
        raise HTTPException(403, 'Registration proof is incomplete')
    item = db.get(RegistrationChallenge, payload.registration_challenge_id)
    if not item or item.user_id != user_id or item.browser_fingerprint != payload.device_fingerprint:
        raise HTTPException(403, 'Registration proof does not match this account and browser')
    if item.state != 'issued' or item.expires_at <= datetime.utcnow():
        raise HTTPException(409, 'Registration proof expired or already used')
    verify_signature(payload.public_key, payload.registration_signature, item.challenge)
    changed = db.query(RegistrationChallenge).filter_by(id=item.id, state='issued').filter(
        RegistrationChallenge.expires_at > datetime.utcnow()).update({'state': 'consumed'}, synchronize_session=False)
    if not changed:
        raise HTTPException(409, 'Registration proof expired or already used')
    return True


def key_fingerprint(pem):
    try:
        key = serialization.load_pem_public_key(pem.encode('ascii'))
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError('Use an ECDSA P-256 key')
        der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        return hashlib.sha256(der).hexdigest()
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(400, 'A valid ECDSA P-256 public key is required')


router = APIRouter(prefix='/api/v1/devices', tags=['devices'])


class ChallengeRequest(BaseModel):
    device_fingerprint: str = Field(min_length=1, max_length=64)
    session_id: str


class RegistrationRequest(BaseModel):
    device_fingerprint: str = Field(min_length=1, max_length=64)
    public_key: str = Field(min_length=1, max_length=1024)


@router.post('/registration-challenges', status_code=201)
def issue_registration(payload: RegistrationRequest, user: User = Depends(require_roles('student', 'ta', 'instructor', 'admin')), db: Session = Depends(get_db)):
    enforce_rate_limit('device-registration', user.id, 20, 60)
    if key_fingerprint(payload.public_key) != payload.device_fingerprint:
        raise HTTPException(400, 'Fingerprint does not match the public key')
    lock_account(db, user.id)
    if find_device(db, user.id, payload.device_fingerprint) is None:
        require_slot(db, user.id)
    now = datetime.utcnow()
    db.query(RegistrationChallenge).filter(RegistrationChallenge.expires_at < now).delete(synchronize_session=False)
    item = RegistrationChallenge(user_id=user.id, browser_fingerprint=payload.device_fingerprint,
        challenge=f'saiv-register-v1:{user.id}:{payload.device_fingerprint}:{secrets.token_urlsafe(32)}',
        expires_at=now + timedelta(minutes=2))
    db.add(item); db.commit(); db.refresh(item)
    return {'challenge_id': item.id, 'challenge': item.challenge, 'expires_at': item.expires_at.isoformat() + 'Z'}


@router.post('/challenges', status_code=201)
def issue(payload: ChallengeRequest, user: User = Depends(require_roles('student')), db: Session = Depends(get_db)):
    enforce_rate_limit('device-challenge', user.id, 20, 60)
    now = datetime.utcnow()
    device = find_device(db, user.id, payload.device_fingerprint)
    if not device or not device.is_active or not device.public_key:
        raise HTTPException(403, 'This device is unavailable or disabled. Manage it in Profile → My devices.')
    session = db.get(AttendanceSession, payload.session_id)
    if not session or session.status != 'active' or not session.checkin_opens_at <= now <= session.checkin_closes_at:
        raise HTTPException(400, 'Session is not open for check-in')
    if not db.query(Enrollment).filter_by(student_id=user.id, course_id=session.course_id, is_active=True).first():
        raise HTTPException(403, 'You are not enrolled in this course')
    db.query(DeviceChallenge).filter(DeviceChallenge.expires_at < now).delete(synchronize_session=False)
    item = DeviceChallenge(user_id=user.id, device_id=device.id, session_id=session.id,
        challenge=f'saiv-device-v1:{user.id}:{device.id}:{session.id}:{secrets.token_urlsafe(32)}',
        expires_at=min(now + timedelta(minutes=2), session.checkin_closes_at))
    db.add(item); db.commit(); db.refresh(item)
    return {'challenge_id': item.id, 'challenge': item.challenge, 'expires_at': item.expires_at.isoformat() + 'Z'}


def resolve(db, user, payload):
    # Lock against approval/revocation changes while the attendance is committed.
    lock_account(db, user.id)
    device = find_device(db, user.id, payload.device_fingerprint)
    active = active_count(db, user.id)
    if active > MAX_ACTIVE_DEVICES or (device is None and active >= MAX_ACTIVE_DEVICES):
        raise HTTPException(403, LIMIT_MESSAGE)
    if device and not device.is_active:
        raise HTTPException(403, 'This device is disabled. Manage it in Profile → My devices.')
    supplied = bool(payload.device_challenge_id or payload.device_signature)
    if not supplied:
        if active >= MAX_ACTIVE_DEVICES:
            raise HTTPException(403, 'Signed device proof is required when both device slots are in use. Manage devices in Profile → My devices.')
        # Legacy callers remain usable below the limit, but a claimed fingerprint never earns trust.
        return device, False, False
    if not device or not device.public_key or not payload.device_challenge_id or not payload.device_signature:
        raise HTTPException(403, 'Device proof is incomplete; retry check-in')
    item = db.get(DeviceChallenge, payload.device_challenge_id)
    if not item or item.user_id != user.id or item.device_id != device.id or item.session_id != payload.session_id:
        raise HTTPException(403, 'Device proof does not match this student and session')
    if item.state != 'issued' or item.expires_at <= datetime.utcnow():
        raise HTTPException(409, 'Device proof expired or already used; retry check-in')
    verify_signature(device.public_key, payload.device_signature, item.challenge)
    fingerprint = key_fingerprint(device.public_key)
    attach_browser(db, device, fingerprint, device.public_key, verified=True)
    changed = db.query(DeviceChallenge).filter_by(id=item.id, state='issued').filter(DeviceChallenge.expires_at > datetime.utcnow()).update({'state': 'consumed'}, synchronize_session=False)
    if not changed:
        raise HTTPException(409, 'Device proof expired or already used; retry check-in')
    device.attestation_passed = True
    device.last_attestation_at = datetime.utcnow()
    return device, True, fingerprint in shared_fingerprints(db, {fingerprint})


def apply_risk(biometrics, device, verified, shared=False):
    trusted = bool(device and device.is_active and device.is_trusted and verified and not shared)
    contribution = 0.0 if trusted else 0.20
    risk = biometrics.get('module3_risk')
    if risk:
        # Replace Module 3's placeholder device contribution; do not double count.
        breakdown = risk.signal_breakdown or {}
        if 'device' in breakdown:
            risk.risk_score = max(0.0, min(1.0, risk.risk_score - breakdown['device'] + contribution))
            breakdown['device'] = contribution
        else:
            risk.risk_score = max(0.0, min(1.0, risk.risk_score * 0.8 + contribution))
    return trusted, contribution
