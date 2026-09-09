"""Backward-compatible HttpOnly refresh-cookie contract tests."""

import os
import uuid

import httpx
import pytest


@pytest.fixture
def cookie_client():
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        yield client


@pytest.fixture
def cookie_test_student(cookie_client):
    student = {
        "email": f"cookie-test-{uuid.uuid4()}@example.com",
        "password": "SecurePassword123!",
        "full_name": "Cookie Test Student",
        "role": "student",
    }
    response = cookie_client.post("/api/v1/auth/register", json=student)
    assert response.status_code == 201, response.text
    return student


def test_login_sets_httponly_refresh_cookie(cookie_client, cookie_test_student):
    response = cookie_client.post("/api/v1/auth/login", json={
        "email": cookie_test_student["email"],
        "password": cookie_test_student["password"]
    })

    assert response.status_code == 200
    assert "refresh_token" in response.json()
    cookie = response.headers.get("set-cookie", "").lower()
    assert "saiv_refresh_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/v1/auth" in cookie


def test_refresh_accepts_cookie_without_json_body(cookie_client, cookie_test_student):
    login = cookie_client.post("/api/v1/auth/login", json={
        "email": cookie_test_student["email"],
        "password": cookie_test_student["password"]
    })
    assert login.status_code == 200

    response = cookie_client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_refresh_still_accepts_json_body(cookie_client, cookie_test_student):
    login = cookie_client.post("/api/v1/auth/login", json={
        "email": cookie_test_student["email"],
        "password": cookie_test_student["password"]
    })
    refresh_token = login.json()["refresh_token"]

    response = cookie_client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })

    assert response.status_code == 200
    assert "refresh_token" in response.json()


def test_logout_expires_refresh_cookie(cookie_client, cookie_test_student):
    login = cookie_client.post("/api/v1/auth/login", json={
        "email": cookie_test_student["email"],
        "password": cookie_test_student["password"]
    })
    assert login.status_code == 200

    response = cookie_client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}
    cookie = response.headers.get("set-cookie", "").lower()
    assert "saiv_refresh_token=" in cookie
    assert "max-age=0" in cookie

    refresh = cookie_client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 401
