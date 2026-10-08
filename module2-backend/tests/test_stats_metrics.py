"""Edge-case tests for the stats endpoints and API metrics (app/stats.py).

tests/public/test_observability.py only asserts that fields exist against
empty data. These tests build a real scenario (mixed check-in statuses across
sessions, two instructors, a TA) and check the numbers and the access rules.

HTTP tests run against a live backend, like tests/conftest.py:

    TEST_BACKEND_URL=http://127.0.0.1:8000 pytest module2-backend/tests -v

They skip when nothing is listening. The MetricsStore/MetricsMiddleware unit
tests need no server.
"""
import asyncio
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx
import pytest

BACKEND_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
PASSWORD = "testpassword123"

# Course radius is 100 m with risk_threshold 0.5, so risk = distance/200 and
# status flips: approved < 100 m <= flagged, rejected > 200 m. Offsets chosen
# away from the 0.3 / 0.5 band edges so rounding cannot move a check-in.
VENUE = (1.3483, 103.6831)
METERS_PER_DEGREE_LAT = 111_195.0
OFFSETS_M = {"s1": 0, "s2": 50, "s3": 80, "s4": 120, "s5": 500}  # s6 never checks in


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime) -> str:
    return value.isoformat() + "Z"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=BACKEND_URL, timeout=30.0) as client:
        try:
            client.get("/health")
        except httpx.ConnectError:
            pytest.skip(f"Backend not running at {BACKEND_URL}")
        yield client


def _register(api, role: str) -> dict:
    email = f"{role}_{uuid.uuid4().hex[:10]}@stats-test.com"
    response = api.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": f"Stats {role}", "role": role,
    })
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    login = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"id": user_id, "headers": _auth(login.json()["access_token"])}


def _make_course(api, admin, instructor_id):
    response = api.post("/api/v1/courses/", headers=admin["headers"], json={
        "code": f"ST{uuid.uuid4().hex[:8].upper()}",
        "name": "Stats Course",
        "semester": "AY2024-25 Sem 1",
        "instructor_id": instructor_id,
        "venue_latitude": VENUE[0],
        "venue_longitude": VENUE[1],
        "venue_name": "NTU LT1",
        "geofence_radius_meters": 100.0,
        "risk_threshold": 0.5,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _enroll(api, admin, student_id, course_id):
    response = api.post("/api/v1/admin/enrollments/", headers=admin["headers"],
                        json={"student_id": student_id, "course_id": course_id})
    assert response.status_code == 201, response.text


def _make_session(api, instructor, course_id, name, start_in_minutes=5):
    start = _now() + timedelta(minutes=start_in_minutes)
    response = api.post("/api/v1/sessions/", headers=instructor["headers"], json={
        "course_id": course_id,
        "name": name,
        "scheduled_start": _iso(start),
        "scheduled_end": _iso(start + timedelta(hours=2)),
        "checkin_opens_at": _iso(_now() - timedelta(minutes=10)),
        "checkin_closes_at": _iso(_now() + timedelta(minutes=30)),
        "require_liveness_check": False,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _set_status(api, admin, session_id, new_status):
    response = api.patch(f"/api/v1/admin/sessions/{session_id}/status",
                         headers=admin["headers"], json={"status": new_status})
    assert response.status_code == 200, response.text


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
    """Course A (instructor A) with 6 enrolled students and three sessions:

    * session 1 - active; s1..s5 check in at 0/50/80/120/500 m (s6 absent)
    * session 2 - closed; only s1 checked in
    * session 3 - scheduled; nobody checked in (not "held")

    Course B (instructor B) has s1 enrolled; course C (instructor A) is empty.
    """
    admin, instr_a, instr_b, ta = (_register(api, r) for r in ("admin", "instructor", "instructor", "ta"))
    students = {f"s{i}": _register(api, "student") for i in range(1, 7)}
    loner = _register(api, "student")  # enrolled nowhere

    course_a = _make_course(api, admin, instr_a["id"])
    course_b = _make_course(api, admin, instr_b["id"])
    course_c = _make_course(api, admin, instr_a["id"])
    for student in students.values():
        _enroll(api, admin, student["id"], course_a["id"])
    _enroll(api, admin, students["s1"]["id"], course_b["id"])

    session1 = _make_session(api, instr_a, course_a["id"], "Lecture 1", start_in_minutes=5)
    session2 = _make_session(api, instr_a, course_a["id"], "Lecture 2", start_in_minutes=10)
    session3 = _make_session(api, instr_a, course_a["id"], "Lecture 3", start_in_minutes=15)

    _set_status(api, admin, session1["id"], "active")
    checkins = {
        key: _check_in(api, students[key], session1["id"], offset)
        for key, offset in OFFSETS_M.items()
    }

    _set_status(api, admin, session2["id"], "active")
    checkin_s1_second = _check_in(api, students["s1"], session2["id"], 0)
    _set_status(api, admin, session2["id"], "closed")

    return {
        "admin": admin, "instr_a": instr_a, "instr_b": instr_b, "ta": ta,
        "students": students, "loner": loner,
        "course_a": course_a, "course_b": course_b, "course_c": course_c,
        "sessions": (session1, session2, session3),
        "checkins": checkins, "checkin_s1_second": checkin_s1_second,
    }


# ---------------------------------------------------------------------------
# Scenario sanity: the fixture must actually produce mixed statuses, otherwise
# every number asserted below would be trivially satisfied.
# ---------------------------------------------------------------------------

def test_scenario_produces_all_three_decisions(world):
    statuses = Counter(c["status"] for c in world["checkins"].values())
    assert statuses == {"approved": 3, "flagged": 1, "rejected": 1}


# ---------------------------------------------------------------------------
# GET /stats/sessions/{id}
# ---------------------------------------------------------------------------

class TestSessionStats:
    def test_counts_and_rates_match_checkins(self, api, world):
        session1 = world["sessions"][0]
        response = api.get(f"/api/v1/stats/sessions/{session1['id']}", headers=world["instr_a"]["headers"])
        assert response.status_code == 200
        data = response.json()

        checkins = list(world["checkins"].values())
        by_status = Counter(c["status"] for c in checkins)

        assert data["session_id"] == session1["id"]
        assert data["status"] == "active"
        assert data["total_enrolled"] == 6
        assert data["checked_in"] == data["checked_in_count"] == 5
        assert data["attendance_rate"] == round(5 / 6, 4)
        assert data["by_status"] == {
            "approved": by_status["approved"], "flagged": by_status["flagged"],
            "rejected": by_status["rejected"], "pending": 0, "appealed": 0,
        }
        assert data["approved_count"] == 3
        assert data["flagged_count"] == 1
        assert data["rejected_count"] == 1
        assert sum(data["by_status"].values()) == data["checked_in"]

    def test_risk_and_distance_aggregates(self, api, world):
        session1 = world["sessions"][0]
        data = api.get(f"/api/v1/stats/sessions/{session1['id']}",
                       headers=world["instr_a"]["headers"]).json()
        checkins = list(world["checkins"].values())
        risks = [c["risk_score"] for c in checkins]

        assert data["average_risk_score"] == pytest.approx(sum(risks) / len(risks), abs=1e-3)
        distances = [c["distance_from_venue_meters"] for c in checkins]
        assert data["average_distance_meters"] == pytest.approx(sum(distances) / len(distances), abs=0.01)

        expected = {"low": 0, "medium": 0, "high": 0}
        for risk in risks:
            expected["high" if risk >= 0.5 else "medium" if risk >= 0.3 else "low"] += 1
        assert data["risk_distribution"] == expected
        assert expected == {"low": 2, "medium": 1, "high": 2}  # scenario is band-diverse

    def test_timeline_is_five_minute_buckets_covering_every_checkin(self, api, world):
        session1 = world["sessions"][0]
        data = api.get(f"/api/v1/stats/sessions/{session1['id']}",
                       headers=world["instr_a"]["headers"]).json()
        timeline = data["checkin_timeline"]

        assert sum(bucket["count"] for bucket in timeline) == 5
        assert all(bucket["minute"] % 5 == 0 and bucket["minute"] >= 0 for bucket in timeline)
        assert [b["minute"] for b in timeline] == sorted(b["minute"] for b in timeline)
        # Check-in opened 10 minutes before the session was created here.
        assert data["average_checkin_time_minutes"] >= 10

    def test_session_without_checkins_returns_zeros_not_errors(self, api, world):
        session3 = world["sessions"][2]
        response = api.get(f"/api/v1/stats/sessions/{session3['id']}", headers=world["instr_a"]["headers"])
        assert response.status_code == 200
        data = response.json()

        assert data["total_enrolled"] == 6
        assert data["checked_in"] == 0
        assert data["attendance_rate"] == 0.0
        assert data["average_risk_score"] == 0.0
        assert data["average_distance_meters"] is None
        assert data["average_checkin_time_minutes"] is None
        assert data["checkin_timeline"] == []
        assert data["risk_distribution"] == {"low": 0, "medium": 0, "high": 0}

    def test_unknown_session_is_404(self, api, world):
        response = api.get(f"/api/v1/stats/sessions/{uuid.uuid4()}", headers=world["admin"]["headers"])
        assert response.status_code == 404

    def test_access_rules(self, api, world):
        url = f"/api/v1/stats/sessions/{world['sessions'][0]['id']}"
        assert api.get(url, headers=world["admin"]["headers"]).status_code == 200
        assert api.get(url, headers=world["ta"]["headers"]).status_code == 200
        assert api.get(url, headers=world["instr_b"]["headers"]).status_code == 403
        assert api.get(url, headers=world["students"]["s1"]["headers"]).status_code == 403
        assert api.get(url).status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /stats/courses/{id}
# ---------------------------------------------------------------------------

class TestCourseStats:
    def test_only_held_sessions_count_and_rates_are_correct(self, api, world):
        course_id = world["course_a"]["id"]
        data = api.get(f"/api/v1/stats/courses/{course_id}", headers=world["instr_a"]["headers"]).json()

        # The scheduled third session is excluded from every figure.
        assert data["total_sessions"] == 2
        assert data["total_enrolled"] == 6
        assert data["overall_attendance_rate"] == data["average_attendance_rate"] == round(6 / 12, 4)
        assert data["flagged_checkins"] == 1

        assert [s["checked_in"] for s in data["sessions"]] == [5, 1]  # ordered by start
        assert [s["attendance_rate"] for s in data["sessions"]] == [round(5 / 6, 4), round(1 / 6, 4)]

    def test_per_student_attendance_and_low_attendance_alerts(self, api, world):
        course_id = world["course_a"]["id"]
        data = api.get(f"/api/v1/stats/courses/{course_id}", headers=world["instr_a"]["headers"]).json()
        rows = {r["student_id"]: r for r in data["student_attendance"]}
        students = world["students"]

        assert rows[students["s1"]["id"]]["sessions_attended"] == 2
        assert rows[students["s1"]["id"]]["attendance_rate"] == 1.0
        assert rows[students["s2"]["id"]]["attendance_rate"] == 0.5
        assert rows[students["s6"]["id"]]["sessions_attended"] == 0
        assert rows[students["s6"]["id"]]["attendance_rate"] == 0.0
        assert rows[students["s4"]["id"]]["average_risk_score"] == pytest.approx(
            world["checkins"]["s4"]["risk_score"], abs=1e-3)

        alerts = {a["student_id"]: a for a in data["low_attendance_alerts"]}
        assert students["s1"]["id"] not in alerts
        assert set(alerts) == {students[k]["id"] for k in ("s2", "s3", "s4", "s5", "s6")}
        assert alerts[students["s6"]["id"]]["sessions_missed"] == 2
        assert alerts[students["s2"]["id"]]["sessions_missed"] == 1

    def test_course_with_no_sessions_or_students_does_not_divide_by_zero(self, api, world):
        data = api.get(f"/api/v1/stats/courses/{world['course_c']['id']}",
                       headers=world["instr_a"]["headers"]).json()
        assert data["total_sessions"] == 0
        assert data["total_enrolled"] == 0
        assert data["overall_attendance_rate"] == 0.0
        assert data["sessions"] == [] and data["student_attendance"] == []
        assert data["low_attendance_alerts"] == []

    def test_date_range_filters_sessions(self, api, world):
        course_id = world["course_a"]["id"]
        headers = world["instr_a"]["headers"]

        future = api.get(f"/api/v1/stats/courses/{course_id}", headers=headers,
                         params={"start_date": _iso(_now() + timedelta(days=30))}).json()
        assert future["total_sessions"] == 0
        assert future["overall_attendance_rate"] == 0.0
        assert future["low_attendance_alerts"] == []  # nothing held -> nobody "missed" anything

        past = api.get(f"/api/v1/stats/courses/{course_id}", headers=headers,
                       params={"end_date": _iso(_now() - timedelta(days=30))}).json()
        assert past["total_sessions"] == 0

        # Only the first session starts before now+8 minutes.
        window = api.get(f"/api/v1/stats/courses/{course_id}", headers=headers,
                         params={"end_date": _iso(_now() + timedelta(minutes=8))}).json()
        assert window["total_sessions"] == 1
        assert window["sessions"][0]["checked_in"] == 5

    def test_start_after_end_is_400(self, api, world):
        response = api.get(f"/api/v1/stats/courses/{world['course_a']['id']}",
                           headers=world["instr_a"]["headers"],
                           params={"start_date": "2030-01-02T00:00:00Z", "end_date": "2030-01-01T00:00:00Z"})
        assert response.status_code == 400

    def test_access_rules(self, api, world):
        url = f"/api/v1/stats/courses/{world['course_a']['id']}"
        assert api.get(url, headers=world["admin"]["headers"]).status_code == 200
        assert api.get(url, headers=world["instr_b"]["headers"]).status_code == 403
        assert api.get(url, headers=world["ta"]["headers"]).status_code == 403
        assert api.get(url, headers=world["students"]["s1"]["headers"]).status_code == 403
        assert api.get(f"/api/v1/stats/courses/{uuid.uuid4()}",
                       headers=world["admin"]["headers"]).status_code == 404


# ---------------------------------------------------------------------------
# GET /stats/students/{id}
# ---------------------------------------------------------------------------

class TestStudentStats:
    def test_attendance_across_courses(self, api, world):
        s1 = world["students"]["s1"]
        data = api.get(f"/api/v1/stats/students/{s1['id']}", headers=world["admin"]["headers"]).json()

        assert data["student_id"] == s1["id"]
        assert data["total_enrolled_courses"] == 2
        # Course B has no held sessions, so only course A's two count.
        assert data["total_sessions"] == 2
        assert data["attended_sessions"] == 2
        assert data["attendance_rate"] == 1.0

        by_code = {c["course_id"]: c for c in data["courses"]}
        assert by_code[world["course_a"]["id"]]["sessions_attended"] == 2
        assert by_code[world["course_a"]["id"]]["total_sessions"] == 2
        assert by_code[world["course_b"]["id"]]["total_sessions"] == 0
        assert by_code[world["course_b"]["id"]]["attendance_rate"] == 0.0

    def test_partial_attendance_and_recent_history(self, api, world):
        s2 = world["students"]["s2"]
        data = api.get(f"/api/v1/stats/students/{s2['id']}", headers=world["instr_a"]["headers"]).json()

        assert data["total_enrolled_courses"] == 1
        assert data["total_sessions"] == 2
        assert data["attended_sessions"] == 1
        assert data["attendance_rate"] == 0.5
        assert data["average_risk_score"] == pytest.approx(world["checkins"]["s2"]["risk_score"], abs=1e-3)

        assert data["recent_checkins"] == data["recent_sessions"]
        assert len(data["recent_sessions"]) == 1
        assert data["recent_sessions"][0]["status"] == "approved"

    def test_recent_history_is_newest_first(self, api, world):
        s1 = world["students"]["s1"]
        recent = api.get(f"/api/v1/stats/students/{s1['id']}",
                         headers=world["admin"]["headers"]).json()["recent_sessions"]
        assert [r["session_name"] for r in recent] == ["Lecture 2", "Lecture 1"]

    def test_student_enrolled_nowhere(self, api, world):
        url = f"/api/v1/stats/students/{world['loner']['id']}"
        data = api.get(url, headers=world["admin"]["headers"]).json()
        assert data["total_enrolled_courses"] == 0
        assert data["total_sessions"] == 0
        assert data["attendance_rate"] == 0.0
        assert data["average_risk_score"] == 0.0
        assert data["courses"] == [] and data["recent_sessions"] == []
        # An instructor shares no course with this student.
        assert api.get(url, headers=world["instr_a"]["headers"]).status_code == 403

    def test_access_rules(self, api, world):
        s1, s2 = world["students"]["s1"], world["students"]["s2"]
        # s1 is also in instructor B's course, s2 is only in instructor A's.
        assert api.get(f"/api/v1/stats/students/{s1['id']}", headers=world["instr_b"]["headers"]).status_code == 200
        assert api.get(f"/api/v1/stats/students/{s2['id']}", headers=world["instr_b"]["headers"]).status_code == 403
        assert api.get(f"/api/v1/stats/students/{s1['id']}", headers=s1["headers"]).status_code == 403
        assert api.get(f"/api/v1/stats/students/{s1['id']}", headers=world["ta"]["headers"]).status_code == 403

    def test_unknown_id_and_non_student_are_404(self, api, world):
        admin = world["admin"]["headers"]
        assert api.get(f"/api/v1/stats/students/{uuid.uuid4()}", headers=admin).status_code == 404
        assert api.get(f"/api/v1/stats/students/{world['instr_a']['id']}", headers=admin).status_code == 404


# ---------------------------------------------------------------------------
# GET /stats/overview
# ---------------------------------------------------------------------------

class TestOverview:
    def test_scoped_to_one_course(self, api, world):
        data = api.get("/api/v1/stats/overview", headers=world["instr_a"]["headers"],
                       params={"course_id": world["course_a"]["id"]}).json()
        checkins = list(world["checkins"].values()) + [world["checkin_s1_second"]]

        assert data["total_sessions"] == 3          # scheduled + active + closed
        assert data["active_sessions"] == 1
        assert data["total_courses"] == 1
        assert data["total_students"] == 6
        assert data["today_checkins"] == data["total_checkins_today"] == 6
        assert data["total_checkins_week"] == 6
        assert data["flagged_pending"] == data["flagged_pending_review"] == 1
        assert data["approval_rate"] == round(sum(c["status"] == "approved" for c in checkins) / 6, 4)
        assert data["average_attendance_rate"] == round(6 / 12, 4)
        assert data["average_risk_score"] == pytest.approx(
            sum(c["risk_score"] for c in checkins) / 6, abs=1e-3)
        assert data["high_risk_checkins_today"] == sum(c["risk_score"] >= 0.5 for c in checkins)

    def test_trends(self, api, world):
        session1 = world["sessions"][0]
        data = api.get("/api/v1/stats/overview", headers=world["instr_a"]["headers"],
                       params={"course_id": world["course_a"]["id"], "days": 3}).json()
        checkin_day = world["checkins"]["s1"]["checked_in_at"][:10]
        session_day = session1["scheduled_start"][:10]

        by_day = data["trends"]["checkins_by_day"]
        assert len(by_day) == 3                                     # zero-filled, one per day
        assert [d["date"] for d in by_day] == sorted((d["date"] for d in by_day), reverse=True)
        assert {d["date"]: d["count"] for d in by_day}[checkin_day] == 6
        assert sum(d["count"] for d in by_day) == 6

        rates = {d["date"]: d["rate"] for d in data["trends"]["attendance_rate_by_day"]}
        assert rates[session_day] == round(6 / 12, 4)
        assert len(rates) <= 3

    @pytest.mark.parametrize("days,expected", [(0, 1), (-5, 1), (1000, 90)])
    def test_days_is_clamped(self, api, world, days, expected):
        response = api.get("/api/v1/stats/overview", headers=world["admin"]["headers"],
                           params={"days": days})
        assert response.status_code == 200
        assert len(response.json()["trends"]["checkins_by_day"]) == expected

    def test_rates_are_always_numeric(self, api):
        # Never null, even when a denominator is zero (e.g. no check-ins yet).
        fresh = _register(api, "instructor")
        response = api.get("/api/v1/stats/overview", headers=fresh["headers"])
        assert response.status_code == 200
        data = response.json()
        for key in ("approval_rate", "average_attendance_rate", "average_risk_score"):
            assert isinstance(data[key], (int, float)) and data[key] >= 0

    def test_admin_sees_system_wide_totals(self, api, world):
        data = api.get("/api/v1/stats/overview", headers=world["admin"]["headers"]).json()
        assert data["total_students"] >= 7          # s1..s6 + loner
        assert data["total_courses"] >= 3
        assert data["total_sessions"] >= 3

    def test_instructor_scope_excludes_other_instructors_courses(self, api, world):
        a = api.get("/api/v1/stats/overview", headers=world["instr_a"]["headers"]).json()
        b = api.get("/api/v1/stats/overview", headers=world["instr_b"]["headers"]).json()
        # A teaches courses A and C (3 sessions); B teaches only course B (none).
        assert a["total_sessions"] >= 3
        assert b["today_checkins"] < a["today_checkins"]
        assert api.get("/api/v1/stats/overview", headers=world["instr_b"]["headers"],
                       params={"course_id": world["course_a"]["id"]}).status_code == 403

    def test_unknown_course_is_404_and_students_and_tas_are_forbidden(self, api, world):
        assert api.get("/api/v1/stats/overview", headers=world["admin"]["headers"],
                       params={"course_id": str(uuid.uuid4())}).status_code == 404
        assert api.get("/api/v1/stats/overview", headers=world["students"]["s1"]["headers"]).status_code == 403
        assert api.get("/api/v1/stats/overview", headers=world["ta"]["headers"]).status_code == 403
        assert api.get("/api/v1/stats/overview").status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /metrics/ (HTTP)
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    def test_shape_matches_what_module4_reads(self, api, world):
        # Generate traffic, including a 404 that must not count as a failure.
        headers = world["instr_a"]["headers"]
        session_id = world["sessions"][0]["id"]
        for _ in range(3):
            api.get(f"/api/v1/stats/sessions/{session_id}", headers=headers)
        for _ in range(2):
            api.get(f"/api/v1/stats/sessions/{uuid.uuid4()}", headers=headers)

        response = api.get("/api/v1/metrics/", params={"limit": 120}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"items", "total", "limit", "window_hours"}
        assert body["items"], "expected traffic to have been recorded"

        for item in body["items"]:
            assert set(item) == {"id", "recorded_at", "endpoint", "p95_ms", "request_count", "success_rate"}
            assert item["request_count"] >= 1
            assert item["p95_ms"] >= 0
            assert 0 <= item["success_rate"] <= 100

        by_endpoint = {}
        for item in body["items"]:
            by_endpoint.setdefault(item["endpoint"], []).append(item)

        # Labelled by route template, so ids do not create a series each.
        template = "GET /api/v1/stats/sessions/{session_id}"
        assert template in by_endpoint
        assert not any(session_id in endpoint for endpoint in by_endpoint)
        assert sum(i["request_count"] for i in by_endpoint[template]) >= 5
        assert all(i["success_rate"] == 100 for i in by_endpoint[template])  # 404s are not failures

    def test_unmatched_paths_share_one_label(self, api, world):
        for _ in range(2):
            api.get(f"/api/v1/no-such-route/{uuid.uuid4()}")
        items = api.get("/api/v1/metrics/", params={"limit": 500},
                        headers=world["admin"]["headers"]).json()["items"]
        endpoints = {i["endpoint"] for i in items}
        assert "unmatched" in endpoints
        assert not any("no-such-route" in e for e in endpoints)

    def test_limit_and_endpoint_filter(self, api, world):
        headers = world["admin"]["headers"]
        one = api.get("/api/v1/metrics/", params={"limit": 1}, headers=headers).json()
        assert len(one["items"]) == 1 and one["limit"] == 1
        assert api.get("/api/v1/metrics/", params={"limit": 0}, headers=headers).json()["limit"] == 1
        assert api.get("/api/v1/metrics/", params={"limit": 99999}, headers=headers).json()["limit"] == 500

        filtered = api.get("/api/v1/metrics/", headers=headers,
                           params={"endpoint": "GET /health"}).json()["items"]
        assert all(i["endpoint"] == "GET /health" for i in filtered)
        assert api.get("/api/v1/metrics/", headers=headers,
                       params={"endpoint": "nope"}).json()["items"] == []

    def test_hours_is_clamped(self, api, world):
        headers = world["admin"]["headers"]
        assert api.get("/api/v1/metrics/", params={"hours": 0}, headers=headers).json()["window_hours"] == 1
        assert api.get("/api/v1/metrics/", params={"hours": 999}, headers=headers).json()["window_hours"] == 24

    def test_access_rules(self, api, world):
        assert api.get("/api/v1/metrics/", headers=world["instr_a"]["headers"]).status_code == 200
        assert api.get("/api/v1/metrics/", headers=world["admin"]["headers"]).status_code == 200
        assert api.get("/api/v1/metrics/", headers=world["students"]["s1"]["headers"]).status_code == 403
        assert api.get("/api/v1/metrics/").status_code in (401, 403)


# ---------------------------------------------------------------------------
# MetricsStore / MetricsMiddleware (no server needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def stats_module():
    # app.stats pulls in app.database, which insists on DATABASE_URL at import.
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app import stats
    return stats


HOUR = 3600
T0 = 1_800_000_000 - (1_800_000_000 % HOUR)  # exact hour boundary


class TestMetricsStore:
    def test_p95_is_nearest_rank(self, stats_module):
        store = stats_module.MetricsStore()
        for ms in range(1, 101):
            store.record("GET /x", float(ms), 200, now=T0)
        (item,), total = store.snapshot(12, 10, now=T0 + 10)
        assert total == 1
        assert item["p95_ms"] == 95.0
        assert item["request_count"] == 100
        assert item["success_rate"] == 100.0

    def test_single_sample(self, stats_module):
        store = stats_module.MetricsStore()
        store.record("GET /x", 12.34, 200, now=T0)
        (item,), _ = store.snapshot(12, 10, now=T0)
        assert item["p95_ms"] == 12.3

    def test_only_5xx_count_as_failures(self, stats_module):
        store = stats_module.MetricsStore()
        for code in (200, 404, 401, 500):
            store.record("GET /x", 1.0, code, now=T0)
        (item,), _ = store.snapshot(12, 10, now=T0)
        assert item["success_rate"] == 75.0

    def test_buckets_are_hourly_newest_first_and_labelled_in_utc(self, stats_module):
        store = stats_module.MetricsStore()
        store.record("GET /a", 1.0, 200, now=T0)
        store.record("GET /a", 1.0, 200, now=T0 + HOUR)
        store.record("GET /b", 1.0, 200, now=T0 + HOUR)
        items, total = store.snapshot(12, 10, now=T0 + HOUR + 5)
        assert total == 3
        # Newest hour first (both endpoints, alphabetical), then the older hour.
        assert [i["endpoint"] for i in items] == ["GET /a", "GET /b", "GET /a"]
        assert items[0]["recorded_at"] == items[1]["recorded_at"] > items[2]["recorded_at"]
        assert items[0]["recorded_at"].endswith("Z")
        assert datetime.fromisoformat(items[0]["recorded_at"].rstrip("Z")) - datetime.fromisoformat(
            items[2]["recorded_at"].rstrip("Z")) == timedelta(hours=1)
        assert len({i["id"] for i in items}) == 3

    def test_window_limit_and_filter(self, stats_module):
        store = stats_module.MetricsStore()
        store.record("GET /old", 1.0, 200, now=T0)
        store.record("GET /new", 1.0, 200, now=T0 + 5 * HOUR)
        now = T0 + 5 * HOUR + 10
        assert [i["endpoint"] for i in store.snapshot(2, 10, now=now)[0]] == ["GET /new"]
        assert store.snapshot(12, 10, now=now)[1] == 2
        items, total = store.snapshot(12, 1, now=now)
        assert len(items) == 1 and total == 2                      # total is pre-limit
        assert store.snapshot(12, 10, endpoint="GET /old", now=now)[1] == 1

    def test_old_buckets_are_pruned(self, stats_module):
        store = stats_module.MetricsStore()
        store.record("GET /x", 1.0, 200, now=T0)
        store.record("GET /x", 1.0, 200, now=T0 + (stats_module.RETENTION_HOURS + 1) * HOUR)
        assert list(store._buckets) == [(int((T0 + (stats_module.RETENTION_HOURS + 1) * HOUR) // HOUR), "GET /x")]

    def test_memory_is_bounded_but_counts_stay_exact(self, stats_module):
        store = stats_module.MetricsStore()
        n = stats_module.MAX_SAMPLES_PER_BUCKET * 5
        for i in range(n):
            store.record("GET /x", float(i), 500 if i % 10 == 0 else 200, now=T0)
        bucket = store._buckets[(T0 // HOUR, "GET /x")]
        assert len(bucket.samples) == stats_module.MAX_SAMPLES_PER_BUCKET
        (item,), _ = store.snapshot(12, 10, now=T0)
        assert item["request_count"] == n
        assert item["success_rate"] == 90.0
        # Uniform reservoir over 0..n-1: p95 should land near 95% of the range.
        assert item["p95_ms"] == pytest.approx(0.95 * n, rel=0.05)

    def test_empty_store(self, stats_module):
        assert stats_module.MetricsStore().snapshot(12, 10) == ([], 0)


class TestMetricsMiddleware:
    def _run(self, stats_module, app, scope):
        store = stats_module.MetricsStore()
        original = stats_module.metrics_store
        stats_module.metrics_store = store
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        try:
            error = None
            try:
                asyncio.run(stats_module.MetricsMiddleware(app)(scope, receive, send))
            except Exception as exc:  # noqa: BLE001 - asserting it propagates
                error = exc
        finally:
            stats_module.metrics_store = original
        return store, sent, error

    def test_records_status_and_route_template(self, stats_module):
        class Route:
            path = "/api/v1/things/{thing_id}"

        async def app(scope, receive, send):
            scope["route"] = Route()  # what FastAPI's router does after matching
            await send({"type": "http.response.start", "status": 201, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        store, sent, error = self._run(stats_module, app, {"type": "http", "method": "POST", "path": "/api/v1/things/42"})
        assert error is None and len(sent) == 2
        (item,), _ = store.snapshot(1, 10)
        assert item["endpoint"] == "POST /api/v1/things/{thing_id}"
        assert item["success_rate"] == 100.0

    def test_unhandled_exception_is_recorded_as_failure_and_reraised(self, stats_module):
        async def app(scope, receive, send):
            raise RuntimeError("boom")

        store, _, error = self._run(stats_module, app, {"type": "http", "method": "GET", "path": "/x"})
        assert isinstance(error, RuntimeError)
        (item,), _ = store.snapshot(1, 10)
        assert item["endpoint"] == "unmatched"
        assert item["success_rate"] == 0.0

    def test_non_http_scopes_are_ignored(self, stats_module):
        async def app(scope, receive, send):
            return None

        store, _, error = self._run(stats_module, app, {"type": "lifespan"})
        assert error is None
        assert store.snapshot(1, 10) == ([], 0)
