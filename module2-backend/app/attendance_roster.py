"""Whole-session attendance roster; verification does not determine presence."""
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_read_db
from app.models import AuditLog, CheckIn, Course, Enrollment, Session as Meeting, User

router = APIRouter(prefix="/api/v1", tags=["attendance"])


def _iso(value):
    return value.isoformat() + "Z" if value else None


@router.get("/sessions/{session_id}/attendance")
def session_attendance(
    session_id: str,
    current_user: User = Depends(require_roles("instructor", "ta", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    row = (db.query(Meeting, Course).join(Course, Course.id == Meeting.course_id)
           .filter(Meeting.id == session_id).first())
    if not row:
        raise HTTPException(404, "Session not found")
    meeting, course = row
    # Matches the existing detail/review/export resource policy. TA assignments
    # are not represented in the current schema (see API specification).
    if current_user.role == "instructor" and not (
        course.instructor_id in (None, current_user.id)
        or meeting.instructor_id == current_user.id
    ):
        raise HTTPException(403, "Insufficient permissions")

    # Resolve lifecycle at read time, including between scheduler ticks.
    now = datetime.utcnow()
    lifecycle = meeting.status
    if lifecycle in ("scheduled", "active"):
        if meeting.scheduled_end <= now:
            lifecycle = "closed"
        elif meeting.scheduled_start <= now:
            lifecycle = "active"
    cutoff = min(now, meeting.scheduled_start)
    enrollments = (db.query(Enrollment, User).join(User, User.id == Enrollment.student_id)
                   .filter(Enrollment.course_id == course.id).all())
    events = defaultdict(list)
    for enrollment_id, action, timestamp in (
        db.query(AuditLog.resource_id, AuditLog.action, AuditLog.timestamp)
        .join(Enrollment, Enrollment.id == AuditLog.resource_id)
        .filter(Enrollment.course_id == course.id,
                AuditLog.action.in_(("enrollment_added", "enrollment_removed")),
                AuditLog.success.is_(True))
        .order_by(AuditLog.timestamp, AuditLog.id).all()
    ):
        events[enrollment_id].append((timestamp, action))

    students = {}
    for enrollment, student in enrollments:
        # Prefer the last immutable event at the session cutoff. Re-enrollment
        # overwrites enrolled_at/dropped_at, but cannot overwrite these events.
        history = events[enrollment.id]
        before = [action for timestamp, action in history if timestamp <= cutoff]
        eligible = (before[-1] == "enrollment_added") if before else (
            enrollment.enrolled_at <= cutoff
            and (enrollment.dropped_at is None or enrollment.dropped_at > cutoff)
            and (enrollment.is_active or enrollment.dropped_at is not None)
        )
        if eligible:
            students[student.id] = (student, None)

    # A recorded submission is evidence of presence even after a drop or a
    # re-enrollment whose earlier interval predates the available audit trail.
    for checkin, student in (db.query(CheckIn, User).join(User, User.id == CheckIn.student_id)
                             .filter(CheckIn.session_id == meeting.id).all()):
        students[student.id] = (student, checkin)

    closes_at = min(meeting.scheduled_end, meeting.actual_end) if meeting.actual_end else meeting.scheduled_end
    counts = {"present": 0, "absent": 0}
    verification = {name: 0 for name in ("pending", "approved", "flagged", "rejected", "appealed")}
    items = []
    for student, checkin in students.values():
        attendance = "present" if (
            checkin and meeting.scheduled_start <= checkin.checked_in_at < closes_at
            and checkin.checked_in_at <= now
        ) else "absent"
        counts[attendance] += 1
        if checkin:
            verification[checkin.status] += 1
        items.append({
            "student_id": student.id, "student_name": student.full_name,
            "student_email": student.email, "checkin_id": checkin.id if checkin else None,
            "attendance": attendance, "checked_in_at": _iso(checkin.checked_in_at) if checkin else None,
            "status": checkin.status if checkin else None,
            "risk_score": checkin.risk_score if checkin else None,
        })
    # Latest check-in first, missing records last, stable identity tie-breaker.
    items.sort(key=lambda item: (item["student_name"].casefold(), item["student_id"]))
    items.sort(key=lambda item: item["checked_in_at"] or "", reverse=True)
    expected = len(items)
    return {
        "session_id": meeting.id, "course_id": course.id, "session_status": lifecycle,
        "expected": expected, "items": items,
        "summary": {**counts, "verification": verification,
                    "attendance_rate": counts["present"] / expected if expected else 0.0},
        "policy": {"present_from": _iso(meeting.scheduled_start), "present_before": _iso(closes_at), "all_verification_statuses_count": True,
                   "roster_basis": "enrollment_at_start_with_audit_history_and_recorded_checkins"},
    }
