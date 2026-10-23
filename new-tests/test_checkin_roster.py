"""Isolated instructor roster/review/export contracts; no external database."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-roster-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-roster-test-secret-with-at-least-32-characters"
os.environ["STRICT_SECURITY_MODE"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.auth import create_access_token
from app.database import Base, get_db, get_read_db
from app.models import AuditLog, CheckIn, Course, Enrollment, Session as Meeting, User

START = datetime(2026, 1, 10, 9)


@pytest.fixture
def world():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [User(id=role, role=role if role != "other" else "instructor", email=f"{role}@example.edu", full_name=role, hashed_password="unused") for role in ("instructor", "other", "ta", "admin")]
        students = [User(id=f"s{i}", role="student", email=f"s{i}@example.edu", full_name=f"Student {i}", hashed_password="unused") for i in range(18)]
        course = Course(id="course", code="SC4000", name="Test", semester="S1", instructor_id="instructor")
        meeting = Meeting(id="meeting", course_id=course.id, instructor_id="instructor", name="Lecture 9", status="closed", scheduled_start=START, scheduled_end=START + timedelta(hours=1), checkin_opens_at=START - timedelta(minutes=15), checkin_closes_at=START + timedelta(minutes=20))
        db.add_all([*users, *students, course, meeting])
        db.add_all([Enrollment(id=f"e{i}", student_id=student.id, course_id=course.id, enrolled_at=START - timedelta(days=1)) for i, student in enumerate(students)])
        statuses = ["approved", "flagged", "appealed", "pending", "rejected", "approved"]
        for i, status in enumerate(statuses):
            db.add(CheckIn(id=f"c{i}", session_id=meeting.id, student_id=f"s{i}", status=status, checked_in_at=START + timedelta(minutes=i - 2), risk_score=0.4,
                           risk_factors='[{"type":"device_unknown","severity":"medium","weight":0.15}]', appeal_reason="GPS inaccurate" if status == "appealed" else None))
        db.commit()
        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)
        def headers(role="instructor"):
            return {"Authorization": "Bearer " + create_access_token(role, "student" if role.startswith("s") else "instructor" if role == "other" else role)}
        yield client, db, headers
        app.dependency_overrides.clear()
    engine.dispose()


def roster(world):
    client, _, headers = world
    response = client.get("/api/v1/sessions/meeting/attendance", headers=headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_roster_summary_timing_and_sort(world):
    data = roster(world)
    assert data["expected"] == len(data["items"]) == 18
    assert [row["checkin_id"] for row in data["items"][:6]] == ["c5", "c4", "c3", "c2", "c1", "c0"]
    assert data["summary"]["present"] == 4  # start included; early records retained but not present
    assert data["summary"]["absent"] == 14
    assert data["summary"]["attendance_rate"] == 4 / 18
    assert sum(data["summary"]["verification"].values()) == 6
    assert all(row["status"] is None for row in data["items"][6:])
    assert all(row["risk_score"] == 0.4 for row in data["items"][:6])
    assert all(row["risk_score"] is None for row in data["items"][6:])


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_review_changes_verification_only_and_leaves_timing(world, decision):
    client, _, headers = world
    before = roster(world)
    response = client.post("/api/v1/checkins/c2/review", headers=headers(), json={"status": decision, "review_notes": "Verified explanation"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == decision
    after = roster(world)
    assert after["summary"]["verification"]["appealed"] == 0
    for name in ("present", "absent", "attendance_rate"):
        assert before["summary"][name] == after["summary"][name]
    detail = client.get("/api/v1/checkins/c2", headers=headers()).json()
    assert detail["review_notes"] == "Verified explanation"
    assert detail["risk_factors"][0]["weight"] == 0.15
    repeated = client.post("/api/v1/checkins/c2/review", headers=headers(), json={"status": decision})
    assert repeated.status_code == 400


def test_flagged_endpoint_paginates_combined_statuses(world):
    client, _, headers = world
    url = "/api/v1/checkins/flagged?course_id=course&session_id=meeting&limit=1"
    first = client.get(url, headers=headers()).json()
    second = client.get(url + "&offset=1", headers=headers()).json()
    assert first["total"] == second["total"] == 2
    assert {first["items"][0]["status"], second["items"][0]["status"]} == {"flagged", "appealed"}


def test_historical_enrollment_uses_audit_not_current_active_flag(world):
    _, db, _ = world
    # Dropped after class and reactivated later: original interval survives in audit.
    item = db.get(Enrollment, "e6")
    item.enrolled_at = START + timedelta(days=4)
    for i, (action, timestamp) in enumerate([
        ("enrollment_added", START - timedelta(days=1)),
        ("enrollment_removed", START + timedelta(days=1)),
        ("enrollment_added", START + timedelta(days=4)),
    ]):
        db.add(AuditLog(id=f"a{i}", action=action, resource_type="enrollment", resource_id="e6", timestamp=timestamp, success=True))
    db.get(Enrollment, "e7").is_active = False
    db.get(Enrollment, "e7").dropped_at = START - timedelta(seconds=1)
    db.get(Enrollment, "e8").enrolled_at = START + timedelta(seconds=1)
    db.commit()
    ids = {row["student_id"] for row in roster(world)["items"]}
    assert "s6" in ids and "s7" not in ids and "s8" not in ids


def test_active_session_missing_students_are_absent(world):
    _, db, _ = world
    meeting = db.get(Meeting, "meeting")
    meeting.status = "active"
    meeting.scheduled_end = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    data = roster(world)
    assert data["summary"]["absent"] == 14
    assert data["summary"]["present"] == 4


@pytest.mark.parametrize("manual", [False, True])
def test_presence_stops_at_automatic_or_instructor_close(world, manual):
    _, db, _ = world
    meeting = db.get(Meeting, "meeting")
    deadline = START + timedelta(minutes=2) if manual else meeting.scheduled_end
    if manual:
        meeting.actual_end = deadline
    db.get(CheckIn, "c3").checked_in_at = deadline - timedelta(microseconds=1)
    db.get(CheckIn, "c4").checked_in_at = deadline
    db.get(CheckIn, "c5").checked_in_at = deadline + timedelta(microseconds=1)
    db.commit()
    values = {row["checkin_id"]: row["attendance"] for row in roster(world)["items"] if row["checkin_id"]}
    assert values["c3"] == "present"
    assert values["c4"] == values["c5"] == "absent"


@pytest.mark.parametrize("path", ["sessions/meeting/attendance", "checkins/session/meeting", "checkins/c1", "export/session/meeting?format=json"])
def test_other_instructor_cannot_read_session_resources(world, path):
    client, _, headers = world
    response = client.get("/api/v1/" + path, headers=headers("other"))
    assert response.status_code == 403, response.text


def test_auth_review_permissions_and_payload_validation(world):
    client, _, headers = world
    assert client.get("/api/v1/sessions/meeting/attendance").status_code in (401, 403)
    assert client.get("/api/v1/sessions/meeting/attendance", headers=headers("s0")).status_code == 403
    assert client.post("/api/v1/checkins/c1/review", headers=headers("other"), json={"status": "approved"}).status_code == 403
    assert client.post("/api/v1/checkins/c1/review", headers=headers(), json={"status": "flagged"}).status_code == 422
    assert client.get("/api/v1/sessions/missing/attendance", headers=headers()).status_code == 404


def test_export_is_whole_session_submissions_not_absent_rows(world):
    client, _, headers = world
    response = client.get("/api/v1/export/session/meeting?format=json", headers=headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data["records"]) == 6
    assert {row["student_id"] for row in data["records"]} == {f"s{i}" for i in range(6)}
    assert data["summary"]["checked_in_count"] == 6


@pytest.mark.parametrize("value, expected", [
    ("2026-10-23T03:19:59.092334Z", "Oct 23, 2026, 11:19:59 AM SGT"),
    ("2026-10-23T20:01:02Z", "Oct 24, 2026, 04:01:02 AM SGT"),
    ("2026-10-23T11:19:59+08:00", "Oct 23, 2026, 11:19:59 AM SGT"),
    (None, ""),
])
def test_csv_uses_readable_singapore_checkin_times_without_mutating_json(value, expected):
    import csv
    import io
    from app.main import EXPORT_COLUMNS, _records_csv_response
    record = dict.fromkeys(EXPORT_COLUMNS)
    record["checked_in_at"] = value
    response = _records_csv_response([record], "attendance.csv")
    row = next(csv.DictReader(io.StringIO(response.body.decode())))
    assert row["checked_in_at"] == expected
    assert record["checked_in_at"] == value


@pytest.mark.parametrize("status", ["active", "closed"])
def test_calendar_rejects_timing_changes_after_activation(world, status):
    client, db, headers = world
    meeting = db.get(Meeting, "meeting")
    meeting.status = status
    if status == "active":
        meeting.scheduled_start = datetime.utcnow() - timedelta(minutes=1)
        meeting.scheduled_end = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    response = client.patch("/api/v1/sessions/meeting", headers=headers(), json={"scheduled_start": (datetime.utcnow() + timedelta(days=2)).isoformat() + "Z"})
    assert response.status_code == 409, response.text


def test_calendar_scheduled_move_duration_lifecycle_and_permissions(world):
    client, db, headers = world
    meeting = db.get(Meeting, "meeting")
    start = datetime.utcnow() + timedelta(days=2)
    meeting.status = "scheduled"
    meeting.scheduled_start = meeting.checkin_opens_at = start
    meeting.scheduled_end = meeting.checkin_closes_at = start + timedelta(hours=1)
    db.commit()
    payload = {"scheduled_start": (start + timedelta(hours=2)).isoformat() + "Z", "scheduled_end": (start + timedelta(hours=3)).isoformat() + "Z"}
    assert client.patch("/api/v1/sessions/meeting", headers=headers("other"), json=payload).status_code == 403
    assert client.get("/api/v1/sessions/meeting", headers=headers("other")).status_code == 403
    assert client.get("/api/v1/sessions/?course_id=course", headers=headers("other")).json()["total"] == 0
    response = client.patch("/api/v1/sessions/meeting", headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["scheduled_start"].startswith((start + timedelta(hours=2)).isoformat())
    assert client.patch("/api/v1/sessions/meeting", headers=headers(), json={"status": "active"}).status_code == 200
    assert client.patch("/api/v1/sessions/meeting", headers=headers(), json=payload).status_code == 409
    assert client.patch("/api/v1/sessions/meeting", headers=headers(), json={"status": "closed"}).status_code == 200
