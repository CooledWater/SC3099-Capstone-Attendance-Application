"""Historical admin denominators remain fixed across enrollment mutations."""
from datetime import timedelta

from test_checkin_roster import world, START
from app.attendance_snapshots import capture_attendance_snapshots
from app.models import AuditLog, Enrollment, Session as Meeting, SessionAttendanceSnapshot as Snapshot
from app.session_lifecycle import synchronize_sessions


def capture(db, now=START):
    result = capture_attendance_snapshots(db, now)
    db.commit()
    return result


def test_snapshot_is_immutable_after_drop_reenroll_and_scheduler_ticks(world):
    _, db, _ = world
    assert capture(db) == 1
    saved = db.get(Snapshot, "meeting")
    assert saved.expected_attendances == 18
    assert saved.historical_enrollment_limited is False
    enrollment = db.get(Enrollment, "e0")
    enrollment.is_active = False
    enrollment.dropped_at = START + timedelta(days=1)
    db.commit()
    synchronize_sessions(db, START + timedelta(days=2))
    enrollment.is_active = True
    enrollment.dropped_at = None
    enrollment.enrolled_at = START + timedelta(days=3)
    db.commit()
    assert capture(db, START + timedelta(days=4)) == 0
    db.refresh(saved)
    assert saved.expected_attendances == 18
    assert saved.captured_at == START


def test_backfill_uses_events_before_start_despite_overwritten_enrollment(world):
    _, db, _ = world
    enrollment = db.get(Enrollment, "e0")
    enrollment.enrolled_at = START + timedelta(days=3)
    db.add_all([
        AuditLog(id="added", action="enrollment_added", resource_id="e0", timestamp=START-timedelta(days=2), success=True),
        AuditLog(id="removed", action="enrollment_removed", resource_id="e0", timestamp=START+timedelta(days=1), success=True),
        AuditLog(id="readded", action="enrollment_added", resource_id="e0", timestamp=START+timedelta(days=3), success=True),
    ])
    db.commit()
    capture(db, START + timedelta(days=4))
    saved = db.get(Snapshot, "meeting")
    assert saved.expected_attendances == 18
    assert saved.historical_enrollment_limited is True


def test_no_history_uses_intervals_and_excludes_late_enrollment(world):
    _, db, _ = world
    db.get(Enrollment, "e0").enrolled_at = START + timedelta(seconds=1)
    enrollment = db.get(Enrollment, "e1")
    enrollment.is_active = False
    enrollment.dropped_at = START + timedelta(seconds=1)
    db.commit()
    capture(db, START + timedelta(days=4))
    assert db.get(Snapshot, "meeting").expected_attendances == 17


def test_future_and_cancelled_sessions_are_not_frozen(world):
    _, db, _ = world
    meeting = db.get(Meeting, "meeting")
    assert capture(db, START - timedelta(seconds=1)) == 0
    meeting.status = "cancelled"
    db.commit()
    assert capture(db) == 0


def test_get_missing_snapshot_returns_unknown_without_writing(world):
    client, db, headers = world
    response = client.get("/api/v1/stats/overview", headers=headers("admin"), params={
        "include_course_participation": True, "start_date": "2026-01-05", "end_date": "2026-01-12",
    })
    assert response.status_code == 200
    course = response.json()["chart_courses"][0]
    assert course["expected_attendances"] is None
    assert course["recorded_checkins"] == 6
    assert db.query(Snapshot).count() == 0


def test_drop_endpoint_freezes_denominator_before_mutation(world):
    client, db, headers = world
    response = client.delete("/api/v1/enrollments/e0", headers=headers("admin"))
    assert response.status_code == 204, response.text
    assert db.get(Snapshot, "meeting").expected_attendances == 18
    assert db.get(Enrollment, "e0").is_active is False


def test_started_sessions_have_individual_denominators(world):
    _, db, _ = world
    capture(db)
    db.get(Enrollment, "e0").is_active = False
    db.get(Enrollment, "e0").dropped_at = START + timedelta(hours=1)
    second = Meeting(id="second", course_id="course", name="Second", status="active",
                     scheduled_start=START+timedelta(hours=2), scheduled_end=START+timedelta(hours=3),
                     checkin_opens_at=START+timedelta(hours=2), checkin_closes_at=START+timedelta(hours=3))
    db.add(second)
    db.commit()
    capture(db, START + timedelta(hours=2))
    assert db.get(Snapshot, "meeting").expected_attendances == 18
    assert db.get(Snapshot, "second").expected_attendances == 17
    from app.stats import _overview_charts
    from datetime import date
    report = _overview_charts(db, date(2026, 1, 5), date(2026, 1, 12), [])
    assert report["chart_courses"][0]["expected_attendances"] == 35
    assert report["chart_courses"][0]["recorded_checkins"] == 6
