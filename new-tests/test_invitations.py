"""Invitation security, durable delivery, and setup; all storage is disposable."""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import socketserver
import threading
import tempfile
from email import policy
from email.parser import BytesParser

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "invitation-test-secret")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))
from app import invitations
from app.database import Base, get_db, get_read_db
from app.models import User, Course, Enrollment
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from test_missing_endpoints import api, _register, _make_course


@pytest.fixture
def world(monkeypatch):
    temporary = tempfile.TemporaryDirectory(prefix="saiv-invitation-tests-")
    engine = create_engine(f"sqlite:///{(Path(temporary.name) / 'invite.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(invitations, "SessionLocal", factory)
    invitations._request_windows.clear()
    with factory() as db:
        for user_id, role in (("student", "student"), ("teacher", "instructor"), ("other", "instructor"), ("admin", "admin")):
            db.add(User(id=user_id, email=f"{user_id}@example.edu", full_name=user_id, role=role, hashed_password=hash_password("original-password")))
        db.add(Course(id="course", code="SC4000", name="Machine Learning", semester="test", instructor_id="teacher"))
        db.add(Enrollment(student_id="student", course_id="course"))
        invitation = invitations.queue_invitation(db, "student", "course")
        token = invitations.setup_token(invitation)
        db.commit()
    def database():
        with factory() as db:
            yield db
    app = FastAPI()
    app.include_router(invitations.router)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_read_db] = database
    @app.get("/protected")
    def protected(user=Depends(get_current_user)):
        return {"id": user.id}
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=factory, token=token,
                              headers=lambda role: {"Authorization": "Bearer " + create_access_token(role, role if role == "admin" else "instructor")})
    engine.dispose()
    temporary.cleanup()


def test_validate_complete_and_single_use(world):
    c = world.client
    assert c.post("/api/v1/auth/invitations/validate", json={"token": world.token}).json() == {"email": "student@example.edu"}
    assert c.get("/protected", headers={"Authorization": "Bearer " + world.token}).status_code == 401
    response = c.post("/api/v1/auth/invitations/complete", json={"token": world.token, "password": "new-password-123"})
    assert response.status_code == 200
    with world.db() as db:
        assert verify_password("new-password-123", db.get(User, "student").hashed_password)
        assert db.get(invitations.AccountInvitation, "student").used_at
    assert c.post("/api/v1/auth/invitations/complete", json={"token": world.token, "password": "another-password"}).status_code == 400
    assert c.post("/api/v1/auth/invitations/validate", json={"token": world.token}).status_code == 400


def test_concurrent_consumption_only_changes_password_once(world):
    passwords = ["first-password-123", "second-password-123"]
    def complete(password):
        return world.client.post("/api/v1/auth/invitations/complete", json={"token": world.token, "password": password}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(complete, passwords))
    assert sorted(codes) == [200, 400]
    with world.db() as db:
        assert verify_password(passwords[codes.index(200)], db.get(User, "student").hashed_password)


def test_expiry_tampering_and_disabled_account(world):
    c = world.client
    for token in ("garbage", world.token + "x"):
        assert c.post("/api/v1/auth/invitations/validate", json={"token": token}).status_code == 400
    with world.db() as db:
        db.get(invitations.AccountInvitation, "student").expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert c.post("/api/v1/auth/invitations/complete", json={"token": world.token, "password": "new-password-123"}).status_code == 400
    with world.db() as db:
        invitations.queue_invitation(db, "student", "course", db.get(invitations.AccountInvitation, "student"))
        db.get(User, "student").is_active = False
        token = invitations.setup_token(db.get(invitations.AccountInvitation, "student"))
        db.commit()
    assert c.post("/api/v1/auth/invitations/validate", json={"token": token}).status_code == 400


def test_resend_scoping_cooldown_and_rotation(world):
    url = "/api/v1/enrollments/invitations/resend"
    body = {"course_id": "course", "email": "student@example.edu"}
    assert world.client.post(url, json=body, headers=world.headers("other")).status_code == 403
    assert world.client.post(url, json=body, headers=world.headers("teacher")).status_code == 429
    with world.db() as db:
        db.get(invitations.AccountInvitation, "student").issued_at -= timedelta(minutes=2)
        db.commit()
    assert world.client.post(url, json=body, headers=world.headers("teacher")).json()["invitation_status"] == "queued"
    assert world.client.post("/api/v1/auth/invitations/validate", json={"token": world.token}).status_code == 400
    status_url = "/api/v1/enrollments/course/course/invitations"
    assert world.client.get(status_url, headers=world.headers("other")).status_code == 403
    data = world.client.get(status_url, headers=world.headers("teacher")).json()
    assert data["items"][0]["invitation_pending"] is True
    assert "token" not in data["items"][0]


def test_failed_delivery_keeps_account_and_enrollment(world, monkeypatch):
    def fail(*args):
        raise RuntimeError("sensitive smtp diagnostic")
    monkeypatch.setattr(invitations, "send_email", fail)
    assert invitations.deliver_next()
    with world.db() as db:
        row = db.get(invitations.AccountInvitation, "student")
        assert row.delivery_status == "failed"
        assert "sensitive" not in row.delivery_error
        assert db.query(Enrollment).count() == 1
        assert db.get(User, "student")
        assert row.token_hash == invitations.digest(world.token)
        assert row.token_hash != world.token


def test_smtp_message_and_stale_claim_recovery(world, monkeypatch):
    messages = []
    class SMTP(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"220 local-test\r\n")
            while line := self.rfile.readline():
                if line.upper().startswith(b"DATA"):
                    self.wfile.write(b"354 send message\r\n")
                    chunks = []
                    while (chunk := self.rfile.readline()) != b".\r\n":
                        if not chunk: return
                        chunks.append(chunk)
                    messages.append(BytesParser(policy=policy.default).parsebytes(b"".join(chunks)))
                    self.wfile.write(b"250 accepted\r\n")
                elif line.upper().startswith(b"QUIT"):
                    self.wfile.write(b"221 bye\r\n")
                    return
                else:
                    self.wfile.write(b"250 OK\r\n")
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), SMTP) as smtp:
        worker = threading.Thread(target=smtp.serve_forever)
        worker.start()
        try:
            monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
            monkeypatch.setenv("SMTP_PORT", str(smtp.server_address[1]))
            monkeypatch.setenv("SMTP_FROM", "attendance@example.test")
            monkeypatch.setenv("SMTP_SECURITY", "none")
            monkeypatch.setenv("DASHBOARD_APP_URL", "http://localhost:8501")
            with world.db() as db:
                row = db.get(invitations.AccountInvitation, "student")
                row.delivery_status = "sending"
                row.claimed_at = datetime.utcnow() - timedelta(minutes=3)
                db.commit()
            assert invitations.deliver_next()
            assert len(messages) == 1
            assert messages[0]["To"] == "student@example.edu"
            assert f"http://localhost:8501/setup-account#token={world.token}" in messages[0].get_body(preferencelist=("plain",)).get_content()
            with world.db() as db:
                assert db.get(invitations.AccountInvitation, "student").delivery_status == "sent"
            assert not invitations.deliver_next()
        finally:
            smtp.shutdown()
            worker.join()


def test_public_request_does_not_disclose_accounts_and_is_rate_limited(world):
    c = world.client
    known = c.post("/api/v1/auth/invitations/request", json={"email": "student@example.edu"})
    unknown = c.post("/api/v1/auth/invitations/request", json={"email": "unknown@example.edu"})
    assert known.json() == unknown.json()
    for _ in range(3):
        assert c.post("/api/v1/auth/invitations/request", json={"email": "unknown@example.edu"}).status_code == 200
    assert c.post("/api/v1/auth/invitations/request", json={"email": "unknown@example.edu"}).status_code == 429


def test_real_bulk_creates_queued_invitation_and_blocks_login(api):
    import uuid
    admin = _register(api, "admin")
    teacher = _register(api, "instructor")
    course = _make_course(api, admin, teacher)
    email = f"invite-{uuid.uuid4().hex}@example.edu"
    response = api.post("/api/v1/enrollments/bulk", headers=teacher["headers"], json={"course_id": course, "student_emails": [email], "create_accounts": True})
    assert response.status_code == 200, response.text
    assert response.json()["details"][0]["invitation_status"] == "queued"
    assert api.post("/api/v1/auth/login", json={"email": email, "password": "any-password"}).status_code == 403
    invalid = api.post("/api/v1/auth/invitations/complete", json={"token": "private-token", "password": "tiny"})
    assert invalid.status_code == 422
    assert "private-token" not in invalid.text and "tiny" not in invalid.text
