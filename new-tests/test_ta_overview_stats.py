"""TA overview session aggregates and permissions, using isolated SQLite only."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from test_ta_scope import world
from app import stats
from app.models import AuditLog, CheckIn, Enrollment, Session as Meeting, User


def test_singapore_reporting_works_without_timezone_database(monkeypatch):
    def unavailable(_):
        raise RuntimeError("Timezone database unavailable")
    monkeypatch.setattr(stats, "ZoneInfo", unavailable)
    monkeypatch.setattr(stats, "APP_TIMEZONE", "Asia/Singapore")
    assert stats._effective_timezone_name() == "Asia/Singapore"
    assert stats._local_date(datetime(2026, 10, 27, 16)) == datetime(2026, 10, 28).date()
    assert stats._local_day_bounds(datetime(2026, 10, 28).date()) == (
        datetime(2026, 10, 27, 16), datetime(2026, 10, 28, 16),
    )
    monkeypatch.setattr(stats, "APP_TIMEZONE", "Invalid/Zone")
    assert stats._effective_timezone_name() == "Asia/Singapore"
    assert stats._app_zone().utcoffset(None) == timedelta(hours=8)


def populate(world, monkeypatch):
    call, db = world
    class FixedDatetime(datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 10, 28, 2, 2)
    monkeypatch.setattr(stats, "datetime", FixedDatetime)
    meeting = db.get(Meeting, "m_a")
    meeting.scheduled_start = datetime(2026, 10, 28, 2)
    meeting.scheduled_end = datetime(2026, 10, 28, 3)
    meeting.checkin_opens_at = datetime(2026, 10, 28, 1, 45)
    meeting.checkin_closes_at = datetime(2026, 10, 28, 2, 30)
    first = db.get(CheckIn, "c_a")
    first.checked_in_at = datetime(2026, 10, 28, 1, 44)
    for index, (status, risk, when) in enumerate([
        ("approved", 0.2, datetime(2026, 10, 28, 1, 45)),
        ("pending", 0.0, datetime(2026, 10, 28, 1, 50)),
        ("appealed", 0.8, datetime(2026, 10, 28, 2, 1)),
        ("rejected", 0.4, datetime(2026, 10, 28, 3, 1)),
    ]):
        uid = f"extra-{index}"
        db.add(User(id=uid, email=f"{uid}@example.edu", full_name=uid, role="student", hashed_password="unused"))
        db.add(Enrollment(student_id=uid, course_id="A"))
        db.add(CheckIn(id=f"extra-checkin-{index}", student_id=uid, session_id="m_a", status=status, risk_score=risk, checked_in_at=when))
    for sid, start in [("today-local", datetime(2026, 10, 27, 17)), ("yesterday-local", datetime(2026, 10, 27, 15))]:
        db.add(Meeting(id=sid, course_id="A", instructor_id="ia", name=sid, status="scheduled", scheduled_start=start,
                       scheduled_end=start + timedelta(hours=1), checkin_opens_at=start, checkin_closes_at=start + timedelta(hours=1)))
    for cid in ("c_a", "c_b"):
        db.add(AuditLog(id=f"event-{cid}", user_id="ia", action="checkin_reviewed", resource_type="checkin", resource_id=cid,
                        timestamp=datetime(2026, 10, 28, 2), details=json.dumps({"decision": "approved", "previous_status": "flagged", "notes": "PRIVATE"}), ip_address="PRIVATE"))
    db.commit()
    return call, db


def test_session_counts_timeline_anchor_zero_risk_and_scoped_real_activity(world, monkeypatch):
    call, _ = populate(world, monkeypatch)
    response = call("t1", "/stats/sessions/m_a")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["submitted_count"] == data["checked_in"] == 5
    assert data["expected_count"] == data["total_enrolled"] == 5
    assert data["scored_count"] == 5
    assert data["average_risk_score"] == 0.4
    assert sum(data["by_status"].values()) == 5
    assert set(data["by_status"].values()) == {1}
    assert data["checkin_timeline"] == [{"minute": 0, "count": 2}, {"minute": 5, "count": 1}, {"minute": 15, "count": 1}, {"minute": 75, "count": 1}]
    assert data["pre_opening_count"] == 1
    assert data["checkin_opens_at"] == "2026-10-28T01:45:00Z"
    assert data["timeline_bucket_minutes"] == 5
    assert data["today"]["date"] == "2026-10-28"
    assert data["today"]["total"] == 2
    assert data["today"]["breakdown"]["scheduled"] == 1
    assert len(data["recent_review_activity"]) == 1
    assert data["recent_review_activity"][0]["id"] == "event-c_a"
    assert "PRIVATE" not in json.dumps(data)


def test_review_refreshes_session_totals_and_real_activity(world):
    call, _ = world
    response = call("t1", "/checkins/c_a/review", method="POST", json={"status": "approved", "review_notes": "Reviewed"})
    assert response.status_code == 200
    data = call("t1", "/stats/sessions/m_a").json()
    assert data["by_status"]["flagged"] == 0
    assert data["by_status"]["approved"] == 1
    assert data["recent_review_activity"][0]["decision"] == "approved"
    assert call("t1", "/checkins/c_a/review", method="POST", json={"status": "rejected"}).status_code == 400


def test_ta_cannot_escape_assignments_or_use_instructor_analytics(world):
    call, _ = world
    for uid in ("t0", "sa", "ib"):
        assert call(uid, "/stats/sessions/m_a").status_code == 403
    assert call("t1", "/stats/sessions/m_b").status_code == 403
    assert call("t1", "/stats/sessions/unknown").status_code == 404
    for path in ("/stats/overview", "/stats/courses/A", "/stats/students/sa", "/audit/"):
        assert call("t1", path).status_code == 403


def test_no_submissions_and_unique_session_student_policy(world):
    call, db = world
    db.query(CheckIn).filter(CheckIn.session_id == "m_a").delete()
    db.commit()
    data = call("t1", "/stats/sessions/m_a").json()
    assert data["scored_count"] == data["submitted_count"] == 0
    assert data["checkin_timeline"] == []
    assert not any(data["by_status"].values())
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(CheckIn(session_id="m_b", student_id="sb", status="approved", risk_score=0.1))
            db.flush()


def test_legacy_missing_risk_is_excluded_from_average(world):
    _, db = world
    class LegacyDb:
        def query(self, *columns):
            query = db.query(*columns)
            if len(columns) == 4 and getattr(columns[0], "key", None) == "status":
                class Rows:
                    def filter(self, *args):
                        self.args = args
                        return self
                    def all(self):
                        rows = query.filter(*self.args).all()
                        return [(s, None, d, t) for s, _, d, t in rows]
                return Rows()
            return query
    result = stats.stats_session("m_a", current_user=db.get(User, "t1"), db=LegacyDb())
    assert result["submitted_count"] == 1
    assert result["scored_count"] == 0
    assert sum(result["risk_distribution"].values()) == 0
