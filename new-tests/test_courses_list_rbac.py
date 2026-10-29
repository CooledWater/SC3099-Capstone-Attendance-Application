"""GET /courses/ and GET /courses/{id} role scoping (RBAC steps 1-2); isolated in-memory SQLite."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-courses-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-courses-test-secret-with-at-least-32-characters"
os.environ["STRICT_SECURITY_MODE"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app, CATALOGUE_COURSE_FIELDS
from app.auth import create_access_token
from app.database import Base, get_db, get_read_db
from app.models import Course, Enrollment, User

URL = "/api/v1/courses/"
T0 = datetime(2026, 1, 1)
ROLES = {"admin": "admin", "ia": "instructor", "ib": "instructor", "ta": "ta", "sa": "student", "sd": "student", "idle": "instructor"}
SENSITIVE = ("instructor_id", "venue_name", "venue_latitude", "venue_longitude", "geofence_radius_meters",
             "require_face_recognition", "require_device_binding", "risk_threshold", "semester_start_date")


@pytest.fixture
def world():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused")
                    for uid, role in ROLES.items()])
        db.add(User(id="gone", role="admin", email="gone@example.edu", full_name="Gone", hashed_password="unused", is_active=False))
        courses = [
            Course(id="a1", code="A1", name="A one", semester="S1", instructor_id="ia", venue_name="LT1",
                   venue_latitude=1.3, venue_longitude=103.6, risk_threshold=0.4, created_at=T0),
            Course(id="a2", code="A2", name="A two", semester="S1", instructor_id="ia", created_at=T0 + timedelta(days=1)),
            Course(id="b1", code="B1", name="B one", semester="S1", instructor_id="ib", created_at=T0 + timedelta(days=2)),
            Course(id="u1", code="U1", name="Unassigned", semester="S1", instructor_id=None, created_at=T0 + timedelta(days=3)),
            Course(id="old", code="OLD", name="Inactive", semester="S0", instructor_id="ia", is_active=False, created_at=T0),
        ]
        db.add_all(courses)
        db.add(Enrollment(id="e1", student_id="sa", course_id="a1"))
        db.add(Enrollment(id="e2", student_id="sd", course_id="a1", is_active=False, dropped_at=T0))
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def get(uid=None, path=URL, **params):
            headers = {"Authorization": "Bearer " + create_access_token(uid, "admin" if uid == "gone" else ROLES[uid])} if uid else {}
            return client.get(path, params=params, headers=headers)
        yield get
        app.dependency_overrides.clear()
    engine.dispose()


def ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_anonymous_gets_empty_page_with_contract_shape(world):
    response = world(limit=10, offset=0)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 10, "offset": 0}


def test_admin_sees_all_active_courses_newest_first(world):
    response = world("admin")
    assert ids(response) == ["u1", "b1", "a2", "a1"]
    assert response.json()["total"] == 4
    assert response.json()["items"][-1]["venue_latitude"] == 1.3


def test_admin_instructor_id_filter(world):
    response = world("admin", instructor_id="ia")
    assert ids(response) == ["a2", "a1"] and response.json()["total"] == 2
    assert ids(world("admin", instructor_id="ia", is_active=False)) == ["old"]


def test_instructor_sees_only_assigned_courses(world):
    assert ids(world("ia")) == ["a2", "a1"]
    assert ids(world("ib")) == ["b1"]
    assert ids(world("idle")) == []
    assert ids(world("ia", is_active=False)) == ["old"]


def test_instructor_cannot_widen_scope_with_instructor_id_filter(world):
    response = world("ia", instructor_id="ib")
    assert ids(response) == ["a2", "a1"] and response.json()["total"] == 2


def test_instructor_rows_keep_full_course_contract(world):
    item = world("ia").json()["items"][-1]
    assert item["instructor_id"] == "ia" and item["instructor_name"] == "User ia"
    assert item["venue_name"] == "LT1" and item["risk_threshold"] == 0.4


def test_ta_fails_closed_without_assignment_model(world):
    response = world("ta")
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_student_gets_catalogue_of_all_courses_without_sensitive_fields(world):
    response = world("sa")
    assert ids(response) == ["u1", "b1", "a2", "a1"]  # includes courses the student is not enrolled in
    for item in response.json()["items"]:
        assert set(item) == set(CATALOGUE_COURSE_FIELDS)
        assert not set(SENSITIVE) & set(item)
    assert response.json()["items"][-1]["instructor_name"] == "User ia"


def test_student_instructor_id_filter_is_ignored(world):
    assert ids(world("sa", instructor_id="ib")) == ["u1", "b1", "a2", "a1"]


def test_pagination_total_respects_scope(world):
    page = world("admin", limit=2, offset=1).json()
    assert [i["id"] for i in page["items"]] == ["b1", "a2"]
    assert page["total"] == 4 and page["limit"] == 2 and page["offset"] == 1
    beyond = world("ia", limit=2, offset=5).json()
    assert beyond["items"] == [] and beyond["total"] == 2


def test_supplied_invalid_or_inactive_token_is_rejected_not_treated_as_anonymous(world):
    assert world("gone").status_code == 401
    from app.main import app as live_app
    client = TestClient(live_app)
    assert client.get(URL, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


# --- GET /courses/{id} (step 2) ---------------------------------------------

def detail(world, uid, course_id):
    return world(uid, path=URL + course_id)


FULL_FIELDS = set(CATALOGUE_COURSE_FIELDS) | set(SENSITIVE)


def test_detail_requires_authentication(world):
    assert world(path=URL + "a1").status_code in (401, 403)


def test_detail_admin_gets_full_object_for_any_course(world):
    for course_id in ("a1", "b1", "u1", "old"):
        response = detail(world, "admin", course_id)
        assert response.status_code == 200, response.text
        assert set(response.json()) == FULL_FIELDS


def test_detail_assigned_instructor_gets_full_object(world):
    response = detail(world, "ia", "a1")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == FULL_FIELDS
    assert data["venue_latitude"] == 1.3 and data["risk_threshold"] == 0.4
    assert detail(world, "ia", "old").status_code == 200  # inactive but still assigned


@pytest.mark.parametrize("uid, course_id", [("ia", "b1"), ("ib", "a1"), ("ia", "u1"), ("idle", "a1")])
def test_detail_unassigned_instructor_is_forbidden(world, uid, course_id):
    response = detail(world, uid, course_id)
    assert response.status_code == 403
    assert "venue" not in response.text


@pytest.mark.parametrize("course_id", ["a1", "b1", "u1"])
def test_detail_ta_fails_closed(world, course_id):
    assert detail(world, "ta", course_id).status_code == 403


def test_detail_enrolled_student_gets_full_object(world):
    response = detail(world, "sa", "a1")
    assert response.status_code == 200
    assert set(response.json()) == FULL_FIELDS and response.json()["venue_name"] == "LT1"


@pytest.mark.parametrize("uid, course_id", [("sa", "b1"), ("sa", "u1"), ("sd", "a1")])
def test_detail_unenrolled_or_dropped_student_gets_catalogue_only(world, uid, course_id):
    response = detail(world, uid, course_id)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == set(CATALOGUE_COURSE_FIELDS)
    assert data["id"] == course_id and data["code"] and data["name"]  # graded test_get_course_details fields


def test_detail_unknown_course_is_404_for_every_role(world):
    for uid in ("admin", "ia", "ta", "sa"):
        assert detail(world, uid, "missing").status_code == 404
