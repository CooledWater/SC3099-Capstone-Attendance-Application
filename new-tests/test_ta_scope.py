"""TA course scoping through course_assistants (RBAC step 7); isolated in-memory SQLite.

A TA sees courses, sessions, check-ins, the review queue, rosters and session
stats only for courses they are assigned to, and keeps the TA write limits
(review only: no session, enrollment, export or course-stats access).
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-ta-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-ta-scope-secret-with-at-least-32-characters"
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
from app.models import CheckIn, Course, CourseAssistant, Enrollment, Session as Meeting, User

ROLES = {"admin": "admin", "ia": "instructor", "ib": "instructor",
         "t1": "ta", "t2": "ta", "t0": "ta", "sa": "student", "sb": "student"}


@pytest.fixture
def world():
    now = datetime.utcnow()
    start = now - timedelta(minutes=10)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused")
                    for uid, role in ROLES.items()])
        db.add_all([Course(id="A", code="A100", name="A", semester="S1", instructor_id="ia", venue_name="LT1"),
                    Course(id="B", code="B100", name="B", semester="S1", instructor_id="ib")])
        # t1 assists A, t2 assists A and B, t0 assists nothing.
        db.add_all([CourseAssistant(course_id="A", user_id="t1"),
                    CourseAssistant(course_id="A", user_id="t2"),
                    CourseAssistant(course_id="B", user_id="t2")])
        db.add_all([Enrollment(id="e_a", student_id="sa", course_id="A", enrolled_at=now - timedelta(days=1)),
                    Enrollment(id="e_b", student_id="sb", course_id="B", enrolled_at=now - timedelta(days=1))])
        for sid, course, owner in (("m_a", "A", "ia"), ("m_b", "B", "ib")):
            db.add(Meeting(id=sid, course_id=course, instructor_id=owner, name=sid, status="active",
                           scheduled_start=start, scheduled_end=start + timedelta(hours=1),
                           checkin_opens_at=start - timedelta(minutes=15), checkin_closes_at=start + timedelta(minutes=30)))
        db.add_all([CheckIn(id="c_a", session_id="m_a", student_id="sa", status="flagged", checked_in_at=now,
                            risk_score=0.6, risk_factors="[]"),
                    CheckIn(id="c_b", session_id="m_b", student_id="sb", status="flagged", checked_in_at=now,
                            risk_score=0.6, risk_factors="[]")])
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def call(uid, path, method="GET", json=None, **params):
            headers = {"Authorization": "Bearer " + create_access_token(uid, ROLES[uid])}
            return client.request(method, "/api/v1" + path, headers=headers, params=params, json=json)
        yield call, db
        app.dependency_overrides.clear()
    engine.dispose()


def page_ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["items"]}


def list_ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()}


# --- Lists are filtered in the query ----------------------------------------

@pytest.mark.parametrize("uid, expected", [("t1", {"A"}), ("t2", {"A", "B"}), ("t0", set()), ("admin", {"A", "B"})])
def test_course_list(world, uid, expected):
    call, _ = world
    response = call(uid, "/courses/")
    assert page_ids(response) == expected and response.json()["total"] == len(expected)


def test_ta_course_list_is_full_object_not_catalogue(world):
    call, _ = world
    item = call("t1", "/courses/").json()["items"][0]
    assert item["venue_name"] == "LT1" and "risk_threshold" in item


@pytest.mark.parametrize("uid, expected", [("t1", {"m_a"}), ("t2", {"m_a", "m_b"}), ("t0", set())])
def test_session_lists(world, uid, expected):
    call, _ = world
    response = call(uid, "/sessions/", limit=100)
    assert page_ids(response) == expected and response.json()["total"] == len(expected)
    assert list_ids(call(uid, "/sessions/active")) == expected
    assert list_ids(call(uid, "/sessions/my-sessions")) == expected


def test_session_list_course_filter_cannot_escape_scope(world):
    call, _ = world
    # TaView calls /sessions/?course_id=<id> for each assigned course.
    assert page_ids(call("t1", "/sessions/", course_id="A")) == {"m_a"}
    assert page_ids(call("t1", "/sessions/", course_id="B")) == set()


@pytest.mark.parametrize("uid, expected", [("t1", {"c_a"}), ("t2", {"c_a", "c_b"}), ("t0", set()), ("admin", {"c_a", "c_b"})])
def test_flagged_queue(world, uid, expected):
    call, _ = world
    response = call(uid, "/checkins/flagged")
    assert page_ids(response) == expected and response.json()["total"] == len(expected)


def test_flagged_filters_cannot_escape_scope(world):
    call, _ = world
    assert page_ids(call("t1", "/checkins/flagged", course_id="B")) == set()
    assert page_ids(call("t1", "/checkins/flagged", session_id="m_b")) == set()


# --- Single resources -------------------------------------------------------

READS = [
    "/courses/{course}", "/sessions/{session}", "/checkins/session/{session}", "/checkins/{checkin}",
    "/sessions/{session}/attendance", "/stats/sessions/{session}", "/enrollments/course/{course}",
]
OWN = {"course": "A", "session": "m_a", "checkin": "c_a"}
OTHER = {"course": "B", "session": "m_b", "checkin": "c_b"}


@pytest.mark.parametrize("template", READS)
def test_assigned_ta_can_read(world, template):
    call, _ = world
    assert call("t1", template.format(**OWN)).status_code == 200


@pytest.mark.parametrize("template", READS)
def test_ta_cannot_read_unassigned_course(world, template):
    call, _ = world
    assert call("t1", template.format(**OTHER)).status_code == 403
    assert call("t0", template.format(**OWN)).status_code == 403


@pytest.mark.parametrize("template", READS)
def test_multi_course_ta_and_admin_read_both(world, template):
    call, _ = world
    for uid in ("t2", "admin"):
        for ids in (OWN, OTHER):
            assert call(uid, template.format(**ids)).status_code == 200


def test_session_detail_for_ta_is_full(world):
    call, _ = world
    assert "require_liveness_check" in call("t1", "/sessions/m_a").json()


def test_review_requires_assignment(world):
    call, db = world
    assert call("t1", "/checkins/c_b/review", method="POST", json={"status": "approved"}).status_code == 403
    assert db.get(CheckIn, "c_b").status == "flagged"
    response = call("t1", "/checkins/c_a/review", method="POST", json={"status": "approved"})
    assert response.status_code == 200 and response.json()["reviewed_by_id"] == "t1"


# --- TA write and analytics limits are unchanged ----------------------------

@pytest.mark.parametrize("method, path, body", [
    ("GET", "/checkins/", None),
    ("GET", "/export/session/m_a", None),
    ("GET", "/export/attendance/A", None),
    ("GET", "/stats/courses/A", None),
    ("GET", "/stats/overview", None),
    ("PATCH", "/sessions/m_a", {"name": "x"}),
    ("DELETE", "/sessions/m_a", None),
    ("POST", "/enrollments/", {"course_id": "A", "student_id": "sb"}),
    ("PUT", "/courses/A", {"name": "x"}),
])
def test_assigned_ta_still_cannot_manage(world, method, path, body):
    call, _ = world
    assert call("t1", path, method=method, json=body).status_code == 403


# --- Assignment changes take effect immediately -----------------------------

def test_unassigning_revokes_access(world):
    call, db = world
    assert call("t1", "/checkins/session/m_a").status_code == 200
    db.query(CourseAssistant).filter_by(course_id="A", user_id="t1").delete()
    db.commit()
    assert call("t1", "/checkins/session/m_a").status_code == 403
    assert page_ids(call("t1", "/checkins/flagged")) == set()
    assert page_ids(call("t1", "/courses/")) == set()


def test_students_and_instructors_unaffected(world):
    call, _ = world
    assert list_ids(call("sa", "/sessions/active")) == {"m_a"}
    assert page_ids(call("ia", "/checkins/flagged")) == {"c_a"}
    assert call("ia", "/checkins/session/m_b").status_code == 403
