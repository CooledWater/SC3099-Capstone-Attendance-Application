"""Enrollment management against a disposable backend; never shared data."""
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from test_missing_endpoints import api, _register, _make_course


@pytest.fixture(scope="module")
def roster_world(api):
    admin = _register(api, "admin")
    teacher = _register(api, "instructor")
    other = _register(api, "instructor")
    ta = _register(api, "ta")
    student = _register(api, "student", "Roster Alice")
    course = _make_course(api, admin, teacher)
    return dict(admin=admin, teacher=teacher, other=other, ta=ta, student=student, course=course)


def test_roster_is_scoped_and_ta_cannot_modify(api, roster_world):
    w = roster_world
    url = f"/api/v1/enrollments/course/{w['course']}"
    for role in ("teacher", "admin"):
        assert api.get(url, headers=w[role]["headers"]).status_code == 200
    for role in ("other", "student", "ta"):
        assert api.get(url, headers=w[role]["headers"]).status_code == 403
    assert api.get(url).status_code in (401, 403)
    body = {"course_id": w["course"], "student_id": w["student"]["id"]}
    for role in ("other", "ta", "student"):
        assert api.post("/api/v1/enrollments/", headers=w[role]["headers"], json=body).status_code == 403
    assert api.post("/api/v1/enrollments/bulk", headers=w["ta"]["headers"], json={
        "course_id": w["course"], "student_emails": [w["student"]["email"]],
    }).status_code == 403


def test_concurrent_duplicate_enrollment_returns_201_and_400(api, roster_world):
    w = roster_world
    body = {"course_id": w["course"], "student_id": w["student"]["id"]}
    def enroll(_):
        return api.post("/api/v1/enrollments/", headers=w["teacher"]["headers"], json=body).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(enroll, range(2))) == [201, 400]


def test_roster_search_filter_counts_and_soft_delete(api, roster_world):
    w = roster_world
    url = f"/api/v1/enrollments/course/{w['course']}"
    headers = w["teacher"]["headers"]
    active = api.get(url, headers=headers).json()
    assert active["total_enrolled"] == active["total_records"] == active["matching_count"] == 1
    enrollment_id = active["students"][0]["id"]
    assert enrollment_id != w["student"]["id"]
    assert api.get(url, headers=headers, params={"search": "ROSTER ALICE"}).json()["matching_count"] == 1
    assert api.get(url, headers=headers, params={"search": "%"}).json()["matching_count"] == 0
    assert api.get(url, headers=headers, params={"is_active": "bad"}).status_code == 422
    delete = f"/api/v1/enrollments/{enrollment_id}"
    for role in ("other", "ta", "student"):
        assert api.delete(delete, headers=w[role]["headers"]).status_code == 403
    assert api.delete(f"/api/v1/enrollments/{w['student']['id']}", headers=headers).status_code == 404
    response = api.delete(delete, headers=headers)
    assert response.status_code == 204 and not response.content
    inactive = api.get(url, headers=headers, params={"is_active": "false"}).json()
    assert inactive["total_records"] == inactive["inactive_count"] == inactive["matching_count"] == 1
    assert inactive["total_enrolled"] == 0
    assert api.get(url, headers=headers).json()["students"] == []
    assert api.get(url, headers=headers, params={"is_active": "all"}).json()["students"][0]["id"] == enrollment_id
    assert api.delete(delete, headers=headers).status_code == 404
    enrolled = api.post("/api/v1/enrollments/", headers=headers, json={"student_id": w["student"]["id"], "course_id": w["course"]})
    assert enrolled.status_code == 201 and enrolled.json()["id"] == enrollment_id


def test_bulk_outcomes_repeated_input_and_invalid_student(api, roster_world):
    w = roster_world
    unknown = f"missing-{uuid.uuid4().hex}@example.com"
    body = {"course_id": w["course"], "student_emails": [w["student"]["email"], unknown, unknown, w["teacher"]["email"]]}
    response = api.post("/api/v1/enrollments/bulk", headers=w["teacher"]["headers"], json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["already_enrolled"] == 1 and data["not_found"] == 2
    assert len(data["details"]) == 3
    assert api.post("/api/v1/enrollments/bulk", headers=w["other"]["headers"], json=body).status_code == 403
    assert api.post("/api/v1/enrollments/bulk", headers=w["teacher"]["headers"], json={**body, "student_emails": ["invalid"]}).status_code == 422
    bad_student = api.post("/api/v1/enrollments/", headers=w["teacher"]["headers"], json={"student_id": w["teacher"]["id"], "course_id": w["course"]})
    assert bad_student.status_code == 400
