"""Enrollment account creation now returns initial credentials instead of email."""
import json

import pytest
from sqlalchemy import MetaData, Table, Column, String
from sqlalchemy.exc import IntegrityError
from test_checkin_roster import world
from app.auth import hash_password, verify_password
from app.models import User, Enrollment, AuditLog


def bulk(world, emails, role="instructor", create=True):
    client, _, headers = world
    return client.post("/api/v1/enrollments/bulk", headers=headers(role), json={
        "course_id": "course", "student_emails": emails, "create_accounts": create,
    })


@pytest.mark.parametrize("role", ["instructor", "admin"])
def test_new_accounts_receive_distinct_usable_initial_passwords(world, role):
    client, db, _ = world
    response = bulk(world, ["new1@example.edu", "new2@example.edu", "new1@example.edu"], role)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["created"] == data["enrolled"] == 2
    assert len(data["details"]) == 2
    passwords = [row["initial_password"] for row in data["details"]]
    assert len(set(passwords)) == 2
    for row in data["details"]:
        password = row["initial_password"]
        assert len(password) >= 16
        assert "invitation_status" not in row
        user = db.query(User).filter_by(email=row["email"]).one()
        assert user.role == "student"
        assert user.hashed_password != password
        assert verify_password(password, user.hashed_password)
        assert db.query(Enrollment).filter_by(student_id=user.id, course_id="course", is_active=True).count() == 1
        login = client.post("/api/v1/auth/login", json={"email": row["email"], "password": password})
        assert login.status_code == 200, login.text
        serialized_audits = json.dumps([event.details for event in db.query(AuditLog).all()])
        assert password not in serialized_audits
        assert password not in client.get("/api/v1/users/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}).text
    repeat = bulk(world, [row["email"] for row in data["details"]], role).json()
    assert repeat["created"] == 0
    assert repeat["already_enrolled"] == 2
    assert all("initial_password" not in row for row in repeat["details"])


def test_existing_accounts_keep_passwords_and_no_new_credentials_are_exposed(world):
    _, db, _ = world
    existing = db.get(User, "s0")
    existing.hashed_password = hash_password("existing-password")
    enrollment = db.query(Enrollment).filter_by(student_id=existing.id).one()
    enrollment.is_active = False
    db.commit()
    previous = existing.hashed_password
    response = bulk(world, [existing.email, "missing@example.edu"], create=False)
    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert response.json()["not_found"] == 1
    assert all("initial_password" not in row for row in response.json()["details"])
    db.refresh(existing)
    assert existing.hashed_password == previous
    assert db.query(User).filter_by(email="missing@example.edu").count() == 0


@pytest.mark.parametrize("role", ["other", "ta", "s0"])
def test_unauthorized_roles_cannot_create_accounts_or_get_credentials(world, role):
    _, db, _ = world
    response = bulk(world, ["blocked@example.edu"], role)
    assert response.status_code == 403
    assert "initial_password" not in response.text
    assert db.query(User).filter_by(email="blocked@example.edu").count() == 0


@pytest.mark.parametrize("path", ["/auth/invitations/request", "/auth/invitations/validate", "/auth/invitations/complete", "/enrollments/invitations/resend"])
def test_removed_invitation_endpoints_are_unavailable(world, path):
    client, _, headers = world
    assert client.post("/api/v1" + path, headers=headers("admin"), json={}).status_code == 404
    assert client.get("/api/v1/enrollments/course/course/invitations", headers=headers("admin")).status_code == 404


def test_legacy_pending_invitation_metadata_does_not_block_password_login(world):
    client, db, _ = world
    table = Table("account_invitations", MetaData(), Column("user_id", String, primary_key=True), Column("used_at", String))
    table.create(db.get_bind(), checkfirst=True)
    db.execute(table.insert().values(user_id="s0", used_at=None))
    db.get(User, "s0").hashed_password = hash_password("existing-password")
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": "s0@example.edu", "password": "existing-password"})
    assert response.status_code == 200, response.text
    # Retiring the model must not leave legacy personal data behind during purge.
    from datetime import datetime, timedelta
    from sqlalchemy.orm import Session
    from sqlalchemy import func, select
    from app.data_deletion import purge_due_students
    now = datetime.utcnow()
    db.get(User, "s0").scheduled_deletion_at = now - timedelta(seconds=1)
    db.commit()
    assert purge_due_students(factory=lambda: Session(db.get_bind()), now=now) == 1
    assert db.execute(select(func.count()).select_from(table)).scalar() == 0


def test_failed_batch_rolls_back_created_accounts_and_does_not_return_credentials(world, monkeypatch):
    _, db, _ = world
    original = db.flush
    def fail_enrollment(*args, **kwargs):
        if any(isinstance(row, Enrollment) for row in db.new):
            raise IntegrityError("test conflict", {}, Exception("duplicate"))
        return original(*args, **kwargs)
    monkeypatch.setattr(db, "flush", fail_enrollment)
    response = bulk(world, ["rollback@example.edu"])
    assert response.status_code == 409, response.text
    assert "initial_password" not in response.text
    assert db.query(User).filter_by(email="rollback@example.edu").count() == 0
