"""Admin TA assignment endpoints (RBAC step 8); isolated in-memory SQLite.

GET/POST /admin/courses/{course_id}/tas and DELETE /admin/courses/{course_id}/tas/{user_id}.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-ta-admin-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-ta-admin-secret-with-at-least-32-characters"
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
from app.models import AuditLog, CheckIn, Course, CourseAssistant, Session as Meeting, User

ROLES = {"admin": "admin", "ia": "instructor", "t1": "ta", "t2": "ta", "sa": "student"}


@pytest.fixture
def world():
    now = datetime.utcnow()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused")
                    for uid, role in ROLES.items()])
        db.add(User(id="t_off", role="ta", email="t_off@example.edu", full_name="Off", hashed_password="unused", is_active=False))
        db.add_all([Course(id="A", code="A100", name="A", semester="S1", instructor_id="ia"),
                    Course(id="B", code="B100", name="B", semester="S1", instructor_id="ia")])
        db.add(Meeting(id="m_a", course_id="A", instructor_id="ia", name="m_a", status="closed",
                       scheduled_start=now - timedelta(days=1), scheduled_end=now - timedelta(days=1, hours=-1),
                       checkin_opens_at=now - timedelta(days=1, minutes=15), checkin_closes_at=now - timedelta(days=1, minutes=-30)))
        db.add(CheckIn(id="c_a", session_id="m_a", student_id="sa", status="flagged",
                       checked_in_at=now - timedelta(days=1), risk_score=0.6, risk_factors="[]"))
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def call(uid, path, method="GET", json=None):
            headers = {"Authorization": "Bearer " + create_access_token(uid, ROLES[uid])} if uid else {}
            return client.request(method, "/api/v1" + path, headers=headers, json=json)
        yield call, db
        app.dependency_overrides.clear()
    engine.dispose()


def assign(call, course="A", **body):
    return call("admin", f"/admin/courses/{course}/tas", method="POST", json=body)


# --- POST -------------------------------------------------------------------

def test_assign_by_user_id(world):
    call, db = world
    response = assign(call, user_id="t1")
    assert response.status_code == 201, response.text
    data = response.json()
    assert {k: data[k] for k in ("course_id", "user_id", "email", "full_name", "is_active")} == {
        "course_id": "A", "user_id": "t1", "email": "t1@example.edu", "full_name": "User t1", "is_active": True}
    assert data["id"] and data["assigned_at"]
    assert db.query(CourseAssistant).filter_by(course_id="A", user_id="t1").count() == 1


def test_assign_by_email_is_case_insensitive(world):
    call, _ = world
    response = assign(call, email="T2@Example.EDU")
    assert response.status_code == 201 and response.json()["user_id"] == "t2"


@pytest.mark.parametrize("body", [{}, {"user_id": "t1", "email": "t1@example.edu"}, {"email": "not-an-email"}])
def test_assign_requires_exactly_one_valid_identifier(world, body):
    call, _ = world
    assert assign(call, **body).status_code == 422


@pytest.mark.parametrize("course, body, expected", [
    ("missing", {"user_id": "t1"}, 404),
    ("A", {"user_id": "nobody"}, 404),
    ("A", {"email": "nobody@example.edu"}, 404),
    ("A", {"user_id": "sa"}, 400),       # student
    ("A", {"user_id": "ia"}, 400),       # instructor
    ("A", {"user_id": "admin"}, 400),
    ("A", {"user_id": "t_off"}, 400),    # inactive TA
])
def test_assign_validation(world, course, body, expected):
    call, db = world
    assert assign(call, course, **body).status_code == expected
    assert db.query(CourseAssistant).count() == 0


def test_duplicate_assignment_is_409(world):
    call, db = world
    assert assign(call, user_id="t1").status_code == 201
    assert assign(call, user_id="t1").status_code == 409
    assert assign(call, email="t1@example.edu").status_code == 409
    assert db.query(CourseAssistant).count() == 1


def test_many_tas_per_course_and_many_courses_per_ta(world):
    call, _ = world
    for course, uid in (("A", "t1"), ("A", "t2"), ("B", "t1")):
        assert assign(call, course, user_id=uid).status_code == 201
    assert {i["user_id"] for i in call("admin", "/admin/courses/A/tas").json()["items"]} == {"t1", "t2"}
    assert {i["id"] for i in call("t1", "/courses/my-courses").json()["items"]} == {"A", "B"}


# --- GET --------------------------------------------------------------------

def test_list_assignments(world):
    call, _ = world
    assign(call, user_id="t2")
    assign(call, user_id="t1")
    data = call("admin", "/admin/courses/A/tas").json()
    assert data["course_id"] == "A" and data["total"] == 2
    assert [i["user_id"] for i in data["items"]] == ["t1", "t2"]  # ordered by name
    assert call("admin", "/admin/courses/B/tas").json() == {"course_id": "B", "items": [], "total": 0}
    assert call("admin", "/admin/courses/missing/tas").status_code == 404


# --- DELETE -----------------------------------------------------------------

def test_unassign(world):
    call, db = world
    assign(call, user_id="t1")
    assert call("admin", "/admin/courses/A/tas/t1", method="DELETE").status_code == 204
    assert db.query(CourseAssistant).count() == 0
    assert call("admin", "/admin/courses/A/tas/t1", method="DELETE").status_code == 404
    assert call("admin", "/admin/courses/missing/tas/t1", method="DELETE").status_code == 404


def test_unassign_only_touches_that_course(world):
    call, _ = world
    assign(call, "A", user_id="t1")
    assign(call, "B", user_id="t1")
    assert call("admin", "/admin/courses/A/tas/t1", method="DELETE").status_code == 204
    assert {i["id"] for i in call("t1", "/courses/my-courses").json()["items"]} == {"B"}


# --- Access control ---------------------------------------------------------

@pytest.mark.parametrize("uid", ["ia", "t1", "sa", None])
def test_admin_only(world, uid):
    call, db = world
    denied = (401, 403) if uid is None else (403,)
    assert call(uid, "/admin/courses/A/tas").status_code in denied
    assert call(uid, "/admin/courses/A/tas", method="POST", json={"user_id": "t1"}).status_code in denied
    db.add(CourseAssistant(course_id="A", user_id="t2"))
    db.commit()
    assert call(uid, "/admin/courses/A/tas/t2", method="DELETE").status_code in denied
    assert db.query(CourseAssistant).count() == 1


# --- Audit and effect -------------------------------------------------------

def test_assign_and_unassign_are_audited(world):
    call, db = world
    assignment_id = assign(call, user_id="t1").json()["id"]
    call("admin", "/admin/courses/A/tas/t1", method="DELETE")
    rows = db.query(AuditLog).filter(AuditLog.resource_type == "course_assistant").order_by(AuditLog.timestamp).all()
    assert [r.action for r in rows] == ["user_updated", "user_updated"]
    assert all(r.user_id == "admin" and r.resource_id == assignment_id and r.success for r in rows)
    details = [json.loads(r.details) if isinstance(r.details, str) else r.details for r in rows]
    assert [d["change"] for d in details] == ["ta_assigned", "ta_unassigned"]
    assert all(d["course_id"] == "A" and d["ta_id"] == "t1" for d in details)


def test_failed_assignment_is_not_audited(world):
    call, db = world
    assign(call, user_id="sa")
    assert db.query(AuditLog).filter(AuditLog.resource_type == "course_assistant").count() == 0


def test_assignment_grants_and_revokes_ta_access(world):
    call, _ = world
    assert call("t1", "/checkins/session/m_a").status_code == 403
    assign(call, user_id="t1")
    assert call("t1", "/checkins/session/m_a").status_code == 200
    assert call("t1", "/checkins/flagged").json()["total"] == 1
    call("admin", "/admin/courses/A/tas/t1", method="DELETE")
    assert call("t1", "/checkins/session/m_a").status_code == 403
    assert call("t1", "/checkins/flagged").json()["total"] == 0
