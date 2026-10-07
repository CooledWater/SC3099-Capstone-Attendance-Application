"""Dashboard cookie isolation against a disposable SQLite database."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

_temp = tempfile.TemporaryDirectory(prefix="saiv-dashboard-auth-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_temp.name) / "test.db")
os.environ["JWT_SECRET"] = "dashboard-isolation-test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

from fastapi.testclient import TestClient
from jose import jwt
from app.main import app
from app.auth import ALGORITHM, JWT_SECRET, create_refresh_token
from app.database import SessionLocal
from app.models import User

SAIV = "/api/v1/auth"
DASH = SAIV + "/dashboard"


@pytest.fixture
def client():
    with TestClient(app) as browser:
        yield browser


def account(client, role="student"):
    credentials = {"email": f"{uuid.uuid4()}@example.com", "password": "SecurePassword123!"}
    response = client.post(SAIV + "/register", json={**credentials, "full_name": "Test User", "role": role})
    assert response.status_code == 201, response.text
    return credentials, response.json()["id"]


def identity(response):
    assert response.status_code == 200, response.text
    return jwt.decode(response.json()["access_token"], JWT_SECRET, algorithms=[ALGORITHM])["user_id"]


@pytest.mark.parametrize("role", ["student", "ta", "instructor", "admin"])
def test_dashboard_login_does_not_replace_saiv(client, role):
    student, sid = account(client)
    staff, did = account(client, role)
    assert identity(client.post(SAIV + "/login", json=student)) == sid
    original = client.cookies.get("saiv_refresh_token")
    response = client.post(DASH + "/login", json=staff)
    assert identity(response) == did
    cookie = response.headers["set-cookie"].lower()
    assert "saiv_dashboard_refresh_token=" in cookie
    assert "path=/api/v1/auth/dashboard" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.cookies.get("saiv_refresh_token") == original
    assert identity(client.post(SAIV + "/refresh")) == sid
    assert identity(client.post(DASH + "/refresh")) == did


def test_student_bridge_creates_dashboard_session_only(client):
    student, sid = account(client)
    client.post(SAIV + "/login", json=student)
    original = client.cookies.get("saiv_refresh_token")
    assert identity(client.post(DASH + "/student-session")) == sid
    assert client.cookies.get("saiv_refresh_token") == original
    assert identity(client.post(DASH + "/refresh")) == sid


@pytest.mark.parametrize("role", ["ta", "instructor", "admin"])
def test_staff_cannot_automatically_enter_dashboard(client, role):
    staff, _ = account(client, role)
    client.post(SAIV + "/login", json=staff)
    response = client.post(DASH + "/student-session")
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("role", ["student", "instructor"])
def test_dashboard_session_cannot_restore_saiv(client, role):
    user, _ = account(client, role)
    login = client.post(DASH + "/login", json=user)
    assert client.post(SAIV + "/refresh").status_code == 401
    # Even moving a dashboard token into the legacy cookie/body cannot cross apps.
    token = login.json()["refresh_token"]
    client.cookies.set("saiv_refresh_token", token, path=SAIV)
    assert client.post(SAIV + "/refresh").status_code == 401
    assert client.post(SAIV + "/refresh", json={"refresh_token": token}).status_code == 401


@pytest.mark.parametrize("logout_app", [SAIV, DASH])
def test_logout_only_clears_its_own_cookie(client, logout_app):
    student, sid = account(client)
    instructor, did = account(client, "instructor")
    client.post(SAIV + "/login", json=student)
    client.post(DASH + "/login", json=instructor)
    assert client.post(logout_app + "/logout").status_code == 200
    assert client.post(logout_app + "/refresh").status_code == 401
    other, uid = (DASH, did) if logout_app == SAIV else (SAIV, sid)
    assert identity(client.post(other + "/refresh")) == uid


def test_dashboard_refresh_does_not_fall_back_to_student_cookie(client):
    student, _ = account(client)
    login = client.post(SAIV + "/login", json=student)
    assert client.post(DASH + "/refresh").status_code == 401
    assert client.post(DASH + "/refresh", json={"refresh_token": login.json()["refresh_token"]}).status_code == 401


@pytest.mark.parametrize("state", ["inactive", "role_changed", "expired", "invalid", "access_token"])
def test_bridge_rejects_invalid_or_ineligible_session(client, state):
    student, sid = account(client)
    login = client.post(SAIV + "/login", json=student)
    token = login.json()["refresh_token"]
    if state in ("inactive", "role_changed"):
        with SessionLocal() as db:
            user = db.get(User, sid)
            if state == "inactive":
                user.is_active = False
            else:
                user.role = "instructor"
            db.commit()
    elif state == "expired":
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        payload["exp"] = 1
        token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    elif state == "invalid":
        token = "invalid-token"
    else:
        token = login.json()["access_token"]
    client.cookies.clear()
    client.cookies.set("saiv_refresh_token", token, path=SAIV)
    response = client.post(DASH + "/student-session")
    assert response.status_code in (401, 403)
    assert "set-cookie" not in response.headers


def test_existing_unscoped_student_cookie_remains_compatible(client):
    student, sid = account(client)
    payload = jwt.decode(create_refresh_token(sid, "student"), JWT_SECRET, algorithms=[ALGORITHM])
    payload.pop("session_app")
    client.cookies.set("saiv_refresh_token", jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM), path=SAIV)
    assert identity(client.post(DASH + "/student-session")) == sid
    assert identity(client.post(SAIV + "/refresh")) == sid


def test_dashboard_rejects_wrong_credentials(client):
    student, _ = account(client)
    response = client.post(DASH + "/login", json={**student, "password": "wrong-password"})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
