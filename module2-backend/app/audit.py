"""Audit trail (F-AUDIT): event writer and the admin-only query endpoints.

Writing
-------
``create_audit_log(db, action, user_id, resource_id, ...)`` appends one
``audit_logs`` row (signature follows docs/INTEGRATION-GUIDE.md). By default it
only ``db.add``s the row, so it commits atomically with the caller's own
business change; pass ``commit=True`` for events that have no business
transaction (login failures, logout). A standalone write is best-effort: an
audit failure is logged and never turns a login into a 500.

``AuditContextMiddleware`` captures the caller's IP address and user agent in
a ContextVar so handlers need no extra ``Request`` parameter to log them.

Reading
-------
``GET /api/v1/audit/`` and ``GET /api/v1/audit/summary`` are admin only.
Each item carries the API-SPECIFICATION.md fields *and* the fields the
Module 4 dashboard (AuditLogs.tsx) reads (``occurred_at``, ``event_type``,
``actor_email``, ``severity``, ``detail``), so both consumers are served by one
response shape.
"""

import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_read_db
from app.models import AUDIT_ACTIONS, AuditLog, User

logger = logging.getLogger("saiv.audit")

router = APIRouter(prefix="/api/v1", tags=["audit"])

MAX_LIMIT = 1000
DEFAULT_LIMIT = 100
_MAX_DETAILS_CHARS = 4000

# Module 4's "event type" filter: a coarse category per action.
EVENT_TYPES = {
    "login_success": "authentication",
    "login_failed": "authentication",
    "logout": "authentication",
    "user_created": "user",
    "user_updated": "user",
    "checkin_attempted": "checkin",
    "checkin_approved": "checkin",
    "checkin_flagged": "checkin",
    "checkin_rejected": "checkin",
    "checkin_appealed": "checkin",
    "checkin_reviewed": "checkin",
    "session_created": "session",
    "session_updated": "session",
    "session_deleted": "session",
    "enrollment_added": "enrollment",
    "enrollment_removed": "enrollment",
    "device_registered": "device",
    "face_enrolled": "face",
    "data_exported": "export",
    "security_violation": "security",
}

_CRITICAL_ACTIONS = {"security_violation"}
_WARNING_ACTIONS = {"login_failed", "checkin_flagged", "checkin_rejected"}

# resource_type used when a caller does not name one.
_DEFAULT_RESOURCE_TYPES = {
    "checkin": "checkin",
    "session": "session",
    "user": "user",
    "enrollment": "enrollment",
    "device": "device",
    "face": "user",
}


# ---------------------------------------------------------------------------
# Request context (IP address / user agent)
# ---------------------------------------------------------------------------

_request_meta: ContextVar[tuple[str | None, str | None]] = ContextVar(
    "audit_request_meta", default=(None, None)
)


class AuditContextMiddleware:
    """Pure-ASGI middleware exposing the caller's IP / user agent to the writer.

    Only the direct peer address is used: X-Forwarded-For is client-controlled
    and would let a caller forge the address recorded in a compliance log.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        client = scope.get("client")
        ip_address = client[0][:45] if client and client[0] else None
        user_agent = None
        for name, value in scope.get("headers", []):
            if name == b"user-agent":
                user_agent = value.decode("latin-1")[:500]
                break

        token = _request_meta.set((ip_address, user_agent))
        try:
            await self.app(scope, receive, send)
        finally:
            _request_meta.reset(token)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def _encode_details(details: dict | None) -> str | None:
    if not details:
        return None
    encoded = json.dumps(details, default=str)
    if len(encoded) > _MAX_DETAILS_CHARS:
        # Keep the column valid JSON rather than cutting it mid-document.
        return json.dumps({"truncated": True})
    return encoded


def create_audit_log(
    db: Session,
    action: str,
    user_id: str | None = None,
    resource_id: str | None = None,
    *,
    resource_type: str | None = None,
    details: dict | None = None,
    success: bool = True,
    device_id: str | None = None,
    timestamp: datetime | None = None,
    commit: bool = False,
) -> AuditLog | None:
    """Append one audit row. Never put secrets, passwords or images in ``details``."""
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"Unknown audit action: {action}")

    if resource_type is None:
        resource_type = _DEFAULT_RESOURCE_TYPES.get(EVENT_TYPES[action])

    ip_address, user_agent = _request_meta.get()
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        device_id=device_id,
        details=_encode_details(details),
        success=success,
        timestamp=timestamp or datetime.utcnow(),
    )
    db.add(entry)

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not persist audit event %s", action)
            return None

    return entry


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _iso_utc(value: datetime) -> str:
    """Naive UTC datetime -> ISO-8601 with an explicit Z (JS `new Date()` safe)."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None).isoformat() + "Z"


def _severity(action: str, success: bool) -> str:
    if action in _CRITICAL_ACTIONS:
        return "critical"
    if action in _WARNING_ACTIONS or not success:
        return "warning"
    return "info"


def _load_details(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except ValueError:
        return {"raw": raw}
    return loaded if isinstance(loaded, dict) else {"value": loaded}


def _summarise(details: dict | None, resource_type: str | None, resource_id: str | None) -> str | None:
    parts = []
    for key, value in (details or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=str)
        parts.append(f"{key}={value}")
    text = ", ".join(parts)
    if not text and resource_type and resource_id:
        text = f"{resource_type} {resource_id}"
    return text[:300] or None


def _serialize(entry: AuditLog, user_email: str | None) -> dict:
    details = _load_details(entry.details)
    timestamp = _iso_utc(entry.timestamp)
    # Module 4 lowercases/escapes actor_email, so it must always be a string:
    # fall back to the address a failed login tried, then to "system".
    attempted_email = details.get("email") if details else None
    actor_email = user_email or (attempted_email if isinstance(attempted_email, str) else None) or "system"

    return {
        # API-SPECIFICATION.md fields
        "id": entry.id,
        "user_id": entry.user_id,
        "user_email": user_email,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "ip_address": entry.ip_address,
        "user_agent": entry.user_agent,
        "device_id": entry.device_id,
        "details": details,
        "success": entry.success,
        "timestamp": timestamp,
        # Module 4 (AuditLogs.tsx) fields
        "occurred_at": timestamp,
        "event_type": EVENT_TYPES.get(entry.action, "other"),
        "actor_email": actor_email,
        "severity": _severity(entry.action, entry.success),
        "detail": _summarise(details, entry.resource_type, entry.resource_id),
    }


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# ---------------------------------------------------------------------------
# Endpoints (admin only)
# ---------------------------------------------------------------------------

@router.get("/audit/")
def list_audit_logs(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    success: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    current_user: User = Depends(require_roles("admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    if action is not None and action not in AUDIT_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown action '{action}'"
        )

    start = _to_naive_utc(start_date) if start_date else None
    end = _to_naive_utc(end_date) if end_date else None
    if start and end and start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must not be after end_date"
        )

    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    query = db.query(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == str(user_id))
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if resource_type is not None:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        query = query.filter(AuditLog.resource_id == str(resource_id))
    if success is not None:
        query = query.filter(AuditLog.success == success)
    if start is not None:
        query = query.filter(AuditLog.timestamp >= start)
    if end is not None:
        query = query.filter(AuditLog.timestamp <= end)

    total = query.count()
    rows = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize(entry, email) for entry, email in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit/summary")
def audit_summary(
    days: int = Query(default=7, ge=1, le=3650),
    current_user: User = Depends(require_roles("admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    counts = (
        db.query(AuditLog.action, func.count())
        .filter(AuditLog.timestamp >= since)
        .group_by(AuditLog.action)
        .all()
    )
    by_action = {action: count for action, count in counts}

    return {
        "period_days": days,
        "total_logs": sum(by_action.values()),
        "by_action": by_action,
    }
