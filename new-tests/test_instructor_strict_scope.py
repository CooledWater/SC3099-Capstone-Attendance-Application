"""Strict instructor course scope (RBAC step 3); isolated in-memory SQLite, no external database.

Instructors reach check-ins, stats, session export and student profiles only for
courses where courses.instructor_id is them. Unassigned courses are admin-only,
and creating a session in someone else's course grants nothing. The instructor
rule on GET /sessions/{id}/attendance (documented) is deliberately unchanged.
The TA in this world has no course_assistants row; see test_ta_scope.py.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-strict-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-strict-scope-secret-with-at-least-32-characters"
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
from app.models import CheckIn, Course, Enrollment, Session as Meeting, User

START = datetime(2026, 1, 10, 9)
ROLES = {"admin": "admin", "ia": "instructor", "ib": "instructor", "ic": "instructor", "ta": "ta",
         "sa": "student", "sb": "student", "su": "student"}
# Session -> (course, creator). "m_c" is ic's session inside ia's course; "m_u" is ia's session in the unassigned course.
SESSIONS = {"m_a": ("A", "ia"), "m_b": ("B", "ib"), "m_u": ("U", "ia"), "m_c": ("A", "ic")}
# Check-in -> (session, student); all flagged so they appear in the review queue.
CHECKINS = {"c_a": ("m_a", "sa"), "c_b": ("m_b", "sb"), "c_u": ("m_u", "su"), "c_c": ("m_c", "sa")}


@pytest.fixture
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused")
                    for uid, role in ROLES.items()])
        db.add_all([Course(id="A", code="A100", name="A", semester="S1", instructor_id="ia"),
                    Course(id="B", code="B100", name="B", semester="S1", instructor_id="ib"),
                    Course(id="U", code="U100", name="Unassigned", semester="S1", instructor_id=None)])
        db.add_all([Enrollment(id="e_a", student_id="sa", course_id="A", enrolled_at=START - timedelta(days=1)),
                    Enrollment(id="e_b", student_id="sb", course_id="B", enrolled_at=START - timedelta(days=1)),
                    Enrollment(id="e_u", student_id="su", course_id="U", enrolled_at=START - timedelta(days=1))])
        db.add_all([Meeting(id=sid, course_id=course, instructor_id=creator, name=sid, status="closed",
                            scheduled_start=START, scheduled_end=START + timedelta(hours=1),
                            checkin_opens_at=START - timedelta(minutes=15), checkin_closes_at=START + timedelta(minutes=20))
                    for sid, (course, creator) in SESSIONS.items()])
        db.add_all([CheckIn(id=cid, session_id=sid, student_id=student, status="flagged", checked_in_at=START,
                            risk_score=0.6, risk_factors="[]")
                    for cid, (sid, student) in CHECKINS.items()])
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def call(method, uid, path, **kwargs):
            headers = {"Authorization": "Bearer " + create_access_token(uid, ROLES[uid])}
            return client.request(method, "/api/v1" + path, headers=headers, **kwargs)
        yield call
        app.dependency_overrides.clear()
    engine.dispose()


def get(api, uid, path, **params):
    return api("GET", uid, path, params=params)


def item_ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["items"]}


# --- Check-in listings (query-level scope) ----------------------------------

@pytest.mark.parametrize("path", ["/checkins/", "/checkins/flagged"])
def test_instructor_listings_cover_only_assigned_courses(api, path):
    response = get(api, "ia", path)
    assert item_ids(response) == {"c_a", "c_c"}  # includes ic's session in A, excludes ia's session in U
    assert response.json()["total"] == 2
    assert item_ids(get(api, "ib", path)) == {"c_b"}
    assert item_ids(get(api, "ic", path)) == set()  # created m_c but is not assigned to A


@pytest.mark.parametrize("path", ["/checkins/", "/checkins/flagged"])
def test_admin_listings_unscoped(api, path):
    assert item_ids(get(api, "admin", path)) == set(CHECKINS)


def test_explicit_filters_cannot_escape_scope(api):
    assert item_ids(get(api, "ia", "/checkins/", course_id="U")) == set()
    assert item_ids(get(api, "ia", "/checkins/flagged", session_id="m_b")) == set()


def test_unassigned_ta_flagged_queue_is_empty(api):
    # This world has no course_assistants rows; assigned TAs are covered in test_ta_scope.py.
    assert item_ids(get(api, "ta", "/checkins/flagged")) == set()


# --- Single-resource checks -------------------------------------------------

ALLOWED = [("ia", "m_a"), ("ia", "m_c"), ("ib", "m_b"), ("admin", "m_u")]
DENIED = [("ia", "m_u"), ("ia", "m_b"), ("ic", "m_c"), ("ib", "m_a"), ("ta", "m_u")]  # ta: unassigned


@pytest.mark.parametrize("uid, sid", ALLOWED)
def test_session_checkins_allowed(api, uid, sid):
    assert get(api, uid, f"/checkins/session/{sid}").status_code == 200


@pytest.mark.parametrize("uid, sid", DENIED)
def test_session_checkins_denied(api, uid, sid):
    assert get(api, uid, f"/checkins/session/{sid}").status_code == 403


@pytest.mark.parametrize("uid, sid", ALLOWED)
def test_session_stats_allowed(api, uid, sid):
    assert get(api, uid, f"/stats/sessions/{sid}").status_code == 200


@pytest.mark.parametrize("uid, sid", DENIED)
def test_session_stats_denied(api, uid, sid):
    assert get(api, uid, f"/stats/sessions/{sid}").status_code == 403


@pytest.mark.parametrize("uid, sid", ALLOWED)
def test_session_export_allowed(api, uid, sid):
    assert get(api, uid, f"/export/session/{sid}", format="json").status_code == 200


@pytest.mark.parametrize("uid, sid", DENIED + [("ta", "m_a")])
def test_session_export_denied(api, uid, sid):
    assert get(api, uid, f"/export/session/{sid}", format="json").status_code == 403


@pytest.mark.parametrize("uid, cid, expected", [
    ("ia", "c_a", 200), ("ia", "c_c", 200), ("ia", "c_u", 403), ("ia", "c_b", 403), ("ic", "c_c", 403),
    ("admin", "c_u", 200), ("ta", "c_b", 403), ("sa", "c_a", 200), ("sb", "c_a", 403),
])
def test_checkin_detail(api, uid, cid, expected):
    assert get(api, uid, f"/checkins/{cid}").status_code == expected


@pytest.mark.parametrize("uid, cid, expected", [
    ("ia", "c_u", 403), ("ic", "c_c", 403), ("ib", "c_a", 403), ("ia", "c_a", 200), ("admin", "c_u", 200),
])
def test_review_requires_assignment(api, uid, cid, expected):
    response = api("POST", uid, f"/checkins/{cid}/review", json={"status": "approved"})
    assert response.status_code == expected, response.text


# --- Course stats -----------------------------------------------------------

@pytest.mark.parametrize("uid, course_id, expected", [
    ("ia", "A", 200), ("ia", "U", 403), ("ia", "B", 403), ("ic", "A", 403), ("admin", "U", 200),
])
def test_course_stats(api, uid, course_id, expected):
    assert get(api, uid, f"/stats/courses/{course_id}").status_code == expected


def test_overview_counts_only_assigned_courses(api):
    data = get(api, "ia", "/stats/overview").json()
    assert data["total_courses"] == 1 and data["total_sessions"] == 2 and data["total_students"] == 1
    assert get(api, "ic", "/stats/overview").json()["total_courses"] == 0
    assert get(api, "ia", "/stats/overview", course_id="U").status_code == 403
    assert get(api, "admin", "/stats/overview").json()["total_courses"] == 3


@pytest.mark.parametrize("uid, student, expected", [
    ("ia", "sa", 200), ("ia", "su", 403), ("ia", "sb", 403), ("ic", "sa", 403), ("admin", "su", 200),
])
def test_student_stats(api, uid, student, expected):
    assert get(api, uid, f"/stats/students/{student}").status_code == expected


# --- Student profile --------------------------------------------------------

@pytest.mark.parametrize("uid, student, expected", [
    ("ia", "sa", 200), ("ia", "su", 403), ("ia", "sb", 403), ("ic", "sa", 403), ("admin", "su", 200),
])
def test_user_profile(api, uid, student, expected):
    assert get(api, uid, f"/users/{student}").status_code == expected


# --- Attendance roster keeps its documented rule ----------------------------

@pytest.mark.parametrize("uid, sid", [("ia", "m_u"), ("ic", "m_c"), ("ia", "m_a")])
def test_attendance_roster_instructor_rule_unchanged(api, uid, sid):
    assert get(api, uid, f"/sessions/{sid}/attendance").status_code == 200
    assert get(api, "ib", "/sessions/m_a/attendance").status_code == 403
    assert get(api, "ta", "/sessions/m_b/attendance").status_code == 403  # unassigned TA (step 7)
