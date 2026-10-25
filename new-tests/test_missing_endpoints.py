"""Edge cases for the Module 2 endpoints added from docs/API-SPECIFICATION.md.

Covers: GET/PATCH /users/, GET /users/{id}, PATCH /admin/users/{id}/activate,
POST /admin/users/bulk, DELETE /courses/{id}, GET /sessions/my-sessions,
GET /checkins/{id}, POST /checkins/{id}/appeal (called by Module 4
CourseHistory.tsx), POST /checkins/{id}/review, POST /enrollments/bulk,
DELETE /enrollments/{id} and GET /export/attendance/{course_id}.

These tests WRITE data. They never fall back to a default URL: with
TEST_BACKEND_URL unset they skip. Point them only at a scratch backend, e.g.

    DATABASE_URL=sqlite:///scratch.db JWT_SECRET=x \
        python -m uvicorn app.main:app --port 8765     (from module2-backend)
    TEST_BACKEND_URL=http://127.0.0.1:8765 pytest new-tests/test_missing_endpoints.py -v
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
# radius 100 m, threshold 0.5 -> approved < 100 m <= flagged, rejected > 200 m
OFFSETS_M = {"approved": 0, "flagged": 120, "rejected": 500}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime) -> str:
    return value.isoformat() + "Z"


@pytest.fixture(scope="module")
def api():
    if not BACKEND_URL:
        pytest.skip("Set TEST_BACKEND_URL to a scratch backend (these tests write data)")
    with httpx.Client(base_url=BACKEND_URL, timeout=60.0) as client:
        try:
            client.get("/health")
        except httpx.ConnectError:
            pytest.skip(f"Backend not running at {BACKEND_URL}")
        yield client


def _email(role):
    return f"{role}_{uuid.uuid4().hex[:10]}@mep-test.com"


def _login(api, email):
    login = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _register(api, role, full_name=None):
    email = _email(role)
    response = api.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name or f"MEP {role}", "role": role,
    })
    assert response.status_code == 201, response.text
    return {"id": response.json()["id"], "email": email, "headers": _login(api, email)}


def _make_course(api, admin, teacher):
    response = api.post("/api/v1/courses/", headers=admin["headers"], json={
        "code": f"MP{uuid.uuid4().hex[:8].upper()}", "name": "MEP Course",
        "semester": "AY2024-25 Sem 1", "instructor_id": teacher["id"],
        "venue_latitude": VENUE[0], "venue_longitude": VENUE[1],
        "geofence_radius_meters": 100.0, "risk_threshold": 0.5,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _new_session(api, owner, course_id, admin):
    start = _now() + timedelta(minutes=5)
    response = api.post("/api/v1/sessions/", headers=owner["headers"], json={
        "course_id": course_id, "name": f"MEP Session {uuid.uuid4().hex[:6]}",
        "scheduled_start": _iso(start), "scheduled_end": _iso(start + timedelta(hours=2)),
        "checkin_opens_at": _iso(_now() - timedelta(minutes=10)),
        "checkin_closes_at": _iso(_now() + timedelta(minutes=30)),
        "require_liveness_check": False,
    })
    assert response.status_code == 201, response.text
    session = response.json()
    active = api.patch(f"/api/v1/admin/sessions/{session['id']}/status",
                       headers=admin["headers"], json={"status": "active"})
    assert active.status_code == 200, active.text
    return session


def _check_in(api, student, session_id, offset_m):
    response = api.post("/api/v1/checkins/", headers=student["headers"], json={
        "session_id": session_id,
        "latitude": VENUE[0] + offset_m / METERS_PER_DEGREE_LAT,
        "longitude": VENUE[1],
        "device_fingerprint": f"fp-{uuid.uuid4().hex[:12]}",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def world(api):
    admin = _register(api, "admin")
    instructor, other = _register(api, "instructor"), _register(api, "instructor")
    ta = _register(api, "ta")
    students = {name: _register(api, "student") for name in OFFSETS_M}
    outsider = _register(api, "student")

    course_id = _make_course(api, admin, instructor)
    other_course_id = _make_course(api, admin, other)
    enrollment_ids = {}
    for name, student in students.items():
        enrolled = api.post("/api/v1/admin/enrollments/", headers=admin["headers"],
                            json={"student_id": student["id"], "course_id": course_id})
        assert enrolled.status_code == 201, enrolled.text
        enrollment_ids[name] = enrolled.json()["id"]

    session = _new_session(api, instructor, course_id, admin)
    checkins = {name: _check_in(api, students[name], session["id"], OFFSETS_M[name])
                for name in OFFSETS_M}
    for name, checkin in checkins.items():
        assert checkin["status"] == name

    return {
        "admin": admin, "instructor": instructor, "other": other, "ta": ta,
        "students": students, "outsider": outsider, "course_id": course_id,
        "other_course_id": other_course_id, "session": session, "checkins": checkins,
        "enrollment_ids": enrollment_ids,
    }


# --- Users -------------------------------------------------------------------

def test_list_users_filters_and_never_leaks_secrets(api, world):
    admin = world["admin"]
    target = world["students"]["approved"]
    response = api.get("/api/v1/users/", headers=admin["headers"],
                       params={"search": target["email"].upper(), "role": "student"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert {"items", "total", "limit", "offset"} <= data.keys()
    assert [u["id"] for u in data["items"]] == [target["id"]]
    assert data["total"] == 1
    item = data["items"][0]
    assert "hashed_password" not in item and "password" not in item
    assert "face_embedding_hash" not in item


def test_list_users_search_treats_wildcards_literally(api, world):
    response = api.get("/api/v1/users/", headers=world["admin"]["headers"], params={"search": "%"})
    assert response.status_code == 200
    assert all("%" in (u["email"] + u["full_name"]) for u in response.json()["items"])


def test_list_users_pagination_is_capped(api, world):
    response = api.get("/api/v1/users/", headers=world["admin"]["headers"], params={"limit": 1000})
    assert response.status_code == 200
    assert response.json()["limit"] == 100


@pytest.mark.parametrize("role", ["instructor", "ta", "student"])
def test_list_users_is_admin_only(api, world, role):
    headers = {"instructor": world["instructor"], "ta": world["ta"],
               "student": world["students"]["approved"]}[role]["headers"]
    assert api.get("/api/v1/users/", headers=headers).status_code == 403


def test_list_users_rejects_unknown_role_filter(api, world):
    response = api.get("/api/v1/users/", headers=world["admin"]["headers"], params={"role": "root"})
    assert response.status_code == 422


def test_get_user_admin_and_teaching_instructor(api, world):
    student = world["students"]["approved"]
    for viewer in (world["admin"], world["instructor"]):
        response = api.get(f"/api/v1/users/{student['id']}", headers=viewer["headers"])
        assert response.status_code == 200, response.text
        assert response.json()["email"] == student["email"]


def test_get_user_forbidden_for_unrelated_instructor_and_students(api, world):
    student = world["students"]["approved"]
    assert api.get(f"/api/v1/users/{student['id']}", headers=world["other"]["headers"]).status_code == 403
    assert api.get(f"/api/v1/users/{student['id']}",
                   headers=world["outsider"]["headers"]).status_code == 403


def test_get_unknown_user_404(api, world):
    assert api.get(f"/api/v1/users/{uuid.uuid4()}", headers=world["admin"]["headers"]).status_code == 404


def test_users_me_still_resolves_to_current_user(api, world):
    student = world["students"]["approved"]
    response = api.get("/api/v1/users/me", headers=student["headers"])
    assert response.status_code == 200
    assert response.json()["id"] == student["id"]


def test_patch_user_role_and_activation(api, world):
    user = _register(api, "student")
    admin = world["admin"]
    response = api.patch(f"/api/v1/users/{user['id']}", headers=admin["headers"],
                         json={"role": "ta", "is_active": False})
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "ta" and response.json()["is_active"] is False
    login = api.post("/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD})
    assert login.status_code == 403


def test_patch_user_admin_only_and_validated(api, world):
    user = world["students"]["approved"]
    assert api.patch(f"/api/v1/users/{user['id']}", headers=world["instructor"]["headers"],
                     json={"role": "admin"}).status_code == 403
    assert api.patch(f"/api/v1/users/{user['id']}", headers=world["admin"]["headers"],
                     json={"role": "superuser"}).status_code == 422


def test_deactivate_then_activate_restores_login(api, world):
    user = _register(api, "student")
    admin = world["admin"]
    assert api.patch(f"/api/v1/admin/users/{user['id']}/deactivate",
                     headers=admin["headers"]).status_code == 200
    assert api.post("/api/v1/auth/login",
                    json={"email": user["email"], "password": PASSWORD}).status_code == 403
    response = api.patch(f"/api/v1/admin/users/{user['id']}/activate", headers=admin["headers"])
    assert response.status_code == 200, response.text
    assert response.json() == {"id": user["id"], "email": user["email"], "is_active": True,
                               "message": "User activated successfully"}
    assert api.post("/api/v1/auth/login",
                    json={"email": user["email"], "password": PASSWORD}).status_code == 200


def test_activate_admin_only_and_404(api, world):
    user = world["students"]["approved"]
    assert api.patch(f"/api/v1/admin/users/{user['id']}/activate",
                     headers=world["instructor"]["headers"]).status_code == 403
    assert api.patch(f"/api/v1/admin/users/{uuid.uuid4()}/activate",
                     headers=world["admin"]["headers"]).status_code == 404


# --- Bulk user creation ------------------------------------------------------

def test_bulk_create_users_matches_spec_and_users_can_log_in(api, world):
    emails = [_email("bulk") for _ in range(3)]
    response = api.post("/api/v1/admin/users/bulk", headers=world["admin"]["headers"], json={
        "users": [{"email": e, "password": PASSWORD, "full_name": f"Bulk {i}", "role": "student"}
                  for i, e in enumerate(emails)],
    })
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["created"] == 3 and data["failed"] == 0 and data["errors"] == []
    assert [u["email"] for u in data["users"]] == emails
    for user in data["users"]:
        assert set(user) == {"id", "email", "full_name", "role"}
    _login(api, emails[0])


def test_bulk_create_reports_bad_and_duplicate_entries(api, world):
    fresh = _email("bulk")
    existing = world["students"]["approved"]["email"]
    response = api.post("/api/v1/admin/users/bulk", headers=world["admin"]["headers"], json={
        "users": [
            {"email": fresh, "password": PASSWORD, "full_name": "Ok"},
            {"email": fresh, "password": PASSWORD, "full_name": "Repeat"},
            {"email": existing, "password": PASSWORD, "full_name": "Taken"},
            {"email": "not-an-email", "password": PASSWORD, "full_name": "Bad"},
            {"email": _email("bulk"), "password": "short", "full_name": "Weak"},
        ],
    })
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["created"] == 1 and data["failed"] == 4
    assert [e["index"] for e in data["errors"]] == [1, 2, 3, 4]
    assert "short" not in str(data["errors"])  # passwords are never echoed


@pytest.mark.parametrize("body", [{}, {"users": []}])
def test_bulk_create_rejects_empty_payload(api, world, body):
    response = api.post("/api/v1/admin/users/bulk", headers=world["admin"]["headers"], json=body)
    assert response.status_code == 422


def test_bulk_create_admin_only(api, world):
    response = api.post("/api/v1/admin/users/bulk", headers=world["instructor"]["headers"], json={
        "users": [{"email": _email("bulk"), "password": PASSWORD, "full_name": "X"}],
    })
    assert response.status_code == 403


# --- Courses -----------------------------------------------------------------

def test_delete_course_soft_deletes(api, world):
    admin = world["admin"]
    course_id = _make_course(api, admin, world["other"])
    assert api.delete(f"/api/v1/courses/{course_id}", headers=world["instructor"]["headers"]).status_code == 403
    assert api.delete(f"/api/v1/courses/{course_id}", headers=admin["headers"]).status_code == 204
    detail = api.get(f"/api/v1/courses/{course_id}", headers=admin["headers"])
    assert detail.status_code == 200 and detail.json()["is_active"] is False
    active_ids = [c["id"] for c in api.get("/api/v1/courses/", params={"limit": 100}, headers=admin["headers"]).json()["items"]]
    assert course_id not in active_ids
    assert api.delete(f"/api/v1/courses/{uuid.uuid4()}", headers=admin["headers"]).status_code == 404


# --- Sessions ----------------------------------------------------------------

def test_my_sessions_for_enrolled_student_and_teaching_instructor(api, world):
    session_id = world["session"]["id"]
    student_view = api.get("/api/v1/sessions/my-sessions", headers=world["students"]["approved"]["headers"])
    assert student_view.status_code == 200, student_view.text
    assert session_id in [s["id"] for s in student_view.json()]
    teacher_view = api.get("/api/v1/sessions/my-sessions", headers=world["instructor"]["headers"],
                           params={"status": "active"})
    assert session_id in [s["id"] for s in teacher_view.json()]


def test_student_my_sessions_supports_overlap_range_pagination_and_course_scope(api, world):
    session = world["session"]
    start = _start_of(session) - timedelta(minutes=1)
    end = _start_of(session) + timedelta(hours=2, minutes=1)
    response = api.get("/api/v1/sessions/my-sessions", headers=world["students"]["approved"]["headers"], params={
        "start_date": _iso(start), "end_date": _iso(end), "limit": 1, "offset": 0,
    })
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [session["id"]]

    forbidden = api.get("/api/v1/sessions/my-sessions", headers=world["students"]["approved"]["headers"], params={
        "course_id": world["other_course_id"],
    })
    assert forbidden.status_code == 403


def test_my_sessions_excludes_unrelated_users_and_filters(api, world):
    session_id = world["session"]["id"]
    for viewer in (world["outsider"], world["other"]):
        response = api.get("/api/v1/sessions/my-sessions", headers=viewer["headers"])
        assert response.status_code == 200
        assert session_id not in [s["id"] for s in response.json()]
    closed = api.get("/api/v1/sessions/my-sessions", headers=world["instructor"]["headers"],
                     params={"status": "closed"})
    assert session_id not in [s["id"] for s in closed.json()]


def _start_of(session):
    return datetime.fromisoformat(session["scheduled_start"].removesuffix("Z"))


def test_my_sessions_upcoming_excludes_past_and_sorts_chronologically(api, world):
    # A dedicated instructor and course, so the result set is exactly these sessions.
    teacher = _register(api, "instructor")
    course_id = _make_course(api, world["admin"], teacher)
    now = _now()
    session_ids = {}
    # Created out of chronological order so the sort is actually exercised.
    for label, hours in (("late", 3), ("early", 1), ("middle", 2), ("past", 4)):
        start = now + timedelta(hours=hours)
        response = api.post("/api/v1/sessions/", headers=teacher["headers"], json={
            "course_id": course_id, "name": f"MEP Upcoming {label}",
            "scheduled_start": _iso(start), "scheduled_end": _iso(start + timedelta(hours=1)),
            "require_liveness_check": False,
        })
        assert response.status_code == 201, response.text
        session_ids[label] = response.json()["id"]

    # POST /sessions/ only accepts future starts, so move one into the past.
    past_start = now - timedelta(days=2)
    moved = api.patch(f"/api/v1/sessions/{session_ids['past']}", headers=teacher["headers"], json={
        "scheduled_start": _iso(past_start), "scheduled_end": _iso(past_start + timedelta(hours=1)),
        "checkin_opens_at": _iso(past_start - timedelta(minutes=15)),
        "checkin_closes_at": _iso(past_start + timedelta(minutes=30)),
    })
    assert moved.status_code == 200, moved.text

    # Without the filter the past session is listed (newest first).
    everything = api.get("/api/v1/sessions/my-sessions", headers=teacher["headers"])
    assert everything.status_code == 200, everything.text
    assert [s["id"] for s in everything.json()] == [
        session_ids[label] for label in ("late", "middle", "early", "past")
    ]

    upcoming = api.get("/api/v1/sessions/my-sessions", headers=teacher["headers"],
                       params={"upcoming": True})
    assert upcoming.status_code == 200, upcoming.text
    items = upcoming.json()
    # Past session excluded, every future session included, earliest first.
    assert [s["id"] for s in items] == [session_ids[label] for label in ("early", "middle", "late")]
    starts = [_start_of(s) for s in items]
    assert starts == sorted(starts)
    assert all(start > now for start in starts)


def test_my_sessions_requires_auth_and_valid_status(api, world):
    assert api.get("/api/v1/sessions/my-sessions").status_code in (401, 403)
    assert api.get("/api/v1/sessions/my-sessions", headers=world["instructor"]["headers"],
                   params={"status": "bogus"}).status_code == 422


# --- Check-in detail, appeal, review ----------------------------------------

def test_checkin_detail_access(api, world):
    checkin_id = world["checkins"]["flagged"]["id"]
    owner = world["students"]["flagged"]
    for viewer in (owner, world["instructor"], world["admin"]):
        response = api.get(f"/api/v1/checkins/{checkin_id}", headers=viewer["headers"])
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["id"] == checkin_id and "risk_factors" not in data
        assert "face_embedding_hash" not in data
    # world["ta"] has no course_assistants row (assigned TAs: test_ta_scope.py).
    for viewer in (world["students"]["approved"], world["other"], world["ta"]):
        assert api.get(f"/api/v1/checkins/{checkin_id}", headers=viewer["headers"]).status_code == 403
    assert api.get(f"/api/v1/checkins/{uuid.uuid4()}", headers=world["admin"]["headers"]).status_code == 404


def test_checkin_static_routes_not_shadowed(api, world):
    assert api.get("/api/v1/checkins/flagged", headers=world["instructor"]["headers"]).status_code == 200
    assert api.get("/api/v1/checkins/my-checkins",
                   headers=world["students"]["approved"]["headers"]).status_code == 200


def test_appeal_rules(api, world):
    approved = world["checkins"]["approved"]["id"]
    rejected = world["checkins"]["rejected"]["id"]
    owner = world["students"]["rejected"]
    reason = "<b>I'm</b> sure I was in class"

    # Approved check-ins cannot be appealed; only the owner may appeal.
    assert api.post(f"/api/v1/checkins/{approved}/appeal", headers=world["students"]["approved"]["headers"],
                    json={"appeal_reason": "x"}).status_code == 400
    assert api.post(f"/api/v1/checkins/{rejected}/appeal", headers=world["students"]["approved"]["headers"],
                    json={"appeal_reason": "x"}).status_code == 403
    assert api.post(f"/api/v1/checkins/{rejected}/appeal", headers=world["instructor"]["headers"],
                    json={"appeal_reason": "x"}).status_code == 403
    assert api.post(f"/api/v1/checkins/{rejected}/appeal", headers=owner["headers"],
                    json={"appeal_reason": "   "}).status_code == 400

    response = api.post(f"/api/v1/checkins/{rejected}/appeal", headers=owner["headers"],
                        json={"appeal_reason": reason})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == rejected and data["status"] == "appealed" and data["appealed_at"]
    assert "<b>" not in data["appeal_reason"] and "I'm" in data["appeal_reason"]

    # Cannot appeal more than once.
    assert api.post(f"/api/v1/checkins/{rejected}/appeal", headers=owner["headers"],
                    json={"appeal_reason": "again"}).status_code == 400

    queue = api.get("/api/v1/checkins/flagged", headers=world["instructor"]["headers"],
                    params={"session_id": world["session"]["id"]}).json()["items"]
    assert any(i["id"] == rejected and i["status"] == "appealed" for i in queue)


def test_review_rules(api, world):
    flagged = world["checkins"]["flagged"]["id"]
    approved = world["checkins"]["approved"]["id"]

    assert api.post(f"/api/v1/checkins/{flagged}/review", headers=world["students"]["flagged"]["headers"],
                    json={"status": "approved"}).status_code == 403
    assert api.post(f"/api/v1/checkins/{flagged}/review", headers=world["other"]["headers"],
                    json={"status": "approved"}).status_code == 403
    assert api.post(f"/api/v1/checkins/{flagged}/review", headers=world["instructor"]["headers"],
                    json={"status": "flagged"}).status_code == 422
    assert api.post(f"/api/v1/checkins/{approved}/review", headers=world["instructor"]["headers"],
                    json={"status": "rejected"}).status_code == 400

    response = api.post(f"/api/v1/checkins/{flagged}/review", headers=world["instructor"]["headers"],
                        json={"status": "approved", "review_notes": "GPS issue confirmed"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "approved" and data["reviewed_by_id"] == world["instructor"]["id"]
    assert data["reviewed_at"] and data["review_notes"] == "GPS issue confirmed"

    # Already decided: no second review.
    assert api.post(f"/api/v1/checkins/{flagged}/review", headers=world["instructor"]["headers"],
                    json={"status": "rejected"}).status_code == 400


def test_review_of_appealed_checkin_requires_course_staff(api, world):
    student = _register(api, "student")
    enrolled = api.post("/api/v1/admin/enrollments/", headers=world["admin"]["headers"],
                        json={"student_id": student["id"], "course_id": world["course_id"]})
    assert enrolled.status_code == 201
    checkin = _check_in(api, student, world["session"]["id"], OFFSETS_M["flagged"])
    assert api.post(f"/api/v1/checkins/{checkin['id']}/appeal", headers=student["headers"],
                    json={"appeal_reason": "Indoor GPS drift"}).status_code == 200
    review = f"/api/v1/checkins/{checkin['id']}/review"
    # Unassigned TA is refused; assigned-TA reviews are covered in test_ta_scope.py.
    assert api.post(review, headers=world["ta"]["headers"], json={"status": "rejected"}).status_code == 403
    response = api.post(review, headers=world["instructor"]["headers"], json={"status": "rejected"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"


# --- Enrollments -------------------------------------------------------------

def test_bulk_enroll_counts_and_details(api, world):
    instructor, admin = world["instructor"], world["admin"]
    new_student = _register(api, "student")
    enrolled_email = world["students"]["approved"]["email"]
    unknown = _email("ghost")
    response = api.post("/api/v1/enrollments/bulk", headers=instructor["headers"], json={
        "course_id": world["course_id"],
        "student_emails": [new_student["email"], enrolled_email, unknown, new_student["email"]],
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["enrolled"], data["already_enrolled"], data["not_found"], data["created"]) == (1, 1, 1, 0)
    assert [d["status"] for d in data["details"]] == ["enrolled", "already_enrolled", "not_found"]

    roster = api.get(f"/api/v1/enrollments/course/{world['course_id']}", headers=admin["headers"]).json()
    assert new_student["id"] in [s["student_id"] for s in roster["students"]]


def test_bulk_enroll_create_accounts(api, world):
    unknown = _email("created")
    response = api.post("/api/v1/enrollments/bulk", headers=world["admin"]["headers"], json={
        "course_id": world["course_id"], "student_emails": [unknown], "create_accounts": True,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["created"] == 1 and data["enrolled"] == 1
    assert data["details"] == [{"email": unknown, "status": "created", "invitation_status": "queued", "invitation_pending": True}]


def test_bulk_enroll_permissions_and_validation(api, world):
    body = {"course_id": world["course_id"], "student_emails": [world["outsider"]["email"]]}
    assert api.post("/api/v1/enrollments/bulk", headers=world["other"]["headers"], json=body).status_code == 403
    assert api.post("/api/v1/enrollments/bulk", headers=world["outsider"]["headers"], json=body).status_code == 403
    assert api.post("/api/v1/enrollments/bulk", headers=world["admin"]["headers"],
                    json={**body, "course_id": str(uuid.uuid4())}).status_code == 404
    assert api.post("/api/v1/enrollments/bulk", headers=world["admin"]["headers"],
                    json={**body, "student_emails": ["nope"]}).status_code == 422


def test_delete_enrollment_then_re_enroll(api, world):
    admin, instructor = world["admin"], world["instructor"]
    student = _register(api, "student")
    created = api.post("/api/v1/enrollments/", headers=instructor["headers"],
                       json={"student_id": student["id"], "course_id": world["course_id"]})
    assert created.status_code == 201, created.text
    enrollment_id = created.json()["id"]

    assert api.delete(f"/api/v1/enrollments/{enrollment_id}", headers=world["other"]["headers"]).status_code == 403
    assert api.delete(f"/api/v1/enrollments/{enrollment_id}", headers=instructor["headers"]).status_code == 204
    assert api.delete(f"/api/v1/enrollments/{enrollment_id}", headers=instructor["headers"]).status_code == 404

    mine = api.get("/api/v1/enrollments/my-enrollments", headers=student["headers"]).json()
    assert world["course_id"] not in [e["course_id"] for e in mine]

    again = api.post("/api/v1/admin/enrollments/", headers=admin["headers"],
                     json={"student_id": student["id"], "course_id": world["course_id"]})
    assert again.status_code == 201, again.text
    assert again.json()["is_active"] is True


# --- Course export -----------------------------------------------------------

def test_course_export_boundaries_and_validation(api, world):
    url = f"/api/v1/export/attendance/{world['course_id']}"
    stamp = world["session"]["scheduled_start"]
    params = {"format": "json", "start_date": stamp, "end_date": stamp}
    exact = api.get(url, headers=world["instructor"]["headers"], params=params)
    assert exact.status_code == 200, exact.text
    # Earlier tests may add check-ins to this shared module fixture.
    assert {student["id"] for student in world["students"].values()} <= {
        record["student_id"] for record in exact.json()
    }
    assert all(record["session_name"] == world["session"]["name"] for record in exact.json())
    instant = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    local_day = instant.astimezone(timezone(timedelta(hours=8))).date().isoformat()
    params.update(start_date=local_day + "T00:00:00+08:00", end_date=local_day + "T23:59:59.999999+08:00")
    whole_day = api.get(url, headers=world["instructor"]["headers"], params=params)
    assert whole_day.status_code == 200 and whole_day.json() == exact.json()
    for bad in ({"format": "xml"}, {"start_date": "bad"}, {"end_date": "bad"}):
        assert api.get(url, headers=world["admin"]["headers"], params=bad).status_code == 422
    assert api.get(url, headers=world["ta"]["headers"]).status_code == 403
    assert api.get(url).status_code in (401, 403)


def test_course_export_unassigned_is_admin_only(api, world):
    result = api.post("/api/v1/courses/", headers=world["admin"]["headers"], json={
        "code": "EX" + uuid.uuid4().hex[:8], "name": "Unassigned export course", "semester": "Test"})
    assert result.status_code == 201, result.text
    url = f"/api/v1/export/attendance/{result.json()['id']}"
    assert api.get(url, headers=world["instructor"]["headers"]).status_code == 403
    admin = api.get(url, headers=world["admin"]["headers"], params={"format": "json"})
    assert admin.status_code == 200 and admin.json() == []

def test_export_course_attendance_csv_and_json(api, world):
    url = f"/api/v1/export/attendance/{world['course_id']}"
    csv_response = api.get(url, headers=world["instructor"]["headers"])
    assert csv_response.status_code == 200, csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(csv_response.text)))
    assert rows[0] == ["student_id", "student_name", "student_email", "session_date",
                       "session_name", "status", "checked_in_at", "risk_score"]
    assert len(rows) - 1 >= len(world["checkins"])

    json_response = api.get(url, headers=world["admin"]["headers"], params={"format": "json"})
    assert json_response.status_code == 200
    records = json_response.json()
    assert isinstance(records, list)
    assert {r["student_id"] for r in records} >= {s["id"] for s in world["students"].values()}


def test_export_course_attendance_date_filter_and_access(api, world):
    url = f"/api/v1/export/attendance/{world['course_id']}"
    future = _iso(_now() + timedelta(days=30))
    empty = api.get(url, headers=world["admin"]["headers"], params={"format": "json", "start_date": future,
                    "end_date": _iso(_now() + timedelta(days=31))})
    assert empty.status_code == 200 and empty.json() == []
    assert api.get(url, headers=world["admin"]["headers"], params={
        "start_date": future, "end_date": _iso(_now())}).status_code == 400
    assert api.get(url, headers=world["other"]["headers"]).status_code == 403
    assert api.get(url, headers=world["students"]["approved"]["headers"]).status_code == 403
    assert api.get(f"/api/v1/export/attendance/{uuid.uuid4()}",
                   headers=world["admin"]["headers"]).status_code == 404
