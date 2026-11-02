"""Freeze session denominators once; GET analytics never writes snapshots."""
from collections import defaultdict
from datetime import datetime, timedelta

from app.models import AuditLog, Enrollment, Session as Meeting, SessionAttendanceSnapshot as Snapshot


def capture_attendance_snapshots(db, now=None):
    """Backfill missing held sessions using available immutable enrollment events.

    Call inside the lifecycle/enrollment transaction. Existing snapshots are never
    updated, including on re-enrollment or subsequent scheduler ticks.
    """
    now = now or datetime.utcnow()
    meetings = db.query(Meeting).outerjoin(Snapshot, Snapshot.session_id == Meeting.id).filter(
        Snapshot.session_id.is_(None), Meeting.status.in_(("active", "closed")),
        Meeting.scheduled_start <= now,
    ).order_by(Meeting.id).all()
    if not meetings:
        return 0
    course_ids = {meeting.course_id for meeting in meetings}
    enrollments = defaultdict(list)
    for enrollment in db.query(Enrollment).filter(Enrollment.course_id.in_(course_ids)).all():
        enrollments[enrollment.course_id].append(enrollment)
    events = defaultdict(list)
    for enrollment_id, action, timestamp in db.query(
        AuditLog.resource_id, AuditLog.action, AuditLog.timestamp,
    ).join(Enrollment, Enrollment.id == AuditLog.resource_id).filter(
        Enrollment.course_id.in_(course_ids), AuditLog.success.is_(True),
        AuditLog.action.in_(("enrollment_added", "enrollment_removed")),
    ).order_by(AuditLog.timestamp, AuditLog.id).all():
        events[enrollment_id].append((timestamp, action))
    values = []
    for meeting in meetings:
        eligible = set()
        for enrollment in enrollments[meeting.course_id]:
            before = [action for timestamp, action in events[enrollment.id]
                      if timestamp <= meeting.scheduled_start]
            included = before[-1] == "enrollment_added" if before else (
                enrollment.enrolled_at <= meeting.scheduled_start
                and (enrollment.dropped_at is None or enrollment.dropped_at > meeting.scheduled_start)
                and (enrollment.is_active or enrollment.dropped_at is not None)
            )
            if included:
                eligible.add(enrollment.student_id)
        values.append(dict(
            session_id=meeting.id, expected_attendances=len(eligible), captured_at=now,
            # Historical imports can have overwritten/deleted intervals that no
            # longer exist in the audit trail. Never claim an exact backfill.
            historical_enrollment_limited=meeting.scheduled_start < now - timedelta(seconds=5),
        ))
    # Multiple workers may discover a missing snapshot concurrently. The first
    # committed value wins; a later tick cannot replace it or roll back a caller.
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(Snapshot).values(values).on_conflict_do_nothing(index_elements=["session_id"]))
    return len(values)
