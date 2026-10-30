"""One connected staff/student workflow against an isolated FastAPI database."""
from datetime import datetime, timedelta

from test_checkin_roster import world
from app.models import Course


def test_account_enrollment_ta_review_instructor_export_and_admin_audit(world):
    client, db, headers = world
    course = db.get(Course, "course")
    course.venue_latitude = 1.3483
    course.venue_longitude = 103.6831
    course.geofence_radius_meters = 100
    db.commit()

    assigned = client.post("/api/v1/admin/courses/course/tas", headers=headers("admin"), json={"user_id": "ta"})
    assert assigned.status_code == 201, assigned.text
    assert client.post("/api/v1/enrollments/bulk", headers=headers("ta"), json={
        "course_id": "course", "student_emails": ["not-allowed@example.edu"], "create_accounts": True,
    }).status_code == 403

    enrollment = client.post("/api/v1/enrollments/bulk", headers=headers("instructor"), json={
        "course_id": "course", "student_emails": ["new-student@example.edu"], "create_accounts": True,
    })
    assert enrollment.status_code == 200, enrollment.text
    detail = enrollment.json()["details"][0]
    signed_in = client.post("/api/v1/auth/login", json={"email": detail["email"], "password": detail["initial_password"]})
    assert signed_in.status_code == 200, signed_in.text
    student_headers = {"Authorization": "Bearer " + signed_in.json()["access_token"]}

    now = datetime.utcnow()
    iso = lambda value: value.isoformat() + "Z"
    created = client.post("/api/v1/sessions/", headers=headers("instructor"), json={
        "course_id": "course", "name": "Connected role flow",
        "scheduled_start": iso(now + timedelta(minutes=5)), "scheduled_end": iso(now + timedelta(hours=1)),
        "checkin_opens_at": iso(now - timedelta(minutes=5)), "checkin_closes_at": iso(now + timedelta(minutes=30)),
        "require_liveness_check": False, "require_face_match": False,
    })
    assert created.status_code == 201, created.text
    meeting = created.json()["id"]
    activated = client.patch(f"/api/v1/admin/sessions/{meeting}/status", headers=headers("admin"), json={"status": "active"})
    assert activated.status_code == 200, activated.text
    submitted = client.post("/api/v1/checkins/", headers=student_headers, json={
        "session_id": meeting, "latitude": 1.3483, "longitude": 103.6831,
        "device_fingerprint": "connected-flow-unverified-browser",
    })
    assert submitted.status_code == 201, submitted.text
    # Unknown devices are flagged by the actual policy, even at the venue.
    record = submitted.json()
    assert record["status"] == "flagged"
    assert client.get(f"/api/v1/sessions/{meeting}/attendance", headers=headers("ta")).status_code == 200
    reviewed = client.post(f"/api/v1/checkins/{record['id']}/review", headers=headers("ta"), json={
        "status": "approved", "review_notes": "Independently verified student identity and attendance",
    })
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    history = client.get("/api/v1/checkins/my-checkins", headers=student_headers)
    assert history.status_code == 200, history.text
    assert any(row["id"] == record["id"] and row["status"] == "approved" for row in history.json())

    export_path = "/api/v1/export/attendance/course"
    params = {"format": "json", "start_date": iso(now - timedelta(days=1)), "end_date": iso(now + timedelta(days=1))}
    exported = client.get(export_path, headers=headers("instructor"), params=params)
    assert exported.status_code == 200, exported.text
    assert client.get(export_path, headers=headers("ta"), params=params).status_code == 403
    assert client.get("/api/v1/audit/", headers=headers("instructor")).status_code == 403
    audit = client.get("/api/v1/audit/", headers=headers("admin"), params={"action": "checkin_reviewed", "resource_id": record["id"]})
    assert audit.status_code == 200, audit.text
    assert audit.json()["items"]
