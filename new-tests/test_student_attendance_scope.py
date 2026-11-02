"""Student details privacy regressions using an isolated in-memory database."""
from datetime import timedelta

import pytest
from test_instructor_strict_scope import api, START
from app.main import app
from app.database import get_db
from app.models import CheckIn, Course, Enrollment, Session as Meeting


def shared_student():
    db = next(app.dependency_overrides[get_db]())
    db.add(Enrollment(id="shared-b", student_id="sa", course_id="B", enrolled_at=START))
    # Enough newer private records to hide every authorised record if LIMIT is
    # applied before instructor scoping.
    for i in range(12):
        when = START + timedelta(days=i + 1)
        db.add(Meeting(id=f"private-{i}", course_id="B", instructor_id="ib", name=f"Private {i}", status="closed",
                       scheduled_start=when, scheduled_end=when + timedelta(hours=1),
                       checkin_opens_at=when, checkin_closes_at=when + timedelta(minutes=20)))
        db.add(CheckIn(id=f"private-checkin-{i}", session_id=f"private-{i}", student_id="sa", status="approved",
                       checked_in_at=when, risk_score=0.1, risk_factors="[]"))
    db.commit()
    return db


def test_shared_student_returns_only_instructors_courses_and_checkins(api):
    shared_student()
    response = api("GET", "ia", "/stats/students/sa")
    assert response.status_code == 200
    data = response.json()
    assert {c["course_id"] for c in data["courses"]} == {"A"}
    assert data["total_enrolled_courses"] == 1
    assert data["total_sessions"] == 2
    assert data["attended_sessions"] == 2
    assert data["average_risk_score"] == 0.6
    assert {c["session_id"] for c in data["recent_checkins"]} == {"m_a", "m_c"}
    assert data["recent_sessions"] == data["recent_checkins"]
    other = api("GET", "ib", "/stats/students/sa").json()
    assert {c["course_id"] for c in other["courses"]} == {"B"}
    assert len(other["recent_checkins"]) == 10
    assert all(c["course_code"] == "B100" for c in other["recent_checkins"])


def test_admin_keeps_all_course_access_and_recent_limit(api):
    shared_student()
    data = api("GET", "admin", "/stats/students/sa").json()
    assert {c["course_id"] for c in data["courses"]} == {"A", "B"}
    assert data["attended_sessions"] == 14
    assert len(data["recent_checkins"]) == 10
    times = [c["checked_in_at"] for c in data["recent_checkins"]]
    assert times == sorted(times, reverse=True)


@pytest.mark.parametrize("uid", ["ta", "sa", "ic"])
def test_student_details_deny_tas_students_and_unrelated_instructors(api, uid):
    shared_student()
    assert api("GET", uid, "/stats/students/sa").status_code == 403


def test_empty_authorised_course_and_unknown_student(api):
    db = next(app.dependency_overrides[get_db]())
    db.add(Course(id="empty-course", code="E100", name="Empty", semester="S1", instructor_id="ia"))
    db.add(Enrollment(id="empty-enrollment", student_id="sb", course_id="empty-course", enrolled_at=START))
    db.commit()
    data = api("GET", "ia", "/stats/students/sb").json()
    assert len(data["courses"]) == 1
    assert data["courses"][0]["total_sessions"] == 0
    assert data["recent_checkins"] == []
    assert api("GET", "ia", "/stats/students/missing").status_code == 404
