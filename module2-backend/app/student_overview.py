"""Student-owned overview metrics, distinct from staff presence statistics."""
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_read_db
from app.models import AuditLog, CheckIn, Course, Enrollment, Session as Meeting, User

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])
SGT = timezone(timedelta(hours=8))


def utc_iso(value):
    return value.isoformat() + "Z"


def reporting_period(now):
    raw = os.getenv("SEMESTER_START_DATE", "")
    try:
        start = datetime.combine(date.fromisoformat(raw), time.min, SGT).astimezone(timezone.utc).replace(tzinfo=None)
        if start > now:
            raise ValueError()
    except ValueError:
        return None, "Configure SEMESTER_START_DATE to the current semester's start date."
    return start, None


def lifecycle(meeting, now):
    if meeting.status in ("scheduled", "active"):
        if meeting.scheduled_end <= now:
            return "closed"
        if meeting.scheduled_start <= now:
            return "active"
    return meeting.status


def eligible(enrollment, history, instant):
    # Match the roster's immutable-history policy. Never use current active
    # enrollment alone to decide whether a past session was expected.
    before = [action for timestamp, action in history if timestamp <= instant]
    if before:
        return before[-1] == "enrollment_added"
    return (enrollment.enrolled_at <= instant
            and (enrollment.dropped_at is None or enrollment.dropped_at > instant)
            and (enrollment.is_active or enrollment.dropped_at is not None))


def overview(db, student_id, section="all", course_id=None, now=None):
    now = now or datetime.utcnow()
    result = {"as_of": utc_iso(now)}
    # Unique(student_id, session_id) is authoritative. Latest timestamp then ID
    # is a deterministic fallback for imported legacy duplicate attempts.
    checkins = {}
    if section != "today":
        for record in (db.query(CheckIn).filter(CheckIn.student_id == student_id)
                       .order_by(CheckIn.checked_in_at.desc(), CheckIn.id.desc()).all()):
            checkins.setdefault(record.session_id, record)
    if section in ("all", "flagged"):
        flagged = sum(record.status == "flagged" for record in checkins.values())
        appealed = sum(record.status == "appealed" for record in checkins.values())
        result["flagged"] = {"total": flagged + appealed, "flagged": flagged, "appealed": appealed}
    if section == "flagged":
        return result

    enrolled = (db.query(Enrollment, Course).join(Course, Course.id == Enrollment.course_id)
                .filter(Enrollment.student_id == student_id).order_by(Course.code).all())
    by_course = {course.id: (enrollment, course) for enrollment, course in enrolled}
    current = [(enrollment, course) for enrollment, course in enrolled if enrollment.is_active]
    events = defaultdict(list)
    for enrollment_id, action, timestamp in (
        db.query(AuditLog.resource_id, AuditLog.action, AuditLog.timestamp)
        .join(Enrollment, Enrollment.id == AuditLog.resource_id)
        .filter(Enrollment.student_id == student_id, AuditLog.success.is_(True),
                AuditLog.action.in_(("enrollment_added", "enrollment_removed")))
        .order_by(AuditLog.timestamp, AuditLog.id).all()
    ):
        events[enrollment_id].append((timestamp, action))

    local_today = now.replace(tzinfo=timezone.utc).astimezone(SGT).date()
    midnight = datetime.combine(local_today, time.min, SGT)
    today_start = midnight.astimezone(timezone.utc).replace(tzinfo=None)
    today_end = (midnight + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
    semester_start, period_error = reporting_period(now)
    lower = min(semester_start, today_start) if semester_start else today_start
    meetings = (db.query(Meeting).filter(Meeting.course_id.in_(list(by_course)),
                Meeting.scheduled_start >= lower, Meeting.scheduled_start < today_end)
                .order_by(Meeting.scheduled_start, Meeting.id).all()) if by_course else []
    eligible_meetings = []
    for meeting in meetings:
        enrollment, course = by_course[meeting.course_id]
        if eligible(enrollment, events[enrollment.id], meeting.scheduled_start):
            eligible_meetings.append((meeting, course))

    if section in ("all", "today"):
        items = []
        for meeting, course in eligible_meetings:
            state = lifecycle(meeting, now)
            if today_start <= meeting.scheduled_start < today_end and state != "cancelled":
                items.append({"id": meeting.id, "course_id": course.id, "course_code": course.code,
                              "name": meeting.name, "venue_name": meeting.venue_name,
                              "scheduled_start": utc_iso(meeting.scheduled_start),
                              "scheduled_end": utc_iso(meeting.scheduled_end), "status": state})
        result["today"] = {"date": local_today.isoformat(), "start": utc_iso(today_start),
                           "end": utc_iso(today_end), "total": len(items),
                           "active": sum(item["status"] == "active" for item in items),
                           "upcoming": sum(item["status"] == "scheduled" for item in items),
                           "completed": sum(item["status"] == "closed" for item in items), "sessions": items}

    if section in ("all", "attendance"):
        permitted = {course.id for _, course in current}
        if course_id and course_id not in permitted:
            raise HTTPException(403, "Choose one of your enrolled courses")
        selected = course_id or (current[0][1].id if current else None)
        result["courses"] = [{"id": course.id, "code": course.code, "name": course.name,
                              "semester": course.semester} for _, course in current]
        result["period"] = {"start": utc_iso(semester_start) if semester_start else None,
                            "end": utc_iso(now), "error": period_error}
        statuses = []
        for meeting, _ in eligible_meetings:
            if (semester_start and meeting.course_id == selected
                    and semester_start <= meeting.scheduled_start <= now
                    and lifecycle(meeting, now) == "closed"):
                record = checkins.get(meeting.id)
                statuses.append(record.status if record else None)
        approved = statuses.count("approved")
        result["attendance"] = {"course_id": selected, "approved": approved, "eligible": len(statuses),
                                "percentage": approved / len(statuses) * 100 if statuses else None,
                                "unresolved": sum(status in ("pending", "flagged", "appealed") for status in statuses)}
    return result


@router.get("/my-overview")
def student_overview(
    section: Literal["all", "attendance", "today", "flagged"] = "all",
    course_id: str | None = None,
    current_user: User = Depends(require_roles("student", read_only=True)),
    db: Session = Depends(get_read_db),
):
    return overview(db, current_user.id, section, course_id)
