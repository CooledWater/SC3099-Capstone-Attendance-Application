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
import random
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_read_db
from app.models import CheckIn, Course, Enrollment, Session as SessionModel, User
from app import prometheus_metrics

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
    """Admins see everything; instructors see their own courses.

    Courses with no assigned instructor (admin-created via POST /courses/
    without one) are visible to every instructor, matching how the other
    read endpoints (enrollments, session check-ins) treat them.
    """
    return user.role == "admin" or course_instructor_id in (None, user.id)


def _course_scope(user: User, course_id: str | None) -> list:
    """WHERE conditions (on ``Course``) restricting a stats query to what
    ``user`` may see, optionally narrowed to one course."""
    conditions = []
    if course_id:
        conditions.append(Course.id == course_id)
    if user.role != "admin":
        conditions.append(
            or_(Course.instructor_id == user.id, Course.instructor_id.is_(None))
        )
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

@router.get("/stats/overview")
def stats_overview(
    course_id: str | None = None,
    days: int = 7,
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

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=6)
    trend_start = today_start - timedelta(days=days - 1)
    trend_end = today_start + timedelta(days=1)

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
    ) = (
        db.query(
            func.count(CheckIn.id),
            _count_if(CheckIn.status == "approved"),
            _count_if(CheckIn.status.in_(NEEDS_REVIEW_STATUSES)),
            func.avg(CheckIn.risk_score),
            _count_if(CheckIn.checked_in_at >= today_start),
            _count_if(CheckIn.checked_in_at >= week_start),
            _count_if(and_(CheckIn.checked_in_at >= today_start, CheckIn.risk_score >= HIGH_RISK)),
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
        "approval_rate": _rate(int(approved), int(checkins_total)),
        "average_risk_score": _avg(average_risk) or 0.0,
        "high_risk_checkins_today": int(high_risk_today),
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
# GET /stats/sessions/{session_id}
# --------------------------------------------------------------------------

@router.get("/stats/sessions/{session_id}")
def stats_session(
    session_id: str,
    current_user: User = Depends(require_roles("instructor", "ta", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    # There is no TA<->course assignment model, so a TA cannot be scoped to
    # "their" courses; TAs get the same session-level read access they
    # already have on GET /checkins/session/{id}.
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

    if current_user.role == "instructor" and not (
        session.instructor_id == current_user.id
        or _can_view_course(current_user, course.instructor_id)
    ):
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

    for checkin_status, risk, distance, checked_in_at in checkins:
        by_status[checkin_status] = by_status.get(checkin_status, 0) + 1

        risk = risk or 0.0
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
        minutes.append(elapsed)
        bucket = int(elapsed // TIMELINE_BUCKET_MINUTES) * TIMELINE_BUCKET_MINUTES
        timeline[bucket] = timeline.get(bucket, 0) + 1

    checked_in = len(checkins)

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
        )
        .outerjoin(CheckIn, CheckIn.session_id == SessionModel.id)
        .filter(*session_filters)
        .group_by(SessionModel.id, SessionModel.name, SessionModel.scheduled_start)
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
    total_checkins = sum(int(n) for _, _, _, n, _ in session_rows)
    flagged_checkins = sum(int(n) for _, _, _, _, n in session_rows)
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
            }
            for session_id, name, scheduled_start, n, _ in session_rows
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
