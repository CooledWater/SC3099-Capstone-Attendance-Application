"""Audit-log contract tests (Module 2 <-> Module 4 AuditLogs.tsx).

Two layers:

* Unit tests (no server): the AuditLog model, the writer helper and the
  serialiser run against a throwaway in-memory SQLite database.
* HTTP tests: black-box against a running backend, like tests/conftest.py:

      TEST_BACKEND_URL=http://127.0.0.1:8765 pytest new-tests/test_audit_logs.py -v

  They WRITE data (users, a course, a session, check-ins, audit rows), so they
  never fall back to a default URL: with TEST_BACKEND_URL unset they skip.
  Point them only at a scratch backend, e.g. one started with
  DATABASE_URL=sqlite:///scratch.db - never at a server on shared data.

Module 4 (src/components/dashboard/AuditLogs.tsx) calls ``GET /audit/?limit=200``
and reads ``id, occurred_at, event_type, action, actor_email, severity, detail``
from ``items``. API-SPECIFICATION.md / the public tests want
``{items, total, limit, offset}`` with ``user_id, user_email, action,
resource_type, resource_id, ip_address, user_agent, device_id, details,
success, timestamp``. Both field sets are asserted here.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

BACKEND_URL = os.getenv("TEST_BACKEND_URL")  # deliberately no default
PASSWORD = "testpassword123"
USER_AGENT = "audit-contract-test/1.0"

MODULE4_FIELDS = {"id", "occurred_at", "event_type", "action", "actor_email", "severity", "detail"}
SPEC_FIELDS = {
    "id", "user_id", "user_email", "action", "resource_type", "resource_id",
    "ip_address", "user_agent", "device_id", "details", "success", "timestamp",
}
SEVERITIES = {"info", "warning", "critical"}

VENUE = (1.3483, 103.6831)
METERS_PER_DEGREE_LAT = 111_195.0


# =============================================================================
# Unit tests: model, writer, serialiser (in-memory SQLite, no server)
# =============================================================================

@pytest.fixture()
def unit_db():
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ.setdefault("JWT_SECRET", "unit-test-secret")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import models  # noqa: F401  (registers every table on Base.metadata)
    from app.database import Base

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_audit_logs_table_has_documented_columns_and_no_updated_at(unit_db):
    from sqlalchemy import inspect

    columns = {c["name"] for c in inspect(unit_db.get_bind()).get_columns("audit_logs")}
    assert columns == {
        "id", "user_id", "action", "resource_type", "resource_id", "ip_address",
        "user_agent", "device_id", "details", "success", "timestamp",
    }
    assert "updated_at" not in columns


def test_rows_are_immutable_through_the_orm(unit_db):
    from app.audit import create_audit_log
    from app.models import AuditLog

    entry = create_audit_log(unit_db, "logout", commit=True)
    assert entry is not None

    entry.success = False
    with pytest.raises(RuntimeError, match="immutable"):
        unit_db.commit()
    unit_db.rollback()

    unit_db.delete(unit_db.get(AuditLog, entry.id))
    with pytest.raises(RuntimeError, match="immutable"):
        unit_db.commit()
    unit_db.rollback()

    assert unit_db.query(AuditLog).count() == 1


def test_writer_rejects_unknown_action(unit_db):
    from app.audit import create_audit_log

    with pytest.raises(ValueError):
        create_audit_log(unit_db, "not_a_real_action")


def test_writer_without_commit_only_stages_the_row(unit_db):
    from app.audit import create_audit_log
    from app.models import AuditLog

    create_audit_log(unit_db, "logout")
    unit_db.rollback()
    assert unit_db.query(AuditLog).count() == 0


def test_writer_default_resource_type_follows_the_action(unit_db):
    from app.audit import create_audit_log

    assert create_audit_log(unit_db, "checkin_attempted").resource_type == "checkin"
    assert create_audit_log(unit_db, "session_created").resource_type == "session"
    assert create_audit_log(unit_db, "login_success").resource_type is None
    assert create_audit_log(unit_db, "logout", resource_type="user").resource_type == "user"


def test_oversized_details_stay_valid_json(unit_db):
    import json

    from app.audit import create_audit_log

    entry = create_audit_log(unit_db, "user_updated", details={"blob": "x" * 10_000})
    assert json.loads(entry.details) == {"truncated": True}


def test_serializer_severity_event_type_and_actor_fallbacks(unit_db):
    from app.audit import _serialize, create_audit_log

    def row(action, **kwargs):
        return _serialize(create_audit_log(unit_db, action, **kwargs), None)

    assert row("login_success")["severity"] == "info"
    assert row("login_failed", success=False)["severity"] == "warning"
    assert row("checkin_flagged")["severity"] == "warning"
    assert row("checkin_approved", success=False)["severity"] == "warning"
    assert row("security_violation")["severity"] == "critical"
    assert row("checkin_approved")["event_type"] == "checkin"
    assert row("login_failed")["event_type"] == "authentication"

    # actor_email must always be a string (Module 4 lowercases it).
    assert row("logout")["actor_email"] == "system"
    attempted = row("login_failed", details={"email": "Nobody@Example.com"})
    assert attempted["actor_email"] == "Nobody@Example.com"
    assert attempted["user_email"] is None

    detail = row("checkin_attempted", details={"session_id": "s1", "risk_score": 0.15})["detail"]
    assert detail == "session_id=s1, risk_score=0.15"
    assert row("logout")["detail"] is None


def test_serializer_timestamps_are_explicit_utc(unit_db):
    from app.audit import _serialize, create_audit_log

    entry = create_audit_log(
        unit_db, "logout", timestamp=datetime(2024, 1, 15, 14, 5, 0)
    )
    item = _serialize(entry, "a@b.com")
    assert item["timestamp"] == "2024-01-15T14:05:00Z"
    assert item["occurred_at"] == item["timestamp"]


# =============================================================================
# HTTP tests
# =============================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime) -> str:
    return value.isoformat() + "Z"


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def api():
    if not BACKEND_URL:
        pytest.skip("Set TEST_BACKEND_URL to a scratch backend (these tests write data)")
    with httpx.Client(
        base_url=BACKEND_URL, timeout=30.0, headers={"User-Agent": USER_AGENT}
    ) as client:
        try:
            client.get("/health")
        except httpx.ConnectError:
            pytest.skip(f"Backend not running at {BACKEND_URL}")
        yield client


def _register(api, role: str) -> dict:
    email = f"{role}_{uuid.uuid4().hex[:10]}@audit-test.com"
    response = api.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": f"Audit {role}", "role": role,
    })
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    login = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {
        "id": user_id,
        "email": email,
        "headers": _auth(login.json()["access_token"]),
        "token": login.json()["access_token"],
    }


@pytest.fixture(scope="module")
def admin(api):
    return _register(api, "admin")


@pytest.fixture(scope="module")
def student(api):
    return _register(api, "student")


def _audit(api, admin, **params):
    response = api.get("/api/v1/audit/", headers=admin["headers"], params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _events(api, admin, **params):
    """All entries matching the filters, newest first."""
    return _audit(api, admin, limit=1000, **params)["items"]


# --- Access control ---------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/v1/audit/", "/api/v1/audit/summary"])
def test_unauthenticated_access_is_rejected(api, path):
    assert api.get(path).status_code in (401, 403)


@pytest.mark.parametrize("path", ["/api/v1/audit/", "/api/v1/audit/summary"])
def test_invalid_token_is_rejected(api, path):
    assert api.get(path, headers=_auth("not.a.jwt")).status_code == 401


@pytest.mark.parametrize("role", ["student", "ta", "instructor"])
@pytest.mark.parametrize("path", ["/api/v1/audit/", "/api/v1/audit/summary"])
def test_non_admin_roles_get_403(api, role, path):
    # Module 4 shows the "Audit logs" tab to instructors too; the spec
    # (SECURITY-REQUIREMENTS.md) is admin-only, so they must be refused.
    user = _register(api, role)
    response = api.get(path, headers=user["headers"])
    assert response.status_code == 403
    assert "items" not in response.json() and "total_logs" not in response.json()


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_audit_collection_is_read_only_over_http(api, admin, method):
    response = getattr(api, method)("/api/v1/audit/", headers=admin["headers"])
    assert response.status_code == 405


# --- Response contract ------------------------------------------------------

def test_module4_request_shape_returns_both_field_sets(api, admin):
    """Exactly what Module 4 sends: GET /audit/?limit=200."""
    data = _audit(api, admin, limit=200)

    assert set(data) >= {"items", "total", "limit", "offset"}
    assert data["limit"] == 200 and data["offset"] == 0
    assert isinstance(data["items"], list) and data["items"], "admin's own login is logged"
    assert data["total"] >= len(data["items"])

    for item in data["items"]:
        assert MODULE4_FIELDS <= set(item)
        assert SPEC_FIELDS <= set(item)
        # Types Module 4 relies on (toLowerCase / replace / new Date / Set).
        assert isinstance(item["id"], str)
        assert isinstance(item["event_type"], str) and item["event_type"]
        assert isinstance(item["action"], str)
        assert isinstance(item["actor_email"], str) and item["actor_email"]
        assert item["severity"] in SEVERITIES
        assert item["detail"] is None or isinstance(item["detail"], str)
        assert isinstance(item["success"], bool)
        assert item["timestamp"] == item["occurred_at"]
        assert item["timestamp"].endswith("Z")
        assert _parse(item["occurred_at"]).tzinfo is not None


def test_default_limit_and_newest_first_ordering(api, admin):
    data = _audit(api, admin)
    assert data["limit"] == 100 and data["offset"] == 0

    stamps = [i["timestamp"] for i in data["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_public_test_shape_items_total(api, admin):
    """tests/public/test_observability.py::test_audit_logs_with_filters."""
    data = _audit(api, admin, limit=10)
    assert "items" in data and "total" in data
    assert len(data["items"]) <= 10


# --- Persistence of events --------------------------------------------------

def test_registration_is_logged_with_request_context(api, admin):
    user = _register(api, "student")

    (entry,) = _events(api, admin, user_id=user["id"], action="user_created")
    assert entry["resource_type"] == "user" and entry["resource_id"] == user["id"]
    assert entry["user_email"] == entry["actor_email"] == user["email"]
    assert entry["details"] == {"role": "student"}
    assert entry["success"] is True and entry["severity"] == "info"
    assert entry["event_type"] == "user"
    assert entry["ip_address"]
    assert entry["user_agent"] == USER_AGENT
    assert abs((_now() - _parse(entry["timestamp"]).replace(tzinfo=None)).total_seconds()) < 300


def test_login_success_is_logged(api, admin):
    user = _register(api, "student")  # registers then logs in
    (entry,) = _events(api, admin, user_id=user["id"], action="login_success")
    assert entry["event_type"] == "authentication"
    assert entry["actor_email"] == user["email"]


def test_failed_login_wrong_password_is_logged_without_the_password(api, admin):
    user = _register(api, "student")
    wrong = "definitely-not-the-password"
    assert api.post("/api/v1/auth/login", json={"email": user["email"], "password": wrong}).status_code == 401

    (entry,) = _events(api, admin, user_id=user["id"], action="login_failed")
    assert entry["success"] is False and entry["severity"] == "warning"
    assert entry["details"] == {"email": user["email"], "reason": "bad_password"}

    dump = api.get("/api/v1/audit/", headers=admin["headers"], params={"limit": 1000}).text
    assert wrong not in dump and PASSWORD not in dump


def test_failed_login_unknown_email_is_logged_with_no_user(api, admin):
    email = f"ghost_{uuid.uuid4().hex[:10]}@audit-test.com"
    assert api.post("/api/v1/auth/login", json={"email": email, "password": "whatever123"}).status_code == 401

    matches = [e for e in _events(api, admin, action="login_failed") if (e["details"] or {}).get("email") == email]
    assert len(matches) == 1
    entry = matches[0]
    assert entry["user_id"] is None and entry["user_email"] is None
    assert entry["actor_email"] == email
    assert entry["details"]["reason"] == "unknown_user"


def test_failed_login_inactive_account_is_logged(api, admin):
    user = _register(api, "student")
    deactivate = api.patch(f"/api/v1/admin/users/{user['id']}/deactivate", headers=admin["headers"])
    assert deactivate.status_code == 200, deactivate.text

    assert api.post("/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}).status_code == 403
    (entry,) = _events(api, admin, user_id=user["id"], action="login_failed")
    assert entry["details"]["reason"] == "account_inactive"

    # ...and the admin's deactivation is itself audited against the target.
    (deactivated,) = _events(api, admin, action="user_updated", resource_id=user["id"])
    assert deactivated["user_id"] == admin["id"]
    assert deactivated["details"] == {"is_active": False}


def test_logout_is_logged_only_when_an_actor_is_identifiable(api, admin):
    user = _register(api, "student")
    assert api.post("/api/v1/auth/logout", headers=user["headers"]).status_code == 200
    (entry,) = _events(api, admin, user_id=user["id"], action="logout")
    assert entry["actor_email"] == user["email"]

    before = _audit(api, admin, action="logout")["total"]
    assert api.post("/api/v1/auth/logout").status_code == 200
    assert api.post("/api/v1/auth/logout", headers=_auth("garbage")).status_code == 200
    assert _audit(api, admin, action="logout")["total"] == before


def test_profile_update_logs_field_names_not_values(api, admin):
    user = _register(api, "student")
    response = api.put("/api/v1/users/me", headers=user["headers"],
                       json={"full_name": "Secret Name", "camera_consent": True})
    assert response.status_code == 200

    (entry,) = _events(api, admin, user_id=user["id"], action="user_updated")
    assert entry["details"] == {"fields": ["camera_consent", "full_name"]}
    assert "Secret Name" not in str(entry)


def test_device_registration_is_logged_once(api, admin):
    user = _register(api, "student")
    payload = {"device_fingerprint": f"fp-{uuid.uuid4().hex[:16]}", "device_name": "Laptop", "platform": "web"}
    device = api.post("/api/v1/devices/", headers=user["headers"], json=payload)
    assert device.status_code == 201, device.text
    # Re-registering the same device is not a new registration.
    assert api.post("/api/v1/devices/", headers=user["headers"], json=payload).status_code == 201

    (entry,) = _events(api, admin, user_id=user["id"], action="device_registered")
    assert entry["resource_type"] == "device"
    assert entry["resource_id"] == entry["device_id"] == device.json()["id"]
    assert entry["event_type"] == "device"


# --- Course / session / check-in scenario ----------------------------------

@pytest.fixture(scope="module")
def scenario(api, admin):
    instructor = _register(api, "instructor")
    near, far, unenrolled = _register(api, "student"), _register(api, "student"), _register(api, "student")

    course = api.post("/api/v1/courses/", headers=admin["headers"], json={
        "code": f"AU{uuid.uuid4().hex[:8].upper()}", "name": "Audit Course",
        "semester": "AY2024-25 Sem 1", "instructor_id": instructor["id"],
        "venue_latitude": VENUE[0], "venue_longitude": VENUE[1],
        "venue_name": "NTU LT1", "geofence_radius_meters": 100.0, "risk_threshold": 0.5,
    })
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]

    enrollments = {}
    for student in (near, far):
        response = api.post("/api/v1/admin/enrollments/", headers=admin["headers"],
                            json={"student_id": student["id"], "course_id": course_id})
        assert response.status_code == 201, response.text
        enrollments[student["id"]] = response.json()["id"]

    start = _now() + timedelta(minutes=5)
    session = api.post("/api/v1/sessions/", headers=instructor["headers"], json={
        "course_id": course_id, "name": "Audit Session",
        "scheduled_start": _iso(start), "scheduled_end": _iso(start + timedelta(hours=2)),
        "checkin_opens_at": _iso(_now() - timedelta(minutes=10)),
        "checkin_closes_at": _iso(_now() + timedelta(minutes=30)),
        "require_liveness_check": False,
    })
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]

    activated = api.patch(f"/api/v1/admin/sessions/{session_id}/status",
                          headers=admin["headers"], json={"status": "active"})
    assert activated.status_code == 200, activated.text

    approved = _check_in(api, near, session_id, 0)
    rejected = _check_in(api, far, session_id, 500)
    assert approved.status_code == rejected.status_code == 201
    assert approved.json()["status"] == "approved" and rejected.json()["status"] == "rejected"

    return {
        "instructor": instructor, "near": near, "far": far, "unenrolled": unenrolled,
        "course_id": course_id, "session_id": session_id, "enrollments": enrollments,
        "approved": approved.json(), "rejected": rejected.json(),
    }


def _check_in(api, student, session_id, offset_m):
    return api.post("/api/v1/checkins/", headers=student["headers"], json={
        "session_id": session_id,
        "latitude": VENUE[0] + offset_m / METERS_PER_DEGREE_LAT,
        "longitude": VENUE[1],
        "device_fingerprint": f"fp-{uuid.uuid4().hex[:12]}",
    })


def test_enrollment_and_session_creation_are_logged(api, admin, scenario):
    student_id = scenario["near"]["id"]
    enrollment_id = scenario["enrollments"][student_id]

    (enrolled,) = _events(api, admin, action="enrollment_added", resource_id=enrollment_id)
    assert enrolled["user_id"] == admin["id"]
    assert enrolled["details"] == {"student_id": student_id, "course_id": scenario["course_id"]}

    (created,) = _events(api, admin, action="session_created", resource_id=scenario["session_id"])
    assert created["user_id"] == scenario["instructor"]["id"]
    assert created["resource_type"] == "session"
    assert created["details"]["course_id"] == scenario["course_id"]


def test_session_updates_are_logged(api, admin, scenario):
    session_id = scenario["session_id"]
    patch = api.patch(f"/api/v1/sessions/{session_id}", headers=scenario["instructor"]["headers"],
                      json={"description": "changed"})
    assert patch.status_code == 200, patch.text
    updates = _events(api, admin, action="session_updated", resource_id=session_id)
    assert len(updates) == 2
    details = [u["details"] for u in updates]
    assert {"fields": ["description"]} in details
    assert {"status": {"from": "scheduled", "to": "active"}} in details


def test_failed_checkins_write_no_checkin_events(api, admin, scenario):
    before = _audit(api, admin, resource_type="checkin")["total"]
    response = _check_in(api, scenario["unenrolled"], scenario["session_id"], 0)
    assert response.status_code == 400  # not enrolled
    assert _audit(api, admin, resource_type="checkin")["total"] == before


def test_approved_checkin_logs_attempt_then_outcome(api, admin, scenario):
    checkin = scenario["approved"]

    events = _events(api, admin, resource_id=checkin["id"])
    assert [e["action"] for e in events] == ["checkin_approved", "checkin_attempted"]  # newest first
    for entry in events:
        assert entry["user_id"] == scenario["near"]["id"]
        assert entry["resource_type"] == "checkin"
        assert entry["success"] is True and entry["severity"] == "info"
        assert entry["details"]["session_id"] == scenario["session_id"]
        assert entry["details"]["risk_score"] == checkin["risk_score"]
        assert entry["event_type"] == "checkin"


def test_rejected_checkin_is_a_failed_warning_event(api, admin, scenario):
    events = _events(api, admin, resource_id=scenario["rejected"]["id"])
    outcome = next(e for e in events if e["action"] == "checkin_rejected")
    assert outcome["success"] is False and outcome["severity"] == "warning"
    assert any(e["action"] == "checkin_attempted" for e in events)


# --- Filtering --------------------------------------------------------------

def test_filters_narrow_the_result_set(api, admin, scenario):
    data = _audit(api, admin, action="checkin_attempted", limit=1000)
    assert data["total"] >= 2
    assert all(i["action"] == "checkin_attempted" for i in data["items"])

    by_type = _events(api, admin, resource_type="checkin")
    assert by_type and all(i["resource_type"] == "checkin" for i in by_type)

    failures = _events(api, admin, success="false")
    assert failures and all(i["success"] is False for i in failures)
    successes = _events(api, admin, success="true")
    assert successes and all(i["success"] is True for i in successes)
    assert len(failures) + len(successes) == _audit(api, admin, limit=1)["total"]

    mine = _events(api, admin, user_id=scenario["near"]["id"])
    assert mine and all(i["user_id"] == scenario["near"]["id"] for i in mine)
    assert {"login_success", "user_created", "checkin_attempted"} <= {i["action"] for i in mine}


def test_filters_combine_with_and(api, admin, scenario):
    rows = _events(api, admin, user_id=scenario["near"]["id"], action="checkin_approved")
    assert len(rows) == 1
    assert _events(api, admin, user_id=scenario["far"]["id"], action="checkin_approved") == []


def test_date_range_filters(api, admin, scenario):
    now = _now()
    tomorrow, yesterday = _iso(now + timedelta(days=1)), _iso(now - timedelta(days=1))

    assert _audit(api, admin, start_date=tomorrow)["items"] == []
    assert _audit(api, admin, end_date=yesterday)["total"] == 0

    inside = _audit(api, admin, start_date=yesterday, end_date=tomorrow, limit=1)
    assert inside["total"] == _audit(api, admin, limit=1)["total"] > 0

    # An explicit UTC offset is honoured: 09:00+08:00 is 01:00Z, so an end_date
    # of "now, expressed at +08:00" must still include everything up to now.
    plus8 = (datetime.now(timezone(timedelta(hours=8)))).replace(microsecond=0).isoformat()
    assert _audit(api, admin, end_date=plus8, limit=1)["total"] > 0


def test_empty_result_is_a_well_formed_envelope(api, admin):
    data = _audit(api, admin, user_id=str(uuid.uuid4()))
    assert data == {"items": [], "total": 0, "limit": 100, "offset": 0}

    assert _audit(api, admin, resource_id=str(uuid.uuid4()))["items"] == []
    assert _audit(api, admin, resource_type="no_such_type")["items"] == []


# --- Pagination -------------------------------------------------------------

def test_pagination_pages_are_disjoint_and_consistent(api, admin, scenario):
    user_id = scenario["near"]["id"]
    everything = _audit(api, admin, user_id=user_id, limit=1000)
    total = everything["total"]
    assert total >= 4 and total == len(everything["items"])

    page1 = _audit(api, admin, user_id=user_id, limit=2, offset=0)
    page2 = _audit(api, admin, user_id=user_id, limit=2, offset=2)
    assert len(page1["items"]) == 2 and page1["total"] == page2["total"] == total
    assert page2["offset"] == 2
    ids = [i["id"] for i in page1["items"] + page2["items"]]
    assert ids == [i["id"] for i in everything["items"][:4]]

    beyond = _audit(api, admin, user_id=user_id, offset=total + 50)
    assert beyond["items"] == [] and beyond["total"] == total


def test_limit_and_offset_are_clamped(api, admin):
    assert _audit(api, admin, limit=0)["limit"] == 1
    assert _audit(api, admin, limit=-5)["limit"] == 1
    assert _audit(api, admin, limit=99999)["limit"] == 1000
    assert _audit(api, admin, offset=-3)["offset"] == 0


# --- Invalid input ----------------------------------------------------------

@pytest.mark.parametrize("params", [
    {"user_id": "not-a-uuid"},
    {"resource_id": "12345"},
    {"action": "definitely_not_an_action"},
    {"success": "maybe"},
    {"start_date": "yesterday-ish"},
    {"end_date": "2024-13-45"},
    {"limit": "abc"},
    {"offset": "abc"},
])
def test_invalid_filters_are_422(api, admin, params):
    response = api.get("/api/v1/audit/", headers=admin["headers"], params=params)
    assert response.status_code == 422, response.text


def test_inverted_date_range_is_400(api, admin):
    now = _now()
    response = api.get("/api/v1/audit/", headers=admin["headers"], params={
        "start_date": _iso(now), "end_date": _iso(now - timedelta(days=1)),
    })
    assert response.status_code == 400


def test_sql_metacharacters_in_filters_are_inert(api, admin):
    payload = "checkin' OR '1'='1"
    assert api.get("/api/v1/audit/", headers=admin["headers"], params={"action": payload}).status_code == 422
    assert _audit(api, admin, resource_type=payload)["items"] == []


# --- Summary ----------------------------------------------------------------

def test_summary_shape_and_counts(api, admin, scenario):
    response = api.get("/api/v1/audit/summary", headers=admin["headers"], params={"days": 7})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["period_days"] == 7
    assert isinstance(data["by_action"], dict)
    assert data["total_logs"] == sum(data["by_action"].values())
    assert data["by_action"].get("login_success", 0) >= 1
    assert data["by_action"].get("checkin_attempted", 0) >= 2
    assert set(data["by_action"]) <= {
        "login_success", "login_failed", "logout", "user_created", "user_updated",
        "checkin_attempted", "checkin_approved", "checkin_flagged", "checkin_rejected",
        "checkin_appealed", "checkin_reviewed", "session_created", "session_updated",
        "session_deleted", "enrollment_added", "enrollment_removed", "device_registered",
        "face_enrolled", "data_exported", "security_violation",
    }
    assert data["total_logs"] == _audit(api, admin, limit=1)["total"]  # all test data is recent


def test_summary_default_period_is_seven_days(api, admin):
    response = api.get("/api/v1/audit/summary", headers=admin["headers"])
    assert response.status_code == 200
    assert response.json()["period_days"] == 7


@pytest.mark.parametrize("days", ["0", "-1", "abc", "99999"])
def test_summary_rejects_invalid_days(api, admin, days):
    response = api.get("/api/v1/audit/summary", headers=admin["headers"], params={"days": days})
    assert response.status_code == 422
