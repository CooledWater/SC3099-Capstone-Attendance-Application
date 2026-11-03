"""Session-level TA RBAC (session_assistants); isolated in-memory SQLite.

Course SC3099 ("A") has sessions s1-s4; course "B" has b1. TAs reach a session
only through an admin session assignment AND their course assignment. Course
assignment alone shows the course but zero sessions.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-ta-session-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-ta-session-secret-with-at-least-32-characters"
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
from app.models import AuditLog, CheckIn, Course, CourseAssistant, Enrollment, Session as Meeting, SessionAssistant, User

ROLES = {"admin": "admin", "ia": "instructor", "ib": "instructor", "tA": "ta", "tB": "ta", "t0": "ta",
         "tX": "ta", "t_off": "ta", "sa": "student", "sb": "student"}
A_SESSIONS = ("s1", "s2", "s3", "s4")
CHECKINS = {"s1": "c1", "s2": "c2", "s3": "c3", "s4": "c4", "b1": "cb"}
SESSION_READS = ["/sessions/{s}", "/checkins/session/{s}", "/checkins/{c}", "/sessions/{s}/attendance", "/stats/sessions/{s}"]


@pytest.fixture
def world():
    now = datetime.utcnow()
    start = now - timedelta(minutes=10)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused",
                         is_active=uid != "t_off") for uid, role in ROLES.items()])
        db.add_all([Course(id="A", code="SC3099", name="Capstone", semester="S1", instructor_id="ia"),
                    Course(id="B", code="B100", name="Other", semester="S1", instructor_id="ib")])
        # tA, tB, t0 and t_off assist SC3099; tX assists nothing. No session assignments yet.
        db.add_all([CourseAssistant(course_id="A", user_id=uid) for uid in ("tA", "tB", "t0", "t_off")])
        db.add_all([Enrollment(student_id="sa", course_id="A", enrolled_at=now - timedelta(days=1)),
                    Enrollment(student_id="sb", course_id="B", enrolled_at=now - timedelta(days=1))])
        for sid, course, owner in [*((sid, "A", "ia") for sid in A_SESSIONS), ("b1", "B", "ib")]:
            db.add(Meeting(id=sid, course_id=course, instructor_id=owner, name=sid, status="active",
                           scheduled_start=start, scheduled_end=start + timedelta(hours=1),
                           checkin_opens_at=start - timedelta(minutes=15), checkin_closes_at=start + timedelta(minutes=30)))
        for sid, cid in CHECKINS.items():
            student = "sb" if sid == "b1" else "sa"
            db.add(CheckIn(id=cid, session_id=sid, student_id=student, status="flagged", checked_in_at=now,
                           risk_score=0.6, risk_factors="[]"))
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def call(uid, path, method="GET", json=None, **params):
            headers = {"Authorization": "Bearer " + create_access_token(uid, ROLES[uid])} if uid else {}
            return client.request(method, "/api/v1" + path, headers=headers, params=params, json=json)
        yield call, db
        app.dependency_overrides.clear()
    engine.dispose()


def assign_sessions(call, ta, session_ids, course="A", actor="admin"):
    return call(actor, f"/admin/courses/{course}/tas/{ta}/sessions", method="POST", json={"session_ids": session_ids})


def session_ids(call, uid):
    response = call(uid, "/sessions/", limit=100)
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["items"]}


def visible_everywhere(call, uid):
    """Session ids a user can see through every list endpoint (they must agree)."""
    listed = session_ids(call, uid)
    assert {item["id"] for item in call(uid, "/sessions/active").json()} == listed
    assert {item["id"] for item in call(uid, "/sessions/my-sessions", limit=100).json()} == listed
    return listed


def flagged_ids(call, uid, **params):
    response = call(uid, "/checkins/flagged", **params)
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["items"]}


def can_read(call, uid, sid):
    codes = {call(uid, path.format(s=sid, c=CHECKINS[sid])).status_code for path in SESSION_READS}
    assert len(codes) == 1, f"inconsistent access for {uid} on {sid}: {codes}"
    return codes == {200}


# 1. Course but no sessions -------------------------------------------------

def test_course_only_ta_sees_course_but_zero_sessions(world):
    call, _ = world
    assert {c["id"] for c in call("t0", "/courses/").json()["items"]} == {"A"}
    assert call("t0", "/courses/A").status_code == 200
    assert call("t0", "/enrollments/course/A").status_code == 200  # Roster stays course-level.
    assert visible_everywhere(call, "t0") == set()
    assert flagged_ids(call, "t0") == set()
    for sid in A_SESSIONS:
        assert not can_read(call, "t0", sid)
        assert call("t0", f"/checkins/{CHECKINS[sid]}/review", method="POST", json={"status": "approved"}).status_code == 403


# 2. Bulk assignment ------------------------------------------------------------

def test_admin_assigns_one_ta_to_multiple_sessions(world):
    call, db = world
    response = assign_sessions(call, "tA", ["s1", "s3", "s1"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assigned"] == ["s1", "s3"] and body["already_assigned"] == []
    assert [item["session_id"] for item in body["items"]] == ["s1", "s3"] and body["total"] == 2
    # Re-assigning is idempotent and reports what already existed.
    again = assign_sessions(call, "tA", ["s3", "s4"]).json()
    assert again["assigned"] == ["s4"] and again["already_assigned"] == ["s3"]
    assert db.query(SessionAssistant).filter_by(user_id="tA").count() == 3
    listed = call("admin", "/admin/courses/A/tas/tA/sessions")
    assert listed.status_code == 200 and {i["session_id"] for i in listed.json()["items"]} == {"s1", "s3", "s4"}
    logs = db.query(AuditLog).filter_by(resource_type="session_assistant").all()
    assert len(logs) == 2 and all(log.action == "user_updated" for log in logs)


# 3. Multiple TAs per session ---------------------------------------------------

def test_multiple_tas_can_share_a_session(world):
    call, _ = world
    assert assign_sessions(call, "tA", ["s1"]).status_code == 200
    assert assign_sessions(call, "tB", ["s1", "s2"]).status_code == 200
    response = call("admin", "/admin/sessions/s1/tas")
    assert response.status_code == 200, response.text
    assert {item["user_id"] for item in response.json()["items"]} == {"tA", "tB"}
    assert all(item["course_assigned"] for item in response.json()["items"])
    assert can_read(call, "tA", "s1") and can_read(call, "tB", "s1")
    assert can_read(call, "tB", "s2") and not can_read(call, "tA", "s2")


# 4 + 5. Assigned vs unassigned sessions, including direct API calls ------------

def test_ta_reaches_only_assigned_sessions(world):
    call, db = world
    assign_sessions(call, "tA", ["s1", "s3"])
    assert visible_everywhere(call, "tA") == {"s1", "s3"}
    assert session_ids(call, "tA") == {item["id"] for item in call("tA", "/sessions/", course_id="A").json()["items"]}
    assert can_read(call, "tA", "s1") and can_read(call, "tA", "s3")
    assert not can_read(call, "tA", "s2") and not can_read(call, "tA", "s4")
    assert call("tA", "/sessions/s1").json()["require_liveness_check"] is not None
    # Review: allowed on an assigned session, forbidden on an unassigned one.
    assert call("tA", "/checkins/c2/review", method="POST", json={"status": "approved"}).status_code == 403
    assert db.get(CheckIn, "c2").status == "flagged"
    reviewed = call("tA", "/checkins/c1/review", method="POST", json={"status": "approved"})
    assert reviewed.status_code == 200 and reviewed.json()["reviewed_by_id"] == "tA"


# 6. Other courses ---------------------------------------------------------------

def test_ta_cannot_reach_or_be_assigned_sessions_of_other_courses(world):
    call, _ = world
    assign_sessions(call, "tA", ["s1"])
    assert not can_read(call, "tA", "b1")
    assert "b1" not in session_ids(call, "tA")
    assert call("tA", "/courses/B").status_code == 403
    # A session from another course cannot be assigned under SC3099 ...
    response = assign_sessions(call, "tA", ["s2", "b1"])
    assert response.status_code == 400 and "b1" in response.json()["detail"]
    assert not can_read(call, "tA", "s2")  # ... and the whole request is rejected.
    # ... nor under a course the TA does not assist.
    response = assign_sessions(call, "tA", ["b1"], course="B")
    assert response.status_code == 400 and "not assigned to this course" in response.json()["detail"]


# 7. Attendance and flagged check-ins of unassigned sessions -------------------

def test_attendance_and_flagged_hidden_for_unassigned_sessions(world):
    call, _ = world
    assign_sessions(call, "tA", ["s1", "s3"])
    assert flagged_ids(call, "tA") == {"c1", "c3"}
    assert flagged_ids(call, "tA", session_id="s2") == set()
    assert flagged_ids(call, "tA", course_id="A") == {"c1", "c3"}
    assert flagged_ids(call, "tA", course_id="B") == set()
    for path in ("/sessions/s2/attendance", "/checkins/session/s2", "/stats/sessions/s2", "/checkins/c2"):
        assert call("tA", path).status_code == 403, path


# 8. Exports ---------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/export/session/s1", "/export/session/s2", "/export/attendance/A"])
def test_ta_cannot_export_attendance(world, path):
    call, _ = world
    assign_sessions(call, "tA", ["s1"])
    # Exports stay instructor/admin only, so unassigned sessions are never exportable by a TA.
    assert call("tA", path).status_code == 403


# 9 + 10. Revocation ------------------------------------------------------------

def test_removing_a_session_assignment_revokes_immediately(world):
    call, _ = world
    assign_sessions(call, "tA", ["s1", "s3"])
    assert call("admin", "/admin/courses/A/tas/tA/sessions/s1", method="DELETE").status_code == 204
    assert not can_read(call, "tA", "s1") and can_read(call, "tA", "s3")
    assert visible_everywhere(call, "tA") == {"s3"}
    assert flagged_ids(call, "tA") == {"c3"}
    assert call("admin", "/admin/courses/A/tas/tA/sessions/s1", method="DELETE").status_code == 404
    # The path's course must match the session's course.
    assert call("admin", "/admin/courses/B/tas/tA/sessions/s3", method="DELETE").status_code == 404


def test_removing_course_assignment_revokes_all_its_sessions(world):
    call, db = world
    assign_sessions(call, "tA", ["s1", "s2", "s3"])
    assert call("admin", "/admin/courses/A/tas/tA", method="DELETE").status_code == 204
    assert db.query(SessionAssistant).filter_by(user_id="tA").count() == 0
    assert visible_everywhere(call, "tA") == set()
    assert not any(can_read(call, "tA", sid) for sid in A_SESSIONS)
    assert call("tA", "/courses/A").status_code == 403
    # Re-adding the course does not restore the old session assignments.
    assert call("admin", "/admin/courses/A/tas", method="POST", json={"user_id": "tA"}).status_code == 201
    assert visible_everywhere(call, "tA") == set()


def test_session_access_also_requires_the_course_assignment(world):
    call, db = world
    assign_sessions(call, "tA", ["s1"])
    # Even if a stale session row survives (e.g. a course row removed directly), access is denied.
    db.query(CourseAssistant).filter_by(course_id="A", user_id="tA").delete()
    db.commit()
    assert db.query(SessionAssistant).filter_by(user_id="tA").count() == 1
    assert not can_read(call, "tA", "s1")
    assert visible_everywhere(call, "tA") == set()
    assert call("admin", "/admin/sessions/s1/tas").json()["items"][0]["course_assigned"] is False


def test_deleting_a_scheduled_session_removes_its_ta_assignments(world):
    call, db = world
    meeting = db.get(Meeting, "s4")
    future = datetime.utcnow() + timedelta(days=1)
    meeting.status = "scheduled"
    meeting.scheduled_start, meeting.scheduled_end = future, future + timedelta(hours=1)
    meeting.checkin_opens_at, meeting.checkin_closes_at = future, future + timedelta(minutes=30)
    db.query(CheckIn).filter_by(session_id="s4").delete()
    db.commit()
    assign_sessions(call, "tA", ["s4"])
    assert call("ia", "/sessions/s4", method="DELETE").status_code == 204
    assert db.query(SessionAssistant).filter_by(session_id="s4").count() == 0


# 11. Only admins manage session assignments ----------------------------------

@pytest.mark.parametrize("uid", ["ia", "tA", "t0", "sa", None])
def test_non_admins_cannot_manage_session_assignments(world, uid):
    call, db = world
    assign_sessions(call, "tA", ["s1"])
    expected = 403  # Missing bearer credentials are also 403 in this API.
    assert assign_sessions(call, "tA", ["s2"], actor=uid).status_code == expected
    assert assign_sessions(call, "t0", ["s1"], actor=uid).status_code == expected
    assert call(uid, "/admin/courses/A/tas/tA/sessions").status_code == expected
    assert call(uid, "/admin/courses/A/tas/tA/sessions/s1", method="DELETE").status_code == expected
    assert call(uid, "/admin/sessions/s1/tas").status_code == expected
    assert {row.session_id for row in db.query(SessionAssistant).filter_by(user_id="tA")} == {"s1"}
    assert db.query(SessionAssistant).filter_by(user_id="t0").count() == 0


@pytest.mark.parametrize("ta, session_list, status, detail", [
    ("sa", ["s1"], 400, "not a teaching assistant"),
    ("ia", ["s1"], 400, "not a teaching assistant"),
    ("nobody", ["s1"], 404, "User not found"),
    ("tX", ["s1"], 400, "not assigned to this course"),
    ("t_off", ["s1"], 400, "inactive"),
    ("tA", ["missing"], 404, "Session not found"),
])
def test_assignment_validation(world, ta, session_list, status, detail):
    call, db = world
    response = assign_sessions(call, ta, session_list)
    assert response.status_code == status and detail in response.json()["detail"], response.text
    assert db.query(SessionAssistant).count() == 0


def test_assignment_payload_and_missing_course(world):
    call, _ = world
    assert assign_sessions(call, "tA", []).status_code == 422
    assert call("admin", "/admin/courses/A/tas/tA/sessions", method="POST", json={}).status_code == 422
    assert assign_sessions(call, "tA", ["s1"], course="missing").status_code == 404
    assert call("admin", "/admin/sessions/missing/tas").status_code == 404


# 12. Other roles are unchanged -----------------------------------------------

def test_admin_instructor_and_student_permissions_unchanged(world):
    call, _ = world
    assign_sessions(call, "tA", ["s1"])
    assert session_ids(call, "admin") == {*A_SESSIONS, "b1"}
    assert all(can_read(call, "admin", sid) for sid in (*A_SESSIONS, "b1"))
    assert visible_everywhere(call, "ia") == set(A_SESSIONS)
    assert all(can_read(call, "ia", sid) for sid in A_SESSIONS) and not can_read(call, "ia", "b1")
    assert flagged_ids(call, "ia") == {"c1", "c2", "c3", "c4"}
    assert visible_everywhere(call, "ib") == {"b1"}
    # Students: active sessions of enrolled courses, full detail when enrolled.
    assert {item["id"] for item in call("sa", "/sessions/active").json()} == set(A_SESSIONS)
    assert call("sa", "/sessions/s2").status_code == 200
    assert call("sa", "/checkins/c2").status_code == 200  # Own check-in.
    assert call("sb", "/checkins/c2").status_code == 403
    assert call("ia", "/export/session/s2").status_code == 200
