"""Existing course stats supply uncapped numerator/denominator to admin charts."""
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from test_checkin_roster import world, START
from app.models import CheckIn, Enrollment, Session as Meeting
from app.models import Course
from app import stats as stats_module
from sqlalchemy import event
from app.attendance_snapshots import capture_attendance_snapshots


def stats(world):
    client, _, headers = world
    response = client.get("/api/v1/stats/courses/course", headers=headers("admin"), params={
        "start_date": "2026-01-10T00:00:00+08:00",
        "end_date": "2026-01-10T23:59:59.999999+08:00",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_all_statuses_and_current_denominator(world):
    data = stats(world)
    assert data["recorded_checkins"] == 6
    assert data["expected_attendances"] == 18
    assert data["total_sessions"] == 1
    assert data["active_sessions"] == 0
    assert data["historical_enrollment_limited"] is True
    assert data["sessions"][0]["status"] == "closed"


def test_active_sessions_make_totals_provisional_and_rates_use_sums(world):
    _, db, _ = world
    db.add(Meeting(id="second", course_id="course", name="Live", status="active",
                   scheduled_start=START + timedelta(hours=2), scheduled_end=START + timedelta(hours=3),
                   checkin_opens_at=START, checkin_closes_at=START + timedelta(hours=3)))
    db.add(CheckIn(id="second-record", session_id="second", student_id="s0", status="rejected", checked_in_at=START))
    db.commit()
    data = stats(world)
    assert data["total_sessions"] == 2
    assert data["active_sessions"] == 1
    assert data["recorded_checkins"] == 7
    assert data["expected_attendances"] == 36


@pytest.mark.parametrize("status", ["scheduled", "cancelled"])
def test_non_held_sessions_do_not_supply_attendance(world, status):
    _, db, _ = world
    db.get(Meeting, "meeting").status = status
    db.commit()
    data = stats(world)
    assert data["total_sessions"] == data["expected_attendances"] == data["recorded_checkins"] == 0


def test_zero_enrollment_and_historical_mismatch_preserve_raw_counts(world):
    _, db, _ = world
    db.query(Enrollment).update({Enrollment.is_active: False})
    db.commit()
    assert stats(world)["expected_attendances"] == 0
    assert stats(world)["recorded_checkins"] == 6
    db.query(Enrollment).filter(Enrollment.student_id == "s0").update({Enrollment.is_active: True})
    db.commit()
    data = stats(world)
    assert data["expected_attendances"] == 1
    assert data["recorded_checkins"] == 6  # never cap raw count to the current denominator


def test_database_rejects_retry_attempts_instead_of_inflating_counts(world):
    _, db, _ = world
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(CheckIn(id="retry", session_id="meeting", student_id="s0", status="approved", checked_in_at=START))
            db.flush()
    assert stats(world)["recorded_checkins"] == 6


def test_local_week_bounds_include_monday_midnight_and_exclude_next_monday(world):
    client, db, headers = world
    meeting = db.get(Meeting, "meeting")
    meeting.scheduled_start = START.replace(day=11, hour=16)  # Jan 12 Monday 00:00 SGT
    db.commit()
    params = {"start_date": "2026-01-12T00:00:00+08:00", "end_date": "2026-01-18T23:59:59.999999+08:00"}
    response = client.get("/api/v1/stats/courses/course", headers=headers("admin"), params=params)
    assert response.json()["total_sessions"] == 1
    meeting.scheduled_start += timedelta(days=7)
    db.commit()
    assert client.get("/api/v1/stats/courses/course", headers=headers("admin"), params=params).json()["total_sessions"] == 0


def chart_stats(world, **params):
    client, db, headers = world
    capture_attendance_snapshots(db)
    db.commit()
    response = client.get("/api/v1/stats/overview", headers=headers("admin"), params={
        "include_course_participation": True, "start_date": "2026-01-05", "end_date": "2026-01-12", **params,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_chart_aggregates_match_course_stats_and_retain_inactive_empty_courses(world):
    _, db, _ = world
    db.add(Course(id="inactive", code="OLD", name="Archived", semester="S1", is_active=False))
    db.commit()
    data = chart_stats(world)
    course = next(row for row in data["chart_courses"] if row["course_id"] == "course")
    expected = stats(world)
    for field in ("recorded_checkins", "expected_attendances", "total_sessions", "active_sessions"):
        assert course[field] == expected[field]
    assert sum(day["count"] for day in data["chart_days"]) == 6
    inactive = next(row for row in data["chart_courses"] if row["course_id"] == "inactive")
    assert inactive["total_sessions"] == inactive["expected_attendances"] == 0


def test_chart_query_count_stays_two_with_eighty_additional_courses(world):
    _, db, _ = world
    db.add_all([Course(id=f"extra{i}", code=f"EX{i}", name="Extra", semester="S1") for i in range(80)])
    db.commit()
    statements = []
    def count_queries(*args):
        statements.append(args[2])
    event.listen(db.bind, "before_cursor_execute", count_queries)
    try:
        from datetime import date
        result = stats_module._overview_charts(db, date(2026, 1, 5), date(2026, 1, 12), [])
    finally:
        event.remove(db.bind, "before_cursor_execute", count_queries)
    assert len(result["chart_courses"]) == 81
    assert len(statements) == 2


def test_chart_days_use_local_midnight_zero_fill_partial_and_future_null(world, monkeypatch):
    from datetime import datetime, timezone
    class FrozenTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(stats_module, "datetime", FrozenTime)
    _, db, _ = world
    record = db.get(CheckIn, "c0")
    record.checked_in_at = START.replace(day=9, hour=15, minute=59)  # Jan 9 in SGT
    db.commit()
    days = chart_stats(world)["chart_days"]
    assert [day["count"] for day in days] == [0, 0, 0, 0, 1, 5, None]
    assert days[5]["partial"] is True


def test_aggregate_mode_requires_admin_and_valid_calendar_week(world):
    client, _, headers = world
    params = {"include_course_participation": True, "start_date": "2026-01-05", "end_date": "2026-01-12"}
    assert client.get("/api/v1/stats/overview", headers=headers("instructor"), params=params).status_code == 403
    assert client.get("/api/v1/stats/overview", headers=headers("admin"), params={**params, "end_date": "2026-01-13"}).status_code == 400
    assert client.get("/api/v1/stats/overview", headers=headers("admin"), params={"include_course_participation": True}).status_code == 400
    assert "total_checkins_today" in client.get("/api/v1/stats/overview", headers=headers("admin")).json()
