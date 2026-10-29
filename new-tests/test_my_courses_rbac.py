"""GET /courses/my-courses and the course_assistants model (RBAC step 6); isolated in-memory SQLite."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-mycourses-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-my-courses-secret-with-at-least-32-characters"
os.environ["STRICT_SECURITY_MODE"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.auth import create_access_token
from app.database import Base, get_db, get_read_db
from app.models import Course, CourseAssistant, Enrollment, User

URL = "/api/v1/courses/my-courses"
T0 = datetime(2026, 1, 1)
ROLES = {"admin": "admin", "ia": "instructor", "ib": "instructor", "idle": "instructor",
         "t1": "ta", "t2": "ta", "t3": "ta", "sa": "student", "sn": "student"}
FULL_FIELDS = {"id", "code", "name", "semester", "semester_start_date", "instructor_id", "instructor_name",
               "venue_name", "venue_latitude", "venue_longitude", "geofence_radius_meters",
               "require_face_recognition", "require_device_binding", "risk_threshold", "is_active", "created_at"}


@pytest.fixture
def world():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=uid, role=role, email=f"{uid}@example.edu", full_name=f"User {uid}", hashed_password="unused")
                    for uid, role in ROLES.items()])
        db.add_all([
            Course(id="a1", code="A1", name="A one", semester="S1", instructor_id="ia", venue_name="LT1", created_at=T0),
            Course(id="a2", code="A2", name="A two", semester="S1", instructor_id="ia", created_at=T0 + timedelta(days=1)),
            Course(id="b1", code="B1", name="B one", semester="S1", instructor_id="ib", created_at=T0 + timedelta(days=2)),
            Course(id="u1", code="U1", name="Unassigned", semester="S1", instructor_id=None, created_at=T0 + timedelta(days=3)),
            Course(id="old", code="OLD", name="Inactive", semester="S0", instructor_id="ia", is_active=False, created_at=T0),
        ])
        db.add_all([
            # t1 assists several courses; a1 has several TAs; t3 has none.
            CourseAssistant(course_id="a1", user_id="t1"),
            CourseAssistant(course_id="b1", user_id="t1"),
            CourseAssistant(course_id="old", user_id="t1"),
            CourseAssistant(course_id="a1", user_id="t2"),
        ])
        db.add_all([
            Enrollment(id="e1", student_id="sa", course_id="a1"),
            Enrollment(id="e2", student_id="sa", course_id="b1", is_active=False, dropped_at=T0),
        ])
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        client = TestClient(app)

        def get(uid=None, path=URL, **params):
            headers = {"Authorization": "Bearer " + create_access_token(uid, ROLES[uid])} if uid else {}
            return client.get(path, params=params, headers=headers)
        yield get, db
        app.dependency_overrides.clear()
    engine.dispose()


def ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.parametrize("uid, expected", [
    ("sa", ["a1"]),                    # active enrollment only; dropped b1 excluded
    ("sn", []),
    ("ia", ["a2", "a1"]),              # newest first, same ordering as GET /courses/
    ("ib", ["b1"]),
    ("idle", []),
    ("t1", ["b1", "a1"]),              # multiple courses per TA
    ("t2", ["a1"]),                    # multiple TAs per course
    ("t3", []),                        # unassigned TA
    ("admin", ["u1", "b1", "a2", "a1"]),
])
def test_scope_by_role(world, uid, expected):
    get, _ = world
    response = get(uid)
    assert ids(response) == expected
    assert response.json()["total"] == len(expected)


@pytest.mark.parametrize("uid, expected", [("t1", ["old"]), ("ia", ["old"]), ("admin", ["old"]), ("sa", [])])
def test_is_active_filter(world, uid, expected):
    get, _ = world
    assert ids(get(uid, is_active=False)) == expected


def test_response_contract_matches_course_list_and_taview(world):
    get, _ = world
    data = get("t1").json()
    assert set(data) == {"items", "total", "limit", "offset"}
    assert data["limit"] == 50 and data["offset"] == 0
    for item in data["items"]:
        assert set(item) == FULL_FIELDS
    a1 = next(item for item in data["items"] if item["id"] == "a1")
    # TaView.tsx reads items[].id/code/name.
    assert (a1["code"], a1["name"], a1["instructor_name"], a1["venue_name"]) == ("A1", "A one", "User ia", "LT1")


def test_pagination(world):
    get, _ = world
    page = get("admin", limit=2, offset=1).json()
    assert [item["id"] for item in page["items"]] == ["b1", "a2"]
    assert (page["total"], page["limit"], page["offset"]) == (4, 2, 1)
    beyond = get("t1", limit=1, offset=5).json()
    assert beyond["items"] == [] and beyond["total"] == 2
    clamped = get("admin", limit=1000, offset=-3).json()
    assert (clamped["limit"], clamped["offset"]) == (100, 0)


def test_requires_authentication(world):
    get, _ = world
    assert get().status_code in (401, 403)
    client = TestClient(app)
    assert client.get(URL, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_route_is_not_captured_by_course_detail(world):
    get, _ = world
    response = get("t1")
    assert response.status_code == 200
    assert response.json().get("detail") != "Course not found"
    # Course detail still works next to it.
    assert get("admin", path="/api/v1/courses/a1").json()["id"] == "a1"


def test_assignment_changes_are_visible_immediately(world):
    get, db = world
    db.add(CourseAssistant(course_id="u1", user_id="t3"))
    db.commit()
    assert ids(get("t3")) == ["u1"]
    db.query(CourseAssistant).filter_by(course_id="u1", user_id="t3").delete()
    db.commit()
    assert ids(get("t3")) == []


def test_duplicate_assignment_is_rejected_by_unique_index(world):
    _, db = world
    db.add(CourseAssistant(course_id="a1", user_id="t1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_course_assistants_schema(world):
    _, db = world
    inspector = inspect(db.get_bind())
    columns = {column["name"] for column in inspector.get_columns("course_assistants")}
    assert columns == {"id", "course_id", "user_id", "created_at"}
    foreign = {(fk["constrained_columns"][0], fk["referred_table"]) for fk in inspector.get_foreign_keys("course_assistants")}
    assert foreign == {("course_id", "courses"), ("user_id", "users")}
    indexes = {index["name"]: index for index in inspector.get_indexes("course_assistants")}
    assert indexes["ix_course_assistants_course_user"]["unique"]
    assert indexes["ix_course_assistants_user_id"]["column_names"] == ["user_id"]


def test_ta_course_list_and_detail_follow_assignments(world):
    get, _ = world
    # Step 7: GET /courses/ and GET /courses/{id} use the same assignments.
    assert ids(get("t1", path="/api/v1/courses/")) == ["b1", "a1"]
    assert get("t1", path="/api/v1/courses/a1").status_code == 200
    assert get("t1", path="/api/v1/courses/u1").status_code == 403
    assert get("t3", path="/api/v1/courses/a1").status_code == 403
