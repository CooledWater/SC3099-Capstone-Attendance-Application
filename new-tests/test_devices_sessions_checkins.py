"""Devices + sessions/check-ins contract tests (Module 2 <-> Module 4).

Module 4 (src/lib/attendance.ts, SessionsPanel.tsx) calls:
  GET  /sessions/?limit=100            -> {items: [...]}
  POST /sessions/                      (venue_latitude/longitude may be null)
  GET  /checkins/session/{id}          -> array incl. session_id, latitude,
                                          longitude, liveness_score, face_match_score
  GET  /checkins/my-checkins?limit=100 -> array
Module 4 makes no device calls; GET /devices/ (admin) is a public-test/PRD gap.

These tests WRITE data. They never fall back to a default URL: with
TEST_BACKEND_URL unset they skip. Point them only at a scratch backend, e.g.

    DATABASE_URL=sqlite:///scratch.db JWT_SECRET=x \
        python -m uvicorn app.main:app --port 8765     (from module2-backend)
    TEST_BACKEND_URL=http://127.0.0.1:8765 pytest new-tests/test_devices_sessions_checkins.py -v
"""
import csv
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

BACKEND_URL = os.getenv("TEST_BACKEND_URL")  # deliberately no default
PASSWORD = "testpassword123"

VENUE = (1.3483, 103.6831)
METERS_PER_DEGREE_LAT = 111_195.0
# radius 100 m, threshold 0.5 -> risk = distance / 200: approved < 100 m <= flagged, rejected > 200 m
OFFSETS_M = {"approved": 0, "flagged": 120, "rejected": 500}
FORMULA_NAME = "=HYPERLINK(\"http://evil.example\",\"x\")"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime) -> str:
    return value.isoformat() + "Z"


@pytest.fixture(scope="module")
def api():
    if not BACKEND_URL:
        pytest.skip("Set TEST_BACKEND_URL to a scratch backend (these tests write data)")
    with httpx.Client(base_url=BACKEND_URL, timeout=30.0) as client:
        try:
            client.get("/health")
        except httpx.ConnectError:
            pytest.skip(f"Backend not running at {BACKEND_URL}")
        yield client


def _register(api, role, full_name=None):
    email = f"{role}_{uuid.uuid4().hex[:10]}@dsc-test.com"
    response = api.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name or f"DSC {role}", "role": role,
    })
    assert response.status_code == 201, response.text
    login = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {
        "id": response.json()["id"], "email": email,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def _check_in(api, student, session_id, offset_m):
    return api.post("/api/v1/checkins/", headers=student["headers"], json={
        "session_id": session_id,
        "latitude": VENUE[0] + offset_m / METERS_PER_DEGREE_LAT,
        "longitude": VENUE[1],
        "device_fingerprint": f"fp-{uuid.uuid4().hex[:12]}",
    })


def _new_session(api, owner, course_id, activate_with=None, **overrides):
    start = _now() + timedelta(minutes=5)
    body = {
        "course_id": course_id, "name": f"DSC Session {uuid.uuid4().hex[:6]}",
        "scheduled_start": _iso(start), "scheduled_end": _iso(start + timedelta(hours=2)),
        "checkin_opens_at": _iso(_now() - timedelta(minutes=10)),
        "checkin_closes_at": _iso(_now() + timedelta(minutes=30)),
        "require_liveness_check": False, **overrides,
    }
    response = api.post("/api/v1/sessions/", headers=owner["headers"], json=body)
    assert response.status_code == 201, response.text
    session = response.json()
    if activate_with:
        active = api.patch(f"/api/v1/admin/sessions/{session['id']}/status",
                           headers=activate_with["headers"], json={"status": "active"})
        assert active.status_code == 200, active.text
    return session


@pytest.fixture(scope="module")
def world(api):
    admin, instructor, other = _register(api, "admin"), _register(api, "instructor"), _register(api, "instructor")
    ta = _register(api, "ta")
    students = {
        "approved": _register(api, "student"),
        "flagged": _register(api, "student", full_name=FORMULA_NAME),
        "rejected": _register(api, "student"),
    }

    def make_course(teacher):
        response = api.post("/api/v1/courses/", headers=admin["headers"], json={
            "code": f"DS{uuid.uuid4().hex[:8].upper()}", "name": "DSC Course",
            "semester": "AY2024-25 Sem 1", "instructor_id": teacher["id"],
            "venue_latitude": VENUE[0], "venue_longitude": VENUE[1],
            "geofence_radius_meters": 100.0, "risk_threshold": 0.5,
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    course_id, other_course_id = make_course(instructor), make_course(other)
    for student in students.values():
        enrolled = api.post("/api/v1/admin/enrollments/", headers=admin["headers"],
                            json={"student_id": student["id"], "course_id": course_id})
        assert enrolled.status_code == 201, enrolled.text

    session = _new_session(api, instructor, course_id, activate_with=admin)
    checkins = {}
    for name, student in students.items():
        response = _check_in(api, student, session["id"], OFFSETS_M[name])
        assert response.status_code == 201, response.text
        assert response.json()["status"] == name
        checkins[name] = response.json()

    return {
        "admin": admin, "instructor": instructor, "other": other, "ta": ta,
        "students": students, "course_id": course_id, "other_course_id": other_course_id,
        "session": session, "checkins": checkins,
    }


# --- Sessions: what Module 4 calls -------------------------------------------

def test_sessions_list_has_the_fields_module4_reads(api, world):
    # Module 4 sends only limit=100; course_id just keeps this lookup on a busy DB deterministic.
    response = api.get("/api/v1/sessions/", params={"limit": 100, "course_id": world["course_id"]},
                       headers=world["instructor"]["headers"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert {"items", "total", "limit", "offset"} <= set(data) and data["limit"] == 100

    mine = next(i for i in data["items"] if i["id"] == world["session"]["id"])
    for field in ("course_id", "course_code", "course_name", "scheduled_start", "venue_name",
                  "total_enrolled", "status", "venue_latitude", "venue_longitude",
                  "geofence_radius_meters"):
        assert field in mine, field
    assert mine["total_enrolled"] == 3 and mine["status"] == "active"
    assert mine["checked_in_count"] == 3


def test_sessions_list_filters(api, world):
    headers = world["admin"]["headers"]

    def ids(**params):
        response = api.get("/api/v1/sessions/", params={"limit": 100, **params}, headers=headers)
        assert response.status_code == 200, response.text
        return {i["id"] for i in response.json()["items"]}

    sid = world["session"]["id"]
    assert sid in ids(course_id=world["course_id"], instructor_id=world["instructor"]["id"], status="active")
    assert sid not in ids(instructor_id=world["other"]["id"])
    assert sid not in ids(course_id=world["other_course_id"])
    assert sid not in ids(start_date=_iso(_now() + timedelta(days=30)))
    assert sid not in ids(end_date=_iso(_now() - timedelta(days=30)))
    assert sid in ids(course_id=world["course_id"], start_date=_iso(_now() - timedelta(days=1)),
                      end_date=_iso(_now() + timedelta(days=1)))
    assert api.get("/api/v1/sessions/", params={"start_date": "soon"}, headers=headers).status_code == 422


def test_module4_create_session_payload_with_null_venue_is_accepted(api, world):
    start = _now() + timedelta(hours=1)
    response = api.post("/api/v1/sessions/", headers=world["instructor"]["headers"], json={
        "course_id": world["course_id"], "name": "Hall B session", "session_type": "lecture",
        "scheduled_start": _iso(start), "scheduled_end": _iso(start + timedelta(hours=1)),
        "venue_name": "Hall B", "venue_latitude": None, "venue_longitude": None,
        "geofence_radius_meters": 100,
    })
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "scheduled"


def test_students_and_tas_cannot_list_or_create_sessions(api, world):
    for who in (world["students"]["approved"], world["ta"]):
        assert api.get("/api/v1/sessions/", headers=who["headers"]).status_code == 403
        assert api.post("/api/v1/sessions/", headers=who["headers"], json={}).status_code in (403, 422)


# --- Check-ins: per-session list (Module 4 fields) ---------------------------

def test_session_checkins_carry_the_fields_module4_reads(api, world):
    response = api.get(f"/api/v1/checkins/session/{world['session']['id']}", headers=world["ta"]["headers"])
    assert response.status_code == 200, response.text
    rows = {r["student_id"]: r for r in response.json()}
    assert len(rows) == 3

    row = rows[world["students"]["approved"]["id"]]
    for field in ("id", "session_id", "student_name", "student_email", "checked_in_at", "status",
                  "risk_score", "liveness_score", "face_match_score", "latitude", "longitude"):
        assert field in row, field
    assert row["session_id"] == world["session"]["id"]
    assert row["latitude"] == pytest.approx(VENUE[0], abs=1e-6)
    assert row["liveness_score"] is None and row["face_match_score"] is None  # not performed


def test_my_checkins_shape_still_works_for_module4(api, world):
    response = api.get("/api/v1/checkins/my-checkins", params={"limit": 100},
                       headers=world["students"]["approved"]["headers"])
    assert response.status_code == 200 and isinstance(response.json(), list)
    assert {"id", "session_id", "status", "checked_in_at", "risk_score"} <= set(response.json()[0])


# --- GET /checkins/ ------------------------------------------------------------

def _list(api, who, path="/api/v1/checkins/", **params):
    return api.get(path, params=params, headers=who["headers"])


def test_checkins_list_envelope_and_filters(api, world):
    data = _list(api, world["instructor"], session_id=world["session"]["id"]).json()
    assert {"items", "total", "limit", "offset"} <= set(data)
    assert data["total"] == 3 and data["limit"] == 50 and data["offset"] == 0
    item = data["items"][0]
    for field in ("id", "session_id", "session_name", "student_id", "student_name", "student_email",
                  "status", "checked_in_at", "distance_from_venue_meters", "risk_score", "liveness_passed"):
        assert field in item, field

    flagged = _list(api, world["instructor"], session_id=world["session"]["id"], status="flagged").json()
    assert [i["status"] for i in flagged["items"]] == ["flagged"]

    student_id = world["students"]["rejected"]["id"]
    assert _list(api, world["instructor"], student_id=student_id).json()["total"] == 1
    assert _list(api, world["instructor"], course_id=world["course_id"], min_risk_score=0.55,
                 max_risk_score=0.65).json()["total"] == 1  # only the flagged one (risk 0.6)
    assert _list(api, world["instructor"], session_id=world["session"]["id"],
                 start_date=_iso(_now() + timedelta(days=1))).json()["items"] == []


def test_checkins_list_pagination_and_clamping(api, world):
    sid = world["session"]["id"]
    first = _list(api, world["admin"], session_id=sid, limit=2, offset=0).json()
    second = _list(api, world["admin"], session_id=sid, limit=2, offset=2).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1 and first["total"] == second["total"] == 3
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}
    assert _list(api, world["admin"], session_id=sid, limit=0).json()["limit"] == 1
    assert _list(api, world["admin"], session_id=sid, limit=9999).json()["limit"] == 100
    assert _list(api, world["admin"], session_id=sid, offset=-4).json()["offset"] == 0


def test_checkins_list_invalid_input(api, world):
    assert _list(api, world["admin"], status="bogus").status_code == 422
    assert _list(api, world["admin"], min_risk_score="high").status_code == 422
    assert _list(api, world["admin"], start_date="not-a-date").status_code == 422
    now = _now()
    assert _list(api, world["admin"], start_date=_iso(now), end_date=_iso(now - timedelta(days=1))).status_code == 400
    assert _list(api, world["admin"], session_id=str(uuid.uuid4())).json()["items"] == []


@pytest.mark.parametrize("path", ["/api/v1/checkins/", "/api/v1/checkins/flagged"])
def test_checkin_queues_reject_students_and_anonymous(api, world, path):
    assert _list(api, world["students"]["approved"], path).status_code == 403
    assert api.get(path).status_code in (401, 403)


def test_checkins_list_excludes_ta_and_scopes_instructors(api, world):
    assert _list(api, world["ta"]).status_code == 403  # API-SPECIFICATION: instructor/admin
    sid = world["session"]["id"]
    assert _list(api, world["other"], session_id=sid).json()["total"] == 0  # someone else's course
    assert _list(api, world["instructor"], session_id=sid).json()["total"] == 3
    assert _list(api, world["admin"], session_id=sid).json()["total"] == 3


# --- GET /checkins/flagged -------------------------------------------------------

def test_flagged_queue_contains_only_flagged_or_appealed(api, world):
    response = _list(api, world["instructor"], "/api/v1/checkins/flagged", session_id=world["session"]["id"])
    assert response.status_code == 200
    data = response.json()
    assert {"items", "total", "limit", "offset"} <= set(data)
    assert [i["id"] for i in data["items"]] == [world["checkins"]["flagged"]["id"]]
    item = data["items"][0]
    assert item["status"] == "flagged" and "appeal_reason" in item and "appealed_at" in item
    assert isinstance(item["risk_factors"], list)

    everything = _list(api, world["admin"], "/api/v1/checkins/flagged", limit=100).json()
    assert all(i["status"] in ("flagged", "appealed") for i in everything["items"])


def test_flagged_queue_allows_ta_and_scopes_instructors(api, world):
    sid = world["session"]["id"]
    assert _list(api, world["ta"], "/api/v1/checkins/flagged", session_id=sid).json()["total"] == 1
    assert _list(api, world["other"], "/api/v1/checkins/flagged", session_id=sid).json()["total"] == 0


# --- GET /export/session/{id} ------------------------------------------------------

def _export(api, who, session_id, **params):
    return api.get(f"/api/v1/export/session/{session_id}", params=params, headers=who["headers"])


def test_export_json_summary_and_records(api, world):
    response = _export(api, world["instructor"], world["session"]["id"], format="json")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["session_id"] == world["session"]["id"]
    assert data["summary"]["total_enrolled"] == 3 and data["summary"]["checked_in_count"] == 3
    assert data["summary"]["approved_count"] == data["summary"]["flagged_count"] == 1
    assert data["summary"]["rejected_count"] == 1 and data["summary"]["attendance_rate"] == 1.0
    assert len(data["records"]) == 3
    assert set(data["records"][0]) == {
        "student_id", "student_name", "student_email", "session_date", "session_name",
        "status", "checked_in_at", "risk_score",
    }


def test_export_csv_is_default_quoted_and_formula_safe(api, world):
    response = _export(api, world["admin"], world["session"]["id"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["student_id", "student_name", "student_email", "session_date",
                       "session_name", "status", "checked_in_at", "risk_score"]
    assert len(rows) == 4
    names = {r[1] for r in rows[1:]}
    assert "'" + FORMULA_NAME in names and FORMULA_NAME not in names


def test_export_permissions_and_errors(api, world):
    sid = world["session"]["id"]
    assert _export(api, world["other"], sid).status_code == 403          # not their session/course
    assert _export(api, world["ta"], sid).status_code == 403             # spec: instructor for session
    assert _export(api, world["students"]["approved"], sid).status_code == 403
    assert api.get(f"/api/v1/export/session/{sid}").status_code in (401, 403)
    assert _export(api, world["admin"], str(uuid.uuid4())).status_code == 404
    assert _export(api, world["admin"], sid, format="xml").status_code == 422


def test_export_of_an_empty_session_is_well_formed(api, world):
    empty = _new_session(api, world["instructor"], world["course_id"])
    data = _export(api, world["instructor"], empty["id"], format="json").json()
    assert data["records"] == [] and data["summary"]["checked_in_count"] == 0
    assert data["summary"]["attendance_rate"] == 0.0
    rows = list(csv.reader(io.StringIO(_export(api, world["instructor"], empty["id"]).text)))
    assert len(rows) == 1  # header only


def test_export_writes_a_data_exported_audit_entry(api, world):
    sid = world["session"]["id"]
    assert _export(api, world["instructor"], sid, format="json").status_code == 200
    audit = api.get("/api/v1/audit/", headers=world["admin"]["headers"],
                    params={"action": "data_exported", "resource_id": sid,
                            "user_id": world["instructor"]["id"], "limit": 100})
    assert audit.status_code == 200, audit.text
    entries = audit.json()["items"]
    assert entries and all(e["user_id"] == world["instructor"]["id"] for e in entries)
    assert all(e["severity"] == "info" and e["event_type"] == "export" for e in entries)
    assert entries[0]["details"]["export_type"] == "session_attendance"


# --- Devices --------------------------------------------------------------------

@pytest.fixture(scope="module")
def device(api, world):
    student = world["students"]["approved"]
    response = api.post("/api/v1/devices/", headers=student["headers"], json={
        "device_fingerprint": f"dsc-{uuid.uuid4().hex[:16]}", "device_name": "DSC Laptop", "platform": "web",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_device_list_envelope_and_filters(api, world, device):
    admin = world["admin"]
    data = api.get("/api/v1/devices/", params={"limit": 100}, headers=admin["headers"])
    assert data.status_code == 200, data.text
    body = data.json()
    assert {"items", "total", "limit", "offset"} <= set(body) and body["total"] >= 1

    mine = api.get("/api/v1/devices/", params={"user_id": world["students"]["approved"]["id"]},
                   headers=admin["headers"]).json()
    assert [d["id"] for d in mine["items"]] == [device["id"]]
    item = mine["items"][0]
    assert item["user_email"] == world["students"]["approved"]["email"]
    assert {"id", "user_id", "device_fingerprint", "device_name", "platform", "is_trusted",
            "trust_score", "is_active", "first_seen_at", "last_seen_at", "total_checkins"} <= set(item)

    assert api.get("/api/v1/devices/", params={"user_id": world["students"]["approved"]["id"],
                                               "is_trusted": "true"}, headers=admin["headers"]).json()["items"] == []
    assert api.get("/api/v1/devices/", params={"is_active": "maybe"}, headers=admin["headers"]).status_code == 422
    assert api.get("/api/v1/devices/", params={"limit": 0}, headers=admin["headers"]).json()["limit"] == 1


def test_device_list_is_admin_only(api, world, device):
    for who in (world["students"]["approved"], world["ta"], world["instructor"]):
        assert api.get("/api/v1/devices/", headers=who["headers"]).status_code == 403
    assert api.get("/api/v1/devices/").status_code in (401, 403)


def test_my_devices_is_unchanged(api, world, device):
    mine = api.get("/api/v1/devices/my-devices", headers=world["students"]["approved"]["headers"])
    assert mine.status_code == 200 and [d["id"] for d in mine.json()] == [device["id"]]
    assert api.get("/api/v1/devices/my-devices", headers=world["students"]["rejected"]["headers"]).json() == []
