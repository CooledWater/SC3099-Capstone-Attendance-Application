"""Session scoping (RBAC steps 4-5); isolated in-memory SQLite, no external database.

GET /sessions/active: no login required, but callers only see sessions they
have a course relationship with. GET /sessions/{id}: students outside the course
get schedule metadata only. Instructor session reads use the assigned course only.
PATCH/DELETE /sessions/{id}: instructors must own the session AND be assigned to its course.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-sessions-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-session-scope-secret-with-at-least-32-characters"
os.environ["STRICT_SECURITY_MODE"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app, SESSION_METADATA_FIELDS
from app.auth import create_access_token
from app.database import Base, get_db, get_read_db
from app.models import Course, Enrollment, Session as Meeting, User

ROLES = {"admin": "admin", "ia": "instructor", "ib": "instructor", "ic": "instructor", "ta": "ta",
         "sa": "student", "sb": "student", "sd": "student", "sl": "student", "sn": "student"}
# Session -> (course, creator, open now). m_c is ic's session in ia's course; m_u is ia's session in the unassigned course.
SESSIONS = {"m_a": ("A", "ia", True), "m_b": ("B", "ib", True), "m_u": ("U", "ia", True),
            "m_c": ("A", "ic", True), "m_later": ("A", "ia", False)}
PRIVATE_FIELDS = {"instructor_id", "venue_name", "venue_latitude", "venue_longitude", "geofence_radius_meters",
                  "require_motion_check", "require_liveness_check", "require_face_match", "risk_threshold", "description"}


@pytest.fixture
def api():
    now = datetime.utcnow()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused")
                    for uid, role in ROLES.items()])
        db.add_all([Course(id="A", code="A100", name="A", semester="S1", instructor_id="ia", venue_name="LT1",
                           venue_latitude=1.3, venue_longitude=103.6),
                    Course(id="B", code="B100", name="B", semester="S1", instructor_id="ib"),
                    Course(id="U", code="U100", name="Unassigned", semester="S1", instructor_id=None)])
        db.add_all([
            Enrollment(id="e_sa", student_id="sa", course_id="A", enrolled_at=now - timedelta(days=1)),
            Enrollment(id="e_sb", student_id="sb", course_id="B", enrolled_at=now - timedelta(days=1)),
            # Dropped before today's sessions started.
            Enrollment(id="e_sd", student_id="sd", course_id="A", enrolled_at=now - timedelta(days=1),
                       is_active=False, dropped_at=now - timedelta(hours=2)),
            # Enrolled after today's sessions started (late add).
            Enrollment(id="e_sl", student_id="sl", course_id="A", enrolled_at=now - timedelta(minutes=1)),
        ])
        for sid, (course, creator, open_now) in SESSIONS.items():
            start = now - timedelta(minutes=10) if open_now else now + timedelta(days=1)
            db.add(Meeting(id=sid, course_id=course, instructor_id=creator, name=sid,
                           status="active" if open_now else "scheduled",
                           scheduled_start=start, scheduled_end=start + timedelta(hours=1),
                           checkin_opens_at=start - timedelta(minutes=15), checkin_closes_at=start + timedelta(minutes=30)))
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def get(uid, path, method="GET", json=None, **params):
            headers = {"Authorization": "Bearer " + create_access_token(uid, ROLES[uid])} if uid else {}
            return client.request(method, "/api/v1" + path, params=params, headers=headers, json=json)
        yield get
        app.dependency_overrides.clear()
    engine.dispose()


def active_ids(get, uid):
    response = get(uid, "/sessions/active")
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
    return {item["id"] for item in response.json()}


# --- GET /sessions/active ---------------------------------------------------

@pytest.mark.parametrize("uid, expected", [
    (None, set()),                       # public endpoint: still 200, but nothing to show
    ("sa", {"m_a", "m_c"}),               # active enrollment in A
    ("sl", {"m_a", "m_c"}),               # late add: active enrollment, same rule as POST /checkins/
    ("sb", {"m_b"}),
    ("sd", set()),                        # dropped
    ("sn", set()),                        # no enrollments
    ("ia", {"m_a", "m_c"}),               # assigned course A only; not ia's own session in U
    ("ic", set()),                        # created m_c but is not assigned to A
    ("ta", set()),                        # no TA assignment model yet
    ("admin", {"m_a", "m_b", "m_u", "m_c"}),
])
def test_active_sessions_scope(api, uid, expected):
    assert active_ids(api, uid) == expected


def test_active_sessions_keep_summary_contract_for_enrolled_student(api):
    item = next(i for i in api("sa", "/sessions/active").json() if i["id"] == "m_a")
    assert {"id", "name", "status", "scheduled_start", "scheduled_end", "course_code", "total_enrolled"} <= set(item)
    assert item["venue_name"] == "LT1"


def test_active_sessions_rejects_bad_token_instead_of_treating_as_anonymous(api):
    client = TestClient(app)
    assert client.get("/api/v1/sessions/active", headers={"Authorization": "Bearer nope"}).status_code == 401


# --- GET /sessions/{id} -----------------------------------------------------

def test_enrolled_eligible_student_gets_full_detail(api):
    response = api("sa", "/sessions/m_a")
    assert response.status_code == 200
    assert response.json()["venue_name"] == "LT1" and "require_liveness_check" in response.json()


@pytest.mark.parametrize("uid, sid", [("sa", "m_b"), ("sa", "m_u"), ("sn", "m_a"), ("sd", "m_a"), ("sl", "m_a")])
def test_student_outside_course_gets_metadata_only(api, uid, sid):
    response = api(uid, f"/sessions/{sid}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == set(SESSION_METADATA_FIELDS)
    assert not PRIVATE_FIELDS & set(data)
    # Graded public tests read exactly these.
    assert data["id"] == sid and data["name"] == sid and data["status"] in ("scheduled", "active", "closed", "cancelled")
    for field in ("course_id", "scheduled_start", "scheduled_end", "checkin_opens_at", "checkin_closes_at"):
        assert data[field]


@pytest.mark.parametrize("uid, sid, expected", [
    ("ia", "m_a", 200), ("ia", "m_c", 200), ("ia", "m_u", 403), ("ia", "m_b", 403),
    ("ic", "m_c", 403), ("ib", "m_b", 200), ("admin", "m_u", 200), ("ta", "m_b", 403),  # TA has no assignment
])
def test_staff_session_detail(api, uid, sid, expected):
    response = api(uid, f"/sessions/{sid}")
    assert response.status_code == expected
    if expected == 200:
        assert "venue_name" in response.json()


def test_session_detail_requires_login_and_404s(api):
    assert api(None, "/sessions/m_a").status_code in (401, 403)
    assert api("sa", "/sessions/missing").status_code == 404


# --- GET /sessions/ and /sessions/my-sessions -------------------------------

def page_ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["items"]}


@pytest.mark.parametrize("uid, expected", [
    ("ia", {"m_a", "m_c", "m_later"}), ("ic", set()), ("ib", {"m_b"}),
    ("admin", set(SESSIONS)), ("ta", set()),  # TA has no course_assistants row (see test_ta_scope.py)
])
def test_session_list_scope(api, uid, expected):
    response = api(uid, "/sessions/", limit=100)
    assert page_ids(response) == expected
    assert response.json()["total"] == len(expected)


def test_session_list_filters_cannot_escape_scope(api):
    assert page_ids(api("ia", "/sessions/", course_id="U")) == set()
    assert page_ids(api("ia", "/sessions/", instructor_id="ia")) == {"m_a", "m_later"}


@pytest.mark.parametrize("uid, expected", [
    ("ia", {"m_a", "m_c", "m_later"}), ("ic", set()), ("ta", set()), ("sa", {"m_a", "m_c", "m_later"}),
])
def test_my_sessions_scope(api, uid, expected):
    response = api(uid, "/sessions/my-sessions", limit=100)
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == expected


# --- PATCH / DELETE /sessions/{id} (step 5) ---------------------------------

def patch(api, uid, sid, **fields):
    return api(uid, f"/sessions/{sid}", method="PATCH", json=fields)


@pytest.mark.parametrize("uid, sid, expected", [
    ("ia", "m_later", 200),   # owner and assigned
    ("ia", "m_a", 200),
    ("ia", "m_u", 403),       # owner, but the course has no instructor (admin-only)
    ("ic", "m_c", 403),       # owner, but not assigned to course A
    ("ia", "m_c", 403),       # assigned to A, but not the owner (spec: must be session owner)
    ("ib", "m_a", 403),
    ("ta", "m_a", 403), ("sa", "m_a", 403),
    ("admin", "m_u", 200),
])
def test_patch_requires_owner_and_assignment(api, uid, sid, expected):
    response = patch(api, uid, sid, name="Renamed")
    assert response.status_code == expected, response.text
    if expected == 200:
        assert response.json()["name"] == "Renamed"


def test_denied_patch_changes_nothing(api):
    assert patch(api, "ic", "m_c", name="Hijacked").status_code == 403
    assert api("admin", "/sessions/m_c").json()["name"] == "m_c"


def test_patch_still_cannot_move_session_to_unassigned_course(api):
    assert patch(api, "ia", "m_later", course_id="U").status_code == 403


@pytest.mark.parametrize("uid, sid", [("ic", "m_c"), ("ia", "m_u"), ("ib", "m_later"), ("ia", "m_c"), ("ta", "m_later")])
def test_delete_denied_without_owner_and_assignment(api, uid, sid):
    assert api(uid, f"/sessions/{sid}", method="DELETE").status_code == 403
    assert api("admin", f"/sessions/{sid}").status_code == 200  # still there


def test_delete_allowed_for_assigned_owner_and_admin(api):
    assert api("ia", "/sessions/m_later", method="DELETE").status_code == 204
    assert api("admin", "/sessions/m_later").status_code == 404
    # Permission passes for admin; status rule (scheduled only) still applies afterwards.
    assert api("admin", "/sessions/m_u", method="DELETE").status_code == 400
