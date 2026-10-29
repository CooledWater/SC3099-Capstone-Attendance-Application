"""Enrollment invitations and a durable email outbox; never persist setup links."""
import asyncio
import hashlib
import html
import os
import secrets
import smtplib
import ssl
import uuid
import time
from collections import OrderedDict
from threading import Lock
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.password_policy import validate_new_password
from sqlalchemy import Column, String, DateTime, ForeignKey, or_, and_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import Base, SessionLocal, get_db, get_read_db
from app.models import User, Course, Enrollment
from app.auth import ALGORITHM, JWT_SECRET, hash_password, require_roles
from app.audit import create_audit_log

router = APIRouter(prefix="/api/v1", tags=["invitations"])
TTL = timedelta(hours=24)
COOLDOWN = timedelta(seconds=60)
_request_windows = OrderedDict()
_request_lock = Lock()


class AccountInvitation(Base):
    __tablename__ = "account_invitations"
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    course_id = Column(String(36), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    nonce = Column(String(36), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    issued_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    delivery_status = Column(String(16), nullable=False, index=True)
    claimed_at = Column(DateTime, nullable=True)
    delivery_error = Column(String(255), nullable=True)


def setup_token(invitation):
    def epoch(value):
        return int(value.replace(tzinfo=timezone.utc).timestamp())
    return jwt.encode({"sub": invitation.user_id, "jti": invitation.nonce,
                       "type": "enrollment_invitation", "iat": epoch(invitation.issued_at),
                       "exp": epoch(invitation.expires_at)}, JWT_SECRET, algorithm=ALGORITHM)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def queue_invitation(db, user_id, course_id, invitation=None):
    now = datetime.utcnow().replace(microsecond=0)
    if invitation is None:
        invitation = AccountInvitation(user_id=user_id)
        db.add(invitation)
    invitation.course_id = course_id
    invitation.nonce = str(uuid.uuid4())
    invitation.issued_at = now
    invitation.expires_at = now + TTL
    invitation.used_at = None
    invitation.delivery_status = "queued"
    invitation.claimed_at = None
    invitation.delivery_error = None
    invitation.token_hash = digest(setup_token(invitation))
    return invitation


def invitation_result(invitation):
    if invitation is None or invitation.used_at is not None:
        return {"invitation_status": "not_needed", "invitation_pending": False}
    return {"invitation_status": invitation.delivery_status, "invitation_pending": True,
            "invitation_error": invitation.delivery_error}


def send_email(email, course_name, token):
    host = os.getenv("SMTP_HOST", "")
    sender = os.getenv("SMTP_FROM", "")
    origin = os.getenv("DASHBOARD_APP_URL", "http://localhost:8501").rstrip("/")
    parsed = urlparse(origin)
    if not host or not sender:
        raise ValueError("Email service is not configured")
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Student application URL is not configured correctly")
    link = f"{origin}/setup-account#token={token}"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = email
    message["Subject"] = "Set up your attendance account"
    message.set_content(f"You've been enrolled in {course_name}.\n\nSet your password:\n{link}\n\nThis single-use link expires in 24 hours. If you did not expect this invitation, you can ignore it.")
    message.add_alternative(f"<h2>You've been enrolled in {html.escape(course_name)}</h2><p>Set your password to access the attendance application.</p><p><a href=\"{html.escape(link, quote=True)}\">Set up my account</a></p><p>This single-use link expires in 24 hours.</p>", subtype="html")
    security = os.getenv("SMTP_SECURITY", "starttls")
    connection = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    with connection(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        if security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        elif security not in ("ssl", "none"):
            raise ValueError("Invalid email security setting")
        if os.getenv("SMTP_USERNAME"):
            smtp.login(os.environ["SMTP_USERNAME"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)


def deliver_next():
    """Claim one email, release the DB connection, then send. Recover stale claims."""
    now = datetime.utcnow()
    with SessionLocal() as db:
        invitation = db.query(AccountInvitation).filter(
            AccountInvitation.used_at.is_(None),
            or_(AccountInvitation.delivery_status == "queued", and_(
                AccountInvitation.delivery_status == "sending",
                AccountInvitation.claimed_at < now - timedelta(minutes=2))),
        ).order_by(AccountInvitation.issued_at).with_for_update(skip_locked=True).first()
        if invitation is None:
            return False
        user = db.get(User, invitation.user_id)
        course = db.get(Course, invitation.course_id) if invitation.course_id else None
        user_id, token_hash = invitation.user_id, invitation.token_hash
        token = setup_token(invitation)
        email, course_name = user.email if user else None, f"{course.code} - {course.name}" if course else "your course"
        eligible = user is not None and user.is_active and user.role == "student" and invitation.expires_at > now
        invitation.delivery_status = "sending"
        invitation.claimed_at = now
        db.commit()
    error = None
    try:
        if not eligible:
            raise ValueError("Invitation expired or account unavailable; request another invitation")
        if not secrets.compare_digest(digest(token), token_hash):
            raise ValueError("Invitation configuration changed; request another invitation")
        send_email(email, course_name, token)
    except Exception:
        # Never log SMTP exceptions: they can contain recipients, credentials or links.
        error = "Invitation could not be delivered. Check the email service and resend."
    with SessionLocal() as db:
        changed = db.query(AccountInvitation).filter(
            AccountInvitation.user_id == user_id, AccountInvitation.token_hash == token_hash,
            AccountInvitation.used_at.is_(None),
        ).update({"delivery_status": "failed" if error else "sent", "delivery_error": error}, synchronize_session=False)
        if changed:
            create_audit_log(db, "user_updated", resource_id=user_id, success=not error,
                             details={"invitation_status": "failed" if error else "sent"})
        db.commit()
    return True


async def invitation_clock():
    import logging
    while True:
        try:
            # Bound each pass and keep SMTP work outside the event loop.
            for _ in range(10):
                if not await run_in_threadpool(deliver_next):
                    break
        except Exception:
            logging.getLogger(__name__).warning("Invitation delivery temporarily unavailable")
        await asyncio.sleep(3)


class TokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=1024)


class CompleteRequest(TokenRequest):
    password: str = Field(min_length=8, max_length=72)

    @field_validator('password')
    @classmethod
    def strong_new_password(cls, value):
        return validate_new_password(value)


class ResendRequest(BaseModel):
    email: EmailStr
    course_id: str


class PublicRequest(BaseModel):
    email: EmailStr


def _pending(db, token, lock=False):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "enrollment_invitation":
            raise JWTError("Wrong token purpose")
    except JWTError:
        raise HTTPException(400, "This invitation is invalid or expired. Request a new invitation.")
    query = db.query(AccountInvitation).filter(AccountInvitation.token_hash == digest(token))
    if lock:
        query = query.with_for_update()
    invitation = query.first()
    if not invitation or invitation.used_at or invitation.expires_at <= datetime.utcnow():
        raise HTTPException(400, "This invitation is invalid, expired, or already used. Request a new invitation.")
    if payload.get("sub") != invitation.user_id or payload.get("jti") != invitation.nonce:
        raise HTTPException(400, "This invitation is invalid")
    user = db.get(User, invitation.user_id)
    if not user or not user.is_active or user.role != "student":
        raise HTTPException(400, "This invitation is unavailable")
    return invitation, user


@router.post("/auth/invitations/validate")
def validate(payload: TokenRequest, db: Session = Depends(get_read_db)):
    _, user = _pending(db, payload.token)
    return {"email": user.email}


@router.post("/auth/invitations/complete")
def complete(payload: CompleteRequest, db: Session = Depends(get_db)):
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(422, "Password must be at most 72 UTF-8 bytes")
    invitation, user = _pending(db, payload.token, lock=True)
    password_hash = hash_password(payload.password)
    # Conditional consumption is necessary even on SQLite, where FOR UPDATE is ignored.
    changed = db.query(AccountInvitation).filter(
        AccountInvitation.user_id == user.id, AccountInvitation.token_hash == digest(payload.token),
        AccountInvitation.used_at.is_(None), AccountInvitation.expires_at > datetime.utcnow(),
    ).update({"used_at": datetime.utcnow()}, synchronize_session=False)
    if not changed:
        raise HTTPException(400, "This invitation has already been used")
    user.hashed_password = password_hash
    email = user.email
    create_audit_log(db, "user_updated", user.id, user.id, details={"source": "enrollment_invitation", "password_set": True})
    db.commit()
    return {"email": email, "message": "Password set successfully"}


def course_access(db, current_user, course_id):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    if current_user.role != "admin" and course.instructor_id != current_user.id:
        raise HTTPException(403, "Insufficient permissions")


@router.get("/enrollments/course/{course_id}/invitations")
def statuses(course_id: str, current_user: User = Depends(require_roles("instructor", "admin", read_only=True)), db: Session = Depends(get_read_db)):
    course_access(db, current_user, course_id)
    rows = db.query(User.email, AccountInvitation).join(Enrollment, Enrollment.student_id == User.id).outerjoin(
        AccountInvitation, AccountInvitation.user_id == User.id,
    ).filter(Enrollment.course_id == course_id, Enrollment.is_active == True).all()
    return {"items": [{"email": email, **invitation_result(invitation)} for email, invitation in rows]}


@router.post("/enrollments/invitations/resend")
def resend(payload: ResendRequest, current_user: User = Depends(require_roles("instructor", "admin")), db: Session = Depends(get_db)):
    course_access(db, current_user, payload.course_id)
    row = db.query(AccountInvitation).join(User, User.id == AccountInvitation.user_id).join(
        Enrollment, Enrollment.student_id == User.id,
    ).filter(User.email == payload.email, User.is_active == True, User.role == "student", Enrollment.course_id == payload.course_id,
             Enrollment.is_active == True, AccountInvitation.used_at.is_(None)).with_for_update(of=AccountInvitation).first()
    if not row:
        raise HTTPException(400, "No pending account invitation for this enrollment")
    if row.issued_at > datetime.utcnow() - COOLDOWN:
        raise HTTPException(429, "Please wait one minute before resending", headers={"Retry-After": "60"})
    queue_invitation(db, row.user_id, payload.course_id, row)
    result = invitation_result(row)
    create_audit_log(db, "user_updated", current_user.id, row.user_id, details={"invitation_status": "queued"})
    db.commit()
    return result


@router.post("/auth/invitations/request")
def request_invitation(payload: PublicRequest, request: Request, db: Session = Depends(get_db)):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _request_lock:
        recent = [value for value in _request_windows.pop(key, []) if value > now - 60]
        if len(recent) >= 5:
            _request_windows[key] = recent
            raise HTTPException(429, "Please wait before requesting another invitation", headers={"Retry-After": "60"})
        _request_windows[key] = recent + [now]
        if len(_request_windows) > 10000:
            _request_windows.popitem(last=False)
    # Same response for unknown, completed, disabled, removed and pending accounts.
    row = db.query(AccountInvitation).join(User, User.id == AccountInvitation.user_id).filter(
        User.email == payload.email, User.is_active == True, User.role == "student",
        AccountInvitation.used_at.is_(None), AccountInvitation.issued_at <= datetime.utcnow() - COOLDOWN,
    ).with_for_update(of=AccountInvitation).first()
    if row and db.query(Enrollment.id).filter(Enrollment.student_id == row.user_id, Enrollment.is_active == True).first():
        queue_invitation(db, row.user_id, row.course_id, row)
        db.commit()
    return {"message": "If this account has a pending invitation, a new email will be sent. Please check your inbox."}
