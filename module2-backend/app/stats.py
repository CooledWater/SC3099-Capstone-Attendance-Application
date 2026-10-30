"""Statistics and API-metrics endpoints for the Module 4 dashboard.

* ``GET /api/v1/stats/{overview,sessions/{id},courses/{id},students/{id}}`` -
  attendance analytics per docs/API-SPECIFICATION.md "Statistics".
* ``GET /api/v1/metrics/`` - per-endpoint latency/volume/success buckets that
  module4-observability's MetricsPanel polls (no spec entry; the response shape
  is dictated by that component).

All stats handlers are read-only: they use ``get_read_db`` and
``require_roles(..., read_only=True)`` exactly like the other read endpoints.

Response-shape note: tests/public/test_observability.py and the API spec name
several fields differently (e.g. ``today_checkins`` vs
``total_checkins_today``). Both spellings are returned with the same value so
either contract is satisfied.

Definitions used throughout (the spec is silent, so they are fixed here):

* "held" sessions are those with status ``active`` or ``closed``; attendance
  rates only count held sessions so future/cancelled sessions cannot drag a
  rate down.
* A check-in of any status counts as attending (spec example: ``checked_in``
  45 == approved 42 + flagged 2 + rejected 1); ``by_status`` shows the split.
* ``total_enrolled`` is the *current* active enrollment count.
* Rates are fractions in [0, 1]; ``0.0`` when the denominator is 0.
"""
import math
import json
import os
import random
import threading
import time
from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_read_db
from app.models import AuditLog, CheckIn, Course, Enrollment, Session as SessionModel, User, SessionAttendanceSnapshot
from app import prometheus_metrics
from app.permissions import assists, teaches

router = APIRouter(prefix="/api/v1", tags=["stats"])

HELD_STATUSES = ("active", "closed")
NEEDS_REVIEW_STATUSES = ("flagged", "appealed")
CHECKIN_STATUSES = ("approved", "flagged", "rejected", "pending", "appealed")

# Risk bands from API-SPECIFICATION.md's session risk_distribution.
MEDIUM_RISK = 0.3
HIGH_RISK = 0.5

# Not defined anywhere in the docs; a student below this is listed under
# ``low_attendance_alerts`` on the course stats.
LOW_ATTENDANCE_THRESHOLD = 0.75

RECENT_CHECKINS_LIMIT = 10
TIMELINE_BUCKET_MINUTES = 5
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Singapore")
SGT = timezone(timedelta(hours=8))


def _app_zone() -> tzinfo:
    # Match student_overview.py and the export handlers. Singapore is UTC+8
    # without daylight saving, so its current reporting needs no tzdata package.
    if APP_TIMEZONE == "Asia/Singapore":
        return SGT
    try:
        return ZoneInfo(APP_TIMEZONE)
    except Exception:
        return SGT


def _effective_timezone_name() -> str:
    if APP_TIMEZONE == "Asia/Singapore":
        return APP_TIMEZONE
    try:
        ZoneInfo(APP_TIMEZONE)
        return APP_TIMEZONE
    except Exception:
        return "Asia/Singapore"


def _local_day_bounds(day: date) -> tuple[datetime, datetime]:
    zone = _app_zone()
    start = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _local_date(value: datetime) -> date:
    return value.replace(tzinfo=timezone.utc).astimezone(_app_zone()).date()


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _rate(numerator, denominator) -> float:
    if not denominator:
        return 0.0
    return round(min(1.0, numerator / denominator), 4)


def _avg(value, digits: int = 4):
    return round(float(value), digits) if value is not None else None


def _count_if(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def _naive_utc(value: datetime) -> datetime:
    # Same normalisation as main._to_naive_utc (all timestamp columns are
    # naive UTC); duplicated because main imports this module.
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iso_day(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _can_view_course(user: User, course_instructor_id: str | None) -> bool:
    """Admins see everything; instructors see only courses assigned to them.

    Courses with no assigned instructor are admin-only (app/permissions.py).
    """
    return user.role == "admin" or teaches(user, course_instructor_id)


def _course_scope(user: User, course_id: str | None) -> list:
    """WHERE conditions (on ``Course``) restricting a stats query to what
    ``user`` may see, optionally narrowed to one course."""
    conditions = []
    if course_id:
        conditions.append(Course.id == course_id)
    if user.role != "admin":
        conditions.append(Course.instructor_id == user.id)
    return conditions


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
    )


def _not_found(what: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found"
    )


# --------------------------------------------------------------------------
# GET /stats/overview
# --------------------------------------------------------------------------

def _overview_charts(db: Session, start_date: date, end_date: date, scope: list):
    """Two aggregate reads, independent of the number of courses."""
    if (end_date - start_date).days != 7:
        raise HTTPException(400, "Chart reporting period must contain seven calendar days")
    start, _ = _local_day_bounds(start_date)
    end, _ = _local_day_bounds(end_date)
    calendar_days = [start_date + timedelta(days=i) for i in range(7)]
    counts = db.query(*[
        _count_if(and_(CheckIn.checked_in_at >= _local_day_bounds(day)[0],
                       CheckIn.checked_in_at < _local_day_bounds(day)[1]))
        for day in calendar_days
    ]).select_from(CheckIn).join(SessionModel, SessionModel.id == CheckIn.session_id).join(
        Course, Course.id == SessionModel.course_id
    ).filter(CheckIn.checked_in_at >= start, CheckIn.checked_in_at < end, *scope).one()

    held_filters = [SessionModel.status.in_(HELD_STATUSES),
                    SessionModel.scheduled_start >= start, SessionModel.scheduled_start < end]
    per_session = db.query(
        CheckIn.session_id.label("session_id"), func.count(CheckIn.id).label("recorded"),
    ).join(SessionModel, SessionModel.id == CheckIn.session_id).filter(
        *held_filters,
    ).group_by(CheckIn.session_id).subquery()
    held = db.query(
        SessionModel.course_id.label("course_id"),
        func.count(SessionModel.id).label("sessions"),
        _count_if(SessionModel.status == "active").label("active"),
        func.coalesce(func.sum(per_session.c.recorded), 0).label("recorded"),
        func.coalesce(func.sum(SessionAttendanceSnapshot.expected_attendances), 0).label("expected"),
        _count_if(SessionAttendanceSnapshot.session_id.is_(None)).label("missing"),
        _count_if(SessionAttendanceSnapshot.historical_enrollment_limited.is_(True)).label("limited"),
    ).outerjoin(per_session, per_session.c.session_id == SessionModel.id).outerjoin(
        SessionAttendanceSnapshot, SessionAttendanceSnapshot.session_id == SessionModel.id,
    ).filter(
        *held_filters,
    ).group_by(SessionModel.course_id).subquery()
    rows = db.query(Course.id, Course.code, Course.name, held.c.sessions,
                    held.c.active, held.c.recorded, held.c.expected, held.c.missing, held.c.limited).outerjoin(
        held, held.c.course_id == Course.id
    ).filter(*scope).order_by(Course.code, Course.id).all()
    today = _local_date(datetime.now(timezone.utc))
    return {
        "timezone": _effective_timezone_name(),
        "chart_days": [{"date": day.isoformat(), "count": int(counts[i]) if day <= today else None,
                        "partial": day == today} for i, day in enumerate(calendar_days)],
        "chart_courses": [{
            "course_id": course_id, "course_code": code, "course_name": name,
            "total_sessions": int(sessions or 0), "active_sessions": int(active or 0),
            "recorded_checkins": int(recorded or 0),
            "expected_attendances": None if missing else int(expected or 0),
            "historical_enrollment_limited": bool(limited or missing),
            "denominator_basis": "saved_enrollment_at_session_start",
        } for course_id, code, name, sessions, active, recorded, expected, missing, limited in rows],
    }


@router.get("/stats/overview")
def stats_overview(
    course_id: str | None = None,
    days: int = 7,
    include_course_participation: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(require_roles("instructor", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    """System-wide stats (admin) or stats across the instructor's courses."""
    days = max(1, min(days, 90))

    if course_id:
        course = db.query(Course.instructor_id).filter(Course.id == course_id).first()
        if not course:
            raise _not_found("Course")
        if not _can_view_course(current_user, course.instructor_id):
            raise _forbidden()

    scope = _course_scope(current_user, course_id)

    if include_course_participation:
        if current_user.role != "admin":
            raise _forbidden()
        if start_date is None or end_date is None:
            raise HTTPException(400, "Chart start_date and exclusive end_date are required")
        return _overview_charts(db, start_date, end_date, scope)

    now = datetime.now(timezone.utc)
    today_start, today_end = _local_day_bounds(_local_date(now))
    week_start = today_start - timedelta(days=6)
    trend_start = today_start - timedelta(days=days - 1)
    trend_end = today_end

    held = SessionModel.status.in_(HELD_STATUSES)

    # Enrolled students per course / check-ins per session, used to turn
    # "who showed up" into a rate against "who could have".
    enrolled_per_course = (
        db.query(
            Enrollment.course_id.label("course_id"),
            func.count(Enrollment.id).label("n"),
        )
        .filter(Enrollment.is_active == True)  # noqa: E712
        .group_by(Enrollment.course_id)
        .subquery()
    )
    checkins_per_session = (
        db.query(
            CheckIn.session_id.label("session_id"),
            func.count(CheckIn.id).label("n"),
        )
        .group_by(CheckIn.session_id)
        .subquery()
    )
    possible = func.coalesce(enrolled_per_course.c.n, 0)
    attended = func.coalesce(checkins_per_session.c.n, 0)

    sessions_from = (
        SessionModel.__table__.join(Course, Course.id == SessionModel.course_id)
        .outerjoin(enrolled_per_course, enrolled_per_course.c.course_id == SessionModel.course_id)
        .outerjoin(checkins_per_session, checkins_per_session.c.session_id == SessionModel.id)
    )

    total_sessions, active_sessions, possible_total, attended_total = (
        db.query(
            _count_if(SessionModel.status != "cancelled"),
            _count_if(SessionModel.status == "active"),
            func.coalesce(func.sum(case((held, possible), else_=0)), 0),
            func.coalesce(func.sum(case((held, attended), else_=0)), 0),
        )
        .select_from(sessions_from)
        .filter(*scope)
        .one()
    )

    course_count = (
        db.query(func.count(Course.id))
        .filter(Course.is_active == True, *scope)  # noqa: E712
        .scalar_subquery()
    )
    if current_user.role == "admin" and not course_id:
        student_count = (
            db.query(func.count(User.id))
            .filter(User.role == "student", User.is_active == True)  # noqa: E712
            .scalar_subquery()
        )
    else:
        student_count = (
            db.query(func.count(func.distinct(Enrollment.student_id)))
            .join(Course, Course.id == Enrollment.course_id)
            .filter(Enrollment.is_active == True, *scope)  # noqa: E712
            .scalar_subquery()
        )
    total_courses, total_students = db.query(course_count, student_count).one()

    (
        checkins_total,
        approved,
        flagged_pending,
        average_risk,
        checkins_today,
        checkins_week,
        high_risk_today,
        flagged_count,
        appealed_count,
    ) = (
        db.query(
            func.count(CheckIn.id),
            _count_if(CheckIn.status == "approved"),
            _count_if(CheckIn.status.in_(NEEDS_REVIEW_STATUSES)),
            func.avg(CheckIn.risk_score),
            _count_if(and_(CheckIn.checked_in_at >= today_start, CheckIn.checked_in_at < today_end)),
            _count_if(CheckIn.checked_in_at >= week_start),
            _count_if(and_(CheckIn.checked_in_at >= today_start, CheckIn.checked_in_at < today_end, CheckIn.risk_score >= HIGH_RISK)),
            _count_if(CheckIn.status == "flagged"),
            _count_if(CheckIn.status == "appealed"),
        )
        .select_from(CheckIn)
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .join(Course, Course.id == SessionModel.course_id)
        .filter(*scope)
        .one()
    )

    checkin_day = func.date(CheckIn.checked_in_at)
    checkins_by_day_rows = (
        db.query(checkin_day, func.count(CheckIn.id))
        .select_from(CheckIn)
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .join(Course, Course.id == SessionModel.course_id)
        .filter(CheckIn.checked_in_at >= trend_start, CheckIn.checked_in_at < trend_end, *scope)
        .group_by(checkin_day)
        .all()
    )
    checkins_by_day = {_iso_day(day): int(n) for day, n in checkins_by_day_rows}

    session_day = func.date(SessionModel.scheduled_start)
    rate_rows = (
        db.query(
            session_day,
            func.coalesce(func.sum(possible), 0),
            func.coalesce(func.sum(attended), 0),
        )
        .select_from(sessions_from)
        .filter(
            held,
            SessionModel.scheduled_start >= trend_start,
            SessionModel.scheduled_start < trend_end,
            *scope,
        )
        .group_by(session_day)
        .all()
    )
    rate_by_day = {
        _iso_day(day): _rate(int(att), int(pos)) for day, pos, att in rate_rows if pos
    }

    # Newest first, matching the spec example. Days without check-ins are
    # reported as 0 so a chart gets a continuous axis; days without held
    # sessions have no defined attendance rate and are omitted.
    day_keys = [(today_start - timedelta(days=i)).date().isoformat() for i in range(days)]

    checkins_today = int(checkins_today)
    flagged_pending = int(flagged_pending)

    return {
        "total_sessions": int(total_sessions),
        "active_sessions": int(active_sessions),
        "total_courses": int(total_courses),
        "total_students": int(total_students),
        "today_checkins": checkins_today,
        "total_checkins_today": checkins_today,
        "total_checkins_week": int(checkins_week),
        "average_attendance_rate": _rate(int(attended_total), int(possible_total)),
        "flagged_pending": flagged_pending,
        "flagged_pending_review": flagged_pending,
        "flagged_count": int(flagged_count),
        "appealed_count": int(appealed_count),
        "approval_rate": _rate(int(approved), int(checkins_total)),
        "average_risk_score": _avg(average_risk) or 0.0,
        "high_risk_checkins_today": int(high_risk_today),
        "high_risk_threshold": HIGH_RISK,
        "timezone": _effective_timezone_name(),
        "trends": {
            "checkins_by_day": [
                {"date": key, "count": checkins_by_day.get(key, 0)} for key in day_keys
            ],
            "attendance_rate_by_day": [
                {"date": key, "rate": rate_by_day[key]} for key in day_keys if key in rate_by_day
            ],
        },
    }


# --------------------------------------------------------------------------
# GET /stats/courses/{course_id}/overview
# --------------------------------------------------------------------------

@router.get("/stats/courses/{course_id}/overview")
def stats_course_overview(
    course_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(require_roles("instructor", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    """Return one consistent, course-scoped aggregation for the instructor view.

    ``start_date`` is inclusive and ``end_date`` is exclusive. Session dates
    are evaluated in APP_TIMEZONE (Asia/Singapore by default), then converted
    to UTC-naive values for the database. Expected attendance uses the current
    active enrollment set, matching the existing stats contract; immutable
    historical enrollment events are not available in this model.
    """
    start = _naive_utc(start_date) if start_date else None
    end = _naive_utc(end_date) if end_date else None
    if start and end and start >= end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise _not_found("Course")
    if not _can_view_course(current_user, course.instructor_id):
        raise _forbidden()

    period_filters = [SessionModel.course_id == course_id]
    if start:
        period_filters.append(SessionModel.scheduled_start >= start)
    if end:
        period_filters.append(SessionModel.scheduled_start < end)

    enrolled_count = (
        db.query(func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id, Enrollment.is_active == True)  # noqa: E712
        .scalar()
    ) or 0

    # One row per session. The unique session/student index makes the check-in
    # count retry-safe; every verification status is intentionally included.
    session_rows = (
        db.query(
            SessionModel.id,
            SessionModel.name,
            SessionModel.status,
            SessionModel.scheduled_start,
            SessionModel.scheduled_end,
            func.count(CheckIn.id),
        )
        .outerjoin(CheckIn, CheckIn.session_id == SessionModel.id)
        .filter(*period_filters)
        .group_by(
            SessionModel.id,
            SessionModel.name,
            SessionModel.status,
            SessionModel.scheduled_start,
            SessionModel.scheduled_end,
        )
        .order_by(SessionModel.scheduled_end.desc(), SessionModel.scheduled_start.desc())
        .all()
    )
    held_rows = [row for row in session_rows if row[2] in HELD_STATUSES]
    closed_rows = [row for row in session_rows if row[2] == "closed"]
    recorded = sum(int(row[5]) for row in held_rows)
    expected = enrolled_count * len(held_rows)

    status_counts = {name: 0 for name in CHECKIN_STATUSES}
    period_checkins = (
        db.query(CheckIn.status, func.count(CheckIn.id))
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .filter(*period_filters, SessionModel.status.in_(HELD_STATUSES))
        .group_by(CheckIn.status)
        .all()
    )
    for checkin_status, count in period_checkins:
        status_name = getattr(checkin_status, "value", checkin_status)
        status_counts[status_name] = int(count)
    all_period_checkins = sum(status_counts.values())
    approval_rate = None if all_period_checkins == 0 else _rate(
        status_counts["approved"], all_period_checkins
    )

    today = _local_date(datetime.utcnow())
    today_start, today_end = _local_day_bounds(today)
    today_rows = (
        db.query(SessionModel.status, func.count(SessionModel.id))
        .filter(
            SessionModel.course_id == course_id,
            SessionModel.scheduled_start >= today_start,
            SessionModel.scheduled_start < today_end,
        )
        .group_by(SessionModel.status)
        .all()
    )
    today_breakdown = {"scheduled": 0, "active": 0, "closed": 0, "cancelled": 0}
    for session_status, count in today_rows:
        today_breakdown[session_status] = int(count)

    # Closed-session participation is calculated in one grouped query. A
    # student with no eligible closed sessions is absent from the result.
    participation_rows = (
        db.query(
            User.id,
            User.full_name,
            User.email,
            func.count(func.distinct(SessionModel.id)),
            func.count(func.distinct(CheckIn.session_id)),
        )
        .select_from(Enrollment)
        .join(User, User.id == Enrollment.student_id)
        .join(
            SessionModel,
            and_(
                SessionModel.course_id == Enrollment.course_id,
                SessionModel.status == "closed",
                *( [SessionModel.scheduled_start >= start] if start else [] ),
                *( [SessionModel.scheduled_start < end] if end else [] ),
            ),
        )
        .outerjoin(
            CheckIn,
            and_(
                CheckIn.session_id == SessionModel.id,
                CheckIn.student_id == Enrollment.student_id,
            ),
        )
        .filter(Enrollment.course_id == course_id, Enrollment.is_active == True)  # noqa: E712
        .group_by(User.id, User.full_name, User.email)
        .having(
            func.count(func.distinct(CheckIn.session_id)) * 100
            <= func.count(func.distinct(SessionModel.id)) * 40
        )
        .all()
    )
    low_participation = []
    for student_id, name, email, eligible, submitted in participation_rows:
        eligible, submitted = int(eligible), int(submitted)
        ratio = submitted / eligible if eligible else None
        if ratio is not None:
            low_participation.append({
                "student_id": student_id,
                "student_name": name,
                "student_email": email,
                "submitted_sessions": submitted,
                "expected_sessions": eligible,
                "participation_rate": round(ratio, 4),
            })
    low_participation.sort(key=lambda item: (item["participation_rate"], item["student_name"]))

    # Course overview uses equal-width numerical bins on the backend's 0–1
    # risk scale. The final bin includes 1.0; all others are half-open.
    risk_bins = [
        {
            "label": f"{index / 10:.1f}–<{(index + 1) / 10:.1f}",
            "min": index / 10,
            "max": (index + 1) / 10,
            "count": 0,
        }
        for index in range(10)
    ]
    risk_bins[-1]["label"] = "0.9–1.0"
    risk_index = case(
        *[
            (CheckIn.risk_score < (index + 1) / 10, index)
            for index in range(len(risk_bins) - 1)
        ],
        else_=len(risk_bins) - 1,
    ).label("risk_bin")
    scored_bins = (
        db.query(risk_index, func.count(CheckIn.id))
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .filter(*period_filters, SessionModel.status.in_(HELD_STATUSES), CheckIn.risk_score.isnot(None))
        .group_by(risk_index)
        .all()
    )
    scored_count = 0
    for index, count in scored_bins:
        risk_bins[int(index)]["count"] = int(count)
        scored_count += int(count)

    # Expose the dashboard's three bands without another query. Keep the
    # numerical bins for existing consumers; their boundaries align exactly.
    band_counts = {"low": 0, "medium": 0, "high": 0}
    for item in risk_bins:
        key = "low" if item["max"] <= MEDIUM_RISK else "medium" if item["max"] <= HIGH_RISK else "high"
        band_counts[key] += item["count"]
    risk_bands = [{"key": key, "count": count} for key, count in band_counts.items()]

    # Aggregate trend buckets from recorded/expected totals, never from an
    # average of session percentages. Future buckets remain null.
    is_monthly = bool(start and end and (end - start).days > 7)
    if start and end:
        local_start = start.replace(tzinfo=timezone.utc).astimezone(_app_zone())
        local_end = end.replace(tzinfo=timezone.utc).astimezone(_app_zone())
    else:
        local_start = datetime.now(_app_zone()).replace(hour=0, minute=0, second=0, microsecond=0)
        local_end = local_start + timedelta(days=31)
    final_day = local_end.date()
    if is_monthly:
        # Monthly reporting uses four month-relative buckets. This keeps W1
        # anchored to the first day selected by the user instead of adding a
        # partial calendar-week bucket from the previous month.
        month_start = local_start.date()
        bucket_days = [month_start + timedelta(days=7 * index) for index in range(4)]
    else:
        bucket_days = []
        cursor = local_start.date()
        while cursor < final_day:
            bucket_days.append(cursor)
            cursor += timedelta(days=1)
    trend = []
    for bucket_start in bucket_days:
        bucket_end = bucket_start + (timedelta(days=7) if is_monthly else timedelta(days=1))
        if is_monthly and bucket_start == bucket_days[-1]:
            bucket_end = final_day
        rows = [row for row in held_rows if bucket_start <= _local_date(row[3]) < bucket_end]
        bucket_recorded = sum(int(row[5]) for row in rows)
        bucket_expected = enrolled_count * len(rows)
        trend.append({
            "start": bucket_start.isoformat(),
            "end": min(bucket_end, final_day).isoformat(),
            "recorded": bucket_recorded,
            "expected": bucket_expected,
            "rate": None if bucket_expected == 0 else _rate(bucket_recorded, bucket_expected),
            "provisional": any(row[2] == "active" for row in rows),
        })

    outstanding_counts = (
        db.query(CheckIn.status, func.count(CheckIn.id))
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .filter(
            SessionModel.course_id == course_id,
            CheckIn.status.in_(("flagged", "appealed")),
        )
        .group_by(CheckIn.status)
        .all()
    )
    outstanding = {"flagged": 0, "appealed": 0}
    for checkin_status, count in outstanding_counts:
        status_name = getattr(checkin_status, "value", checkin_status)
        if status_name in outstanding:
            outstanding[status_name] = int(count)

    return {
        "course_id": course.id,
        "course_code": course.code,
        "course_name": course.name,
        "timezone": _effective_timezone_name(),
        "start_date": start,
        "end_date": end,
        "attendance": {
            "recorded": recorded,
            "expected": expected,
            "rate": _rate(recorded, expected),
            "held_sessions": len(held_rows),
            "active_sessions": sum(1 for row in held_rows if row[2] == "active"),
            "approval_rate": approval_rate,
            "status_counts": status_counts,
            "historical_enrollment_limited": True,
        },
        "outstanding": outstanding,
        "today": {"date": today.isoformat(), "total": sum(today_breakdown.values()), "breakdown": today_breakdown},
        "low_participation": {"threshold": 0.4, "total": len(low_participation), "students": low_participation},
        "risk_distribution": {"scored_count": scored_count, "bins": risk_bins, "bands": risk_bands},
        "trend": trend,
        "recent_sessions": [
            {
                "session_id": row[0],
                "name": row[1],
                "status": row[2],
                "scheduled_start": row[3],
                "scheduled_end": row[4],
                "recorded": int(row[5]),
                "expected": enrolled_count,
                "rate": _rate(int(row[5]), enrolled_count),
            }
            for row in closed_rows[:5]
        ],
    }


# --------------------------------------------------------------------------
# GET /stats/sessions/{session_id}
# --------------------------------------------------------------------------

@router.get("/stats/sessions/{session_id}")
def stats_session(
    session_id: str,
    current_user: User = Depends(require_roles("instructor", "ta", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    enrolled = (
        db.query(func.count(Enrollment.id))
        .filter(
            Enrollment.course_id == SessionModel.course_id,
            Enrollment.is_active == True,  # noqa: E712
        )
        .correlate(SessionModel)
        .scalar_subquery()
    )
    row = (
        db.query(SessionModel, Course, enrolled)
        .join(Course, Course.id == SessionModel.course_id)
        .filter(SessionModel.id == session_id)
        .first()
    )
    if not row:
        raise _not_found("Session")

    session, course, total_enrolled = row
    total_enrolled = int(total_enrolled)

    if current_user.role == "instructor" and not _can_view_course(current_user, course.instructor_id):
        raise _forbidden()
    if current_user.role == "ta" and not assists(db, current_user, course.id):
        raise _forbidden()

    checkins = (
        db.query(
            CheckIn.status,
            CheckIn.risk_score,
            CheckIn.distance_from_venue_meters,
            CheckIn.checked_in_at,
        )
        .filter(CheckIn.session_id == session_id)
        .all()
    )

    by_status = {name: 0 for name in CHECKIN_STATUSES}
    risk_distribution = {"low": 0, "medium": 0, "high": 0}
    timeline: dict[int, int] = {}
    risks, distances, minutes = [], [], []
    pre_opening_count = 0

    for checkin_status, risk, distance, checked_in_at in checkins:
        by_status[checkin_status] = by_status.get(checkin_status, 0) + 1

        if risk is not None:
            risks.append(risk)
            if risk >= HIGH_RISK:
                risk_distribution["high"] += 1
            elif risk >= MEDIUM_RISK:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["low"] += 1

        if distance is not None:
            distances.append(distance)

        # Measured from when check-in opened: students may check in before
        # scheduled_start, which would make the delta negative.
        elapsed = max(0.0, (checked_in_at - session.checkin_opens_at).total_seconds() / 60)
        pre_opening_count += int(checked_in_at < session.checkin_opens_at)
        minutes.append(elapsed)
        bucket = int(elapsed // TIMELINE_BUCKET_MINUTES) * TIMELINE_BUCKET_MINUTES
        timeline[bucket] = timeline.get(bucket, 0) + 1

    checked_in = len(checkins)

    now = datetime.utcnow()
    today = _local_date(now)
    today_start, today_end = _local_day_bounds(today)
    today_counts = {"scheduled": 0, "active": 0, "closed": 0, "cancelled": 0}
    for lifecycle, count in (
        db.query(SessionModel.status, func.count(SessionModel.id))
        .filter(SessionModel.course_id == course.id,
                SessionModel.scheduled_start >= today_start,
                SessionModel.scheduled_start < today_end)
        .group_by(SessionModel.status).all()
    ):
        today_counts[lifecycle] = int(count)

    # Return only a small, session-scoped review summary, never general audit
    # metadata (IPs, identities, notes). Filter before LIMIT; no N+1 lookups.
    review_activity = []
    events = (
        db.query(AuditLog)
        .join(CheckIn, CheckIn.id == AuditLog.resource_id)
        .filter(CheckIn.session_id == session.id,
                AuditLog.resource_type == "checkin",
                AuditLog.action == "checkin_reviewed")
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(5).all()
    )
    for event in events:
        try:
            details = json.loads(event.details or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(details, dict) or details.get("decision") not in ("approved", "rejected"):
            continue
        review_activity.append({
            "id": event.id, "session_id": session.id, "session_name": session.name,
            "action": "checkin_reviewed", "decision": details["decision"],
            "previous_status": details.get("previous_status"),
            "timestamp": event.timestamp.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        })

    return {
        "session_id": session.id,
        "session_name": session.name,
        "course_id": course.id,
        "course_code": course.code,
        "scheduled_start": session.scheduled_start,
        "status": session.status,
        "total_enrolled": total_enrolled,
        "checked_in": checked_in,
        "checked_in_count": checked_in,
        "attendance_rate": _rate(checked_in, total_enrolled),
        "by_status": by_status,
        "approved_count": by_status["approved"],
        "flagged_count": by_status["flagged"],
        "rejected_count": by_status["rejected"],
        "pending_count": by_status["pending"],
        "appealed_count": by_status["appealed"],
        "submitted_count": checked_in,
        "expected_count": total_enrolled,
        "scored_count": len(risks),
        "timezone": _effective_timezone_name(),
        "server_time": now.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "checkin_opens_at": session.checkin_opens_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "checkin_closes_at": session.checkin_closes_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "scheduled_end": session.scheduled_end,
        "actual_end": session.actual_end,
        "timeline_bucket_minutes": TIMELINE_BUCKET_MINUTES,
        "pre_opening_count": pre_opening_count,
        "today": {"date": today.isoformat(), "total": sum(today_counts.values()), "breakdown": today_counts},
        "recent_review_activity": review_activity,
        "average_risk_score": _avg(sum(risks) / len(risks)) if risks else 0.0,
        "average_distance_meters": _avg(sum(distances) / len(distances), 2) if distances else None,
        "average_checkin_time_minutes": _avg(sum(minutes) / len(minutes), 2) if minutes else None,
        "risk_distribution": risk_distribution,
        "checkin_timeline": [
            {"minute": minute, "count": timeline[minute]} for minute in sorted(timeline)
        ],
    }


# --------------------------------------------------------------------------
# GET /stats/courses/{course_id}
# --------------------------------------------------------------------------

@router.get("/stats/courses/{course_id}")
def stats_course(
    course_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current_user: User = Depends(require_roles("instructor", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    start = _naive_utc(start_date) if start_date else None
    end = _naive_utc(end_date) if end_date else None
    if start and end and start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must not be after end_date",
        )

    enrolled = (
        db.query(func.count(Enrollment.id))
        .filter(
            Enrollment.course_id == Course.id,
            Enrollment.is_active == True,  # noqa: E712
        )
        .correlate(Course)
        .scalar_subquery()
    )
    row = db.query(Course, enrolled).filter(Course.id == course_id).first()
    if not row:
        raise _not_found("Course")

    course, total_enrolled = row
    total_enrolled = int(total_enrolled)

    if not _can_view_course(current_user, course.instructor_id):
        raise _forbidden()

    session_filters = [
        SessionModel.course_id == course_id,
        SessionModel.status.in_(HELD_STATUSES),
    ]
    if start:
        session_filters.append(SessionModel.scheduled_start >= start)
    if end:
        session_filters.append(SessionModel.scheduled_start <= end)

    session_rows = (
        db.query(
            SessionModel.id,
            SessionModel.name,
            SessionModel.scheduled_start,
            func.count(CheckIn.id),
            _count_if(CheckIn.status == "flagged"),
            SessionModel.status,
        )
        .outerjoin(CheckIn, CheckIn.session_id == SessionModel.id)
        .filter(*session_filters)
        .group_by(SessionModel.id, SessionModel.name, SessionModel.scheduled_start, SessionModel.status)
        .order_by(SessionModel.scheduled_start)
        .all()
    )

    held_checkins = (
        db.query(
            CheckIn.student_id.label("student_id"),
            CheckIn.id.label("checkin_id"),
            CheckIn.risk_score.label("risk_score"),
        )
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .filter(*session_filters)
        .subquery()
    )
    student_rows = (
        db.query(
            User.id,
            User.full_name,
            func.count(held_checkins.c.checkin_id),
            func.avg(held_checkins.c.risk_score),
        )
        .select_from(Enrollment)
        .join(User, User.id == Enrollment.student_id)
        .outerjoin(held_checkins, held_checkins.c.student_id == User.id)
        .filter(Enrollment.course_id == course_id, Enrollment.is_active == True)  # noqa: E712
        .group_by(User.id, User.full_name)
        .order_by(User.full_name)
        .all()
    )

    total_sessions = len(session_rows)
    total_checkins = sum(int(row[3]) for row in session_rows)
    flagged_checkins = sum(int(row[4]) for row in session_rows)
    overall_rate = _rate(total_checkins, total_enrolled * total_sessions)

    student_attendance = []
    low_attendance_alerts = []
    for student_id, student_name, attended, average_risk in student_rows:
        attended = int(attended)
        student_rate = _rate(attended, total_sessions)
        student_attendance.append({
            "student_id": student_id,
            "student_name": student_name,
            "sessions_attended": attended,
            "attendance_rate": student_rate,
            "average_risk_score": _avg(average_risk) or 0.0,
        })
        if total_sessions and student_rate < LOW_ATTENDANCE_THRESHOLD:
            low_attendance_alerts.append({
                "student_id": student_id,
                "student_name": student_name,
                "attendance_rate": student_rate,
                "sessions_missed": max(0, total_sessions - attended),
            })

    return {
        "course_id": course.id,
        "course_code": course.code,
        "course_name": course.name,
        "total_sessions": total_sessions,
        "total_enrolled": total_enrolled,
        "recorded_checkins": total_checkins,
        "expected_attendances": total_enrolled * total_sessions,
        "active_sessions": sum(row[5] == "active" for row in session_rows),
        "historical_enrollment_limited": True,
        "overall_attendance_rate": overall_rate,
        "average_attendance_rate": overall_rate,
        "flagged_checkins": flagged_checkins,
        "sessions": [
            {
                "session_id": session_id,
                "name": name,
                "date": scheduled_start.date().isoformat(),
                "attendance_rate": _rate(int(n), total_enrolled),
                "checked_in": int(n),
                "status": session_status,
            }
            for session_id, name, scheduled_start, n, _, session_status in session_rows
        ],
        "student_attendance": student_attendance,
        "low_attendance_alerts": low_attendance_alerts,
    }


# --------------------------------------------------------------------------
# GET /stats/students/{student_id}
# --------------------------------------------------------------------------

@router.get("/stats/students/{student_id}")
def stats_student(
    student_id: str,
    current_user: User = Depends(require_roles("instructor", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    student = (
        db.query(User)
        .filter(User.id == student_id, User.role == "student")
        .first()
    )
    if not student:
        raise _not_found("Student")

    # Sharing one course grants access only to that instructor's course data.
    # Apply the scope before aggregation and before the recent-record limit.
    scope = _course_scope(current_user, None)

    held_sessions = (
        db.query(SessionModel.id, SessionModel.course_id)
        .filter(SessionModel.status.in_(HELD_STATUSES))
        .subquery()
    )
    own_checkins = (
        db.query(
            CheckIn.session_id.label("session_id"),
            CheckIn.id.label("checkin_id"),
            CheckIn.risk_score.label("risk_score"),
        )
        .filter(CheckIn.student_id == student_id)
        .subquery()
    )
    course_rows = (
        db.query(
            Course.id,
            Course.code,
            Course.instructor_id,
            func.count(func.distinct(held_sessions.c.id)),
            func.count(own_checkins.c.checkin_id),
            func.avg(own_checkins.c.risk_score),
        )
        .select_from(Enrollment)
        .join(Course, Course.id == Enrollment.course_id)
        .outerjoin(held_sessions, held_sessions.c.course_id == Course.id)
        .outerjoin(own_checkins, own_checkins.c.session_id == held_sessions.c.id)
        .filter(Enrollment.student_id == student_id, Enrollment.is_active == True)  # noqa: E712
        .filter(*scope)
        .group_by(Course.id, Course.code, Course.instructor_id)
        .order_by(Course.code)
        .all()
    )

    if current_user.role != "admin" and not any(
        _can_view_course(current_user, instructor_id)
        for _, _, instructor_id, _, _, _ in course_rows
    ):
        raise _forbidden()

    recent_rows = (
        db.query(
            SessionModel.id,
            SessionModel.name,
            Course.code,
            CheckIn.checked_in_at,
            CheckIn.status,
            CheckIn.risk_score,
        )
        .select_from(CheckIn)
        .join(SessionModel, SessionModel.id == CheckIn.session_id)
        .join(Course, Course.id == SessionModel.course_id)
        .filter(CheckIn.student_id == student_id)
        .filter(*scope)
        .order_by(CheckIn.checked_in_at.desc())
        .limit(RECENT_CHECKINS_LIMIT)
        .all()
    )

    courses = []
    total_sessions = attended_sessions = 0
    weighted_risk = 0.0
    for course_id, code, _, held, attended, average_risk in course_rows:
        held, attended = int(held), int(attended)
        total_sessions += held
        attended_sessions += attended
        weighted_risk += (float(average_risk) if average_risk is not None else 0.0) * attended
        courses.append({
            "course_id": course_id,
            "course_code": code,
            "attendance_rate": _rate(attended, held),
            "sessions_attended": attended,
            "total_sessions": held,
            "average_risk_score": _avg(average_risk) or 0.0,
        })

    recent = [
        {
            "session_id": session_id,
            "session_name": session_name,
            "course_code": course_code,
            "checked_in_at": checked_in_at,
            "status": checkin_status,
            "risk_score": risk_score,
        }
        for session_id, session_name, course_code, checked_in_at, checkin_status, risk_score
        in recent_rows
    ]

    return {
        "student_id": student.id,
        "student_name": student.full_name,
        "student_email": student.email,
        "total_enrolled_courses": len(courses),
        "total_sessions": total_sessions,
        "attended_sessions": attended_sessions,
        "attendance_rate": _rate(attended_sessions, total_sessions),
        "average_risk_score": _avg(weighted_risk / attended_sessions) if attended_sessions else 0.0,
        "courses": courses,
        "recent_checkins": recent,
        "recent_sessions": recent,
    }


# --------------------------------------------------------------------------
# API metrics (GET /metrics/) - collected in-process by MetricsMiddleware
# --------------------------------------------------------------------------

BUCKET_SECONDS = 3600
RETENTION_HOURS = 24
MAX_SAMPLES_PER_BUCKET = 1000
P95_QUANTILE = 0.95


class _Bucket:
    __slots__ = ("count", "errors", "samples")

    def __init__(self):
        self.count = 0
        self.errors = 0
        self.samples: list[float] = []


class MetricsStore:
    """Hourly per-endpoint latency/volume/error buckets held in memory.

    Deliberately not persisted: there is no metrics table in
    DATABASE-SCHEMA.md and this round adds no schema. The backend runs as a
    single uvicorn process (see Dockerfile), so one in-process store is
    coherent; figures reset on restart, which the dashboard already renders
    as "No metrics recorded yet".

    Latencies are kept as a bounded uniform reservoir per bucket so memory
    stays flat under load while p95 remains an unbiased estimate.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._buckets: dict[tuple[int, str], _Bucket] = {}
        self._last_pruned_bucket = -1

    def record(self, endpoint: str, duration_ms: float, status_code: int,
               now: float | None = None) -> None:
        bucket_index = int((time.time() if now is None else now) // BUCKET_SECONDS)
        with self._lock:
            if bucket_index != self._last_pruned_bucket:
                oldest = bucket_index - (RETENTION_HOURS * 3600) // BUCKET_SECONDS
                for key in [k for k in self._buckets if k[0] < oldest]:
                    del self._buckets[key]
                self._last_pruned_bucket = bucket_index

            bucket = self._buckets.get((bucket_index, endpoint))
            if bucket is None:
                bucket = self._buckets[(bucket_index, endpoint)] = _Bucket()

            bucket.count += 1
            # Client errors (4xx) are the caller's problem, not the API's;
            # only server-side failures count against the success rate.
            if status_code >= 500:
                bucket.errors += 1

            if len(bucket.samples) < MAX_SAMPLES_PER_BUCKET:
                bucket.samples.append(duration_ms)
            else:
                slot = random.randrange(bucket.count)
                if slot < MAX_SAMPLES_PER_BUCKET:
                    bucket.samples[slot] = duration_ms

    def snapshot(self, hours: int, limit: int, endpoint: str | None = None,
                 now: float | None = None) -> tuple[list[dict], int]:
        """Newest-first rows (one per bucket x endpoint) and the pre-limit total."""
        current = time.time() if now is None else now
        first_bucket = int((current - hours * 3600) // BUCKET_SECONDS)

        with self._lock:
            selected = [
                (key, bucket.count, bucket.errors, list(bucket.samples))
                for key, bucket in self._buckets.items()
                if key[0] >= first_bucket and (endpoint is None or key[1] == endpoint)
            ]

        selected.sort(key=lambda item: (-item[0][0], item[0][1]))
        total = len(selected)

        items = []
        for (bucket_index, name), count, errors, samples in selected[:limit]:
            samples.sort()
            p95 = samples[max(0, math.ceil(P95_QUANTILE * len(samples)) - 1)]
            recorded_at = datetime.fromtimestamp(
                bucket_index * BUCKET_SECONDS, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            items.append({
                "id": f"{bucket_index}:{name}",
                "recorded_at": recorded_at,
                "endpoint": name,
                "p95_ms": round(p95, 1),
                "request_count": count,
                "error_count": errors,
                "success_rate": round((count - errors) / count * 100, 2),
            })
        return items, total


metrics_store = MetricsStore()


class MetricsMiddleware:
    """Pure-ASGI timer feeding ``metrics_store``.

    Endpoints are labelled by *route template* ("GET /api/v1/sessions/{session_id}"),
    never the raw path, so IDs cannot blow up the number of series; requests
    that match no route share one "unmatched" label.

    The same measurement also feeds the Prometheus collectors behind
    ``GET /metrics`` (app/prometheus_metrics.py); the scrape itself is not
    counted in either place.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") == prometheus_metrics.METRICS_PATH:
            return await self.app(scope, receive, send)

        started = time.perf_counter()
        status_code = 500  # what an exception escaping the app turns into

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # The router stores the matched route in the (shared) scope.
            route_path = getattr(scope.get("route"), "path", None)
            endpoint = f"{scope['method']} {route_path}" if route_path else "unmatched"
            elapsed = time.perf_counter() - started
            metrics_store.record(endpoint, elapsed * 1000, status_code)
            prometheus_metrics.observe_http(
                scope["method"], route_path, status_code, elapsed
            )


@router.get("/metrics/")
def list_api_metrics(
    hours: int = Query(default=12, description="Look-back window in hours"),
    limit: int = 120,
    endpoint: str | None = None,
    current_user: User = Depends(require_roles("instructor", "admin", read_only=True)),
):
    """Per-endpoint p95 latency, request count and success rate (percent).

    Rows are hourly buckets, newest first. Only requests served by this
    process since it started are included.
    """
    hours = max(1, min(hours, RETENTION_HOURS))
    limit = max(1, min(limit, 500))

    items, total = metrics_store.snapshot(hours, limit, endpoint)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "window_hours": hours,
    }
