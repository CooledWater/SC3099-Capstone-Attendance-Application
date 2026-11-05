"""JWT, authorization, injection, CORS, cookies and actual HTTP limit boundaries."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest
from jose import jwt
from harness import JWT_SECRET, PASSWORD, bounded_score, expect, assert_private, utc_now

pytestmark = pytest.mark.specification


@pytest.mark.parametrize("kind", ["expired", "wrong_signature", "none_algorithm", "wrong_type", "missing_user", "malformed"])
def test_access_token_validation(world, kind):
    actor = world.student
    payload = {"user_id": actor.id, "role": "admin", "type": "access", "exp": utc_now() + timedelta(hours=1)}
    secret = JWT_SECRET
    if kind == "expired":
        payload["exp"] = utc_now() - timedelta(seconds=10)
    elif kind == "wrong_signature":
        secret = "attacker-controlled-signing-key"
    elif kind == "wrong_type":
        payload["type"] = "refresh"
    elif kind == "missing_user":
        payload.pop("user_id")
    token = jwt.encode(payload, secret, algorithm="HS256")
    if kind == "none_algorithm":
        token = token.rsplit(".", 1)[0].replace("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0") + "."
    elif kind == "malformed":
        token = "not.a.valid.jwt"
    expect(world.service.api("GET", "/users/me", headers={"Authorization": "Bearer " + token}), 401)


def test_signed_role_claim_cannot_override_database_role(world):
    actor = world.student
    forged_role = jwt.encode({"user_id": actor.id, "role": "admin", "type": "access",
                             "exp": utc_now() + timedelta(hours=1)}, JWT_SECRET, algorithm="HS256")
    expect(world.service.api("GET", "/audit/", headers={"Authorization": "Bearer " + forged_role}), 403)


def test_token_lifetimes_and_password_absence(world):
    actor = world.student
    access = jwt.decode(actor.access, JWT_SECRET, algorithms=["HS256"])
    refresh = jwt.decode(actor.refresh, JWT_SECRET, algorithms=["HS256"])
    assert 3500 <= access["exp"] - utc_now().timestamp() <= 3600
    assert 604700 <= refresh["exp"] - utc_now().timestamp() <= 604800
    assert access["type"] == "access" and refresh["type"] == "refresh"
    for claims in (access, refresh):
        assert not {"password", "hashed_password", "face_embedding_hash", "image", "latitude", "longitude"} & claims.keys()


def test_deactivation_revokes_access_and_refresh(world):
    actor = world.student
    expect(world.service.api("PATCH", f"/users/{actor.id}", world.admin, json={"is_active": False}), 200)
    expect(world.service.api("GET", "/users/me", actor), 401)
    expect(world.service.api("POST", "/auth/refresh", json={"refresh_token": actor.refresh}), 401)


@pytest.mark.parametrize("role", ["student", "ta", "instructor"])
def test_non_admin_cannot_read_audit_or_bulk_create_accounts(world, role):
    actor = world.user(role)
    expect(world.service.api("GET", "/audit/", actor), 403)
    expect(world.service.api("POST", "/admin/users/bulk", actor, json={"users": [
        {"email": "unauthorized@example.org", "password": PASSWORD, "full_name": "Unauthorized"}]}), 403)
    assert not world.service.rows("users", email="unauthorized@example.org")


def test_profile_mass_assignment_cannot_change_role_trust_or_template(world):
    actor = world.student
    before = world.service.rows("users", id=actor.id)[0]
    response = world.service.api("PUT", "/users/me", actor, json={
        "role": "admin", "is_active": False, "face_enrolled": True,
        "face_embedding_hash": "a" * 64, "hashed_password": "attacker-value"})
    assert response.status_code in (200, 422)
    after = world.service.rows("users", id=actor.id)[0]
    for key in ("role", "is_active", "face_enrolled", "face_embedding_hash", "hashed_password"):
        assert after[key] == before[key], f"Profile mass assignment changed {key}"


def test_cross_student_and_unassigned_staff_cannot_read_or_review_checkins(world):
    instructor = world.user("instructor")
    meeting = world.session(world.course(instructor))
    record = expect(world.checkin(meeting), 201)
    assert record["status"] == "flagged"  # Unknown device is a deliberate setup precondition.
    for actor in (world.user(), world.user("instructor"), world.user("ta")):
        expect(world.service.api("GET", f"/checkins/{record['id']}", actor), 403)
        expect(world.service.api("POST", f"/checkins/{record['id']}/review", actor, json={"status": "approved"}), 403)
    saved = world.service.rows("checkins", id=record["id"])[0]
    assert saved["status"] == "flagged" and saved["reviewed_by_id"] is None


def test_student_cannot_override_history_identity_filter(world):
    meeting = world.session()
    record = expect(world.checkin(meeting), 201)
    other = world.user()
    data = expect(world.service.api("GET", "/checkins/my-checkins", other,
                                    params={"student_id": world.student.id, "session_id": meeting["id"]}), 200)
    rows = data if isinstance(data, list) else data["items"]
    assert record["id"] not in {row["id"] for row in rows}


@pytest.mark.parametrize("payload", ["' OR 1=1 --", "'; DROP TABLE users; --", "%_\\' OR 'x'='x"])
def test_sql_injection_does_not_expand_admin_search(world, payload):
    data = expect(world.service.api("GET", "/users/", world.admin, params={"search": payload}), 200)
    assert data["total"] == 0 and data["items"] == []
    expect(world.service.api("GET", "/users/me", world.student), 200)


def test_stored_xss_is_escaped_and_csv_formula_is_neutralized(world):
    actor = world.student
    expect(world.service.api("PUT", "/users/me", actor, json={"full_name": "<script>alert('hidden')</script>"}), 200)
    data = expect(world.service.api("GET", "/users/me", actor), 200)
    assert "<script>" not in data["full_name"]
    expect(world.service.api("PUT", "/users/me", actor, json={"full_name": "=HYPERLINK(\"https://example.org\")"}), 200)
    meeting = world.session()
    expect(world.checkin(meeting), 201)
    response = world.service.api("GET", f"/export/session/{meeting['id']}", world.admin, params={"format": "csv"})
    assert response.status_code == 200
    import csv, io
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert rows and any(str(value).startswith("'=") for row in rows for value in row.values())


@pytest.mark.parametrize("origin,allowed", [("http://localhost:3000", True),
    ("https://attacker.example.org", False), ("http://localhost:3000.attacker.example.org", False), ("null", False)])
def test_cors_exact_origin_matching(world, origin, allowed):
    response = world.service.request("OPTIONS", "/api/v1/users/me", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    if allowed:
        assert response.status_code == 200 and response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in response.headers


def test_refresh_cookie_is_httponly_scoped_and_samesite(world):
    response = world.service.api("POST", "/auth/login", json={"email": world.student.email, "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/api/v1/auth" in cookie
    assert "max-age=604800" in cookie


@pytest.mark.parametrize("field", ["camera_consent", "geolocation_consent"])
def test_checkin_requires_each_consent(security_world, field):
    world = security_world
    meeting = world.session()
    expect(world.service.api("PUT", "/users/me", world.student, json={field: False}), 200)
    response = world.checkin(meeting)
    assert response.status_code == 403, f"{world.service.name}: check-in persisted after {field} withdrawal"
    assert not world.service.rows("checkins", session_id=meeting["id"])


def test_exact_login_ip_limit(security_world):
    world = security_world
    # No successful login setup in the measured bucket. A nonexistent account
    # avoids bcrypt cost while still being a real login attempt.
    statuses = []
    for i in range(61):
        response = world.service.api("POST", "/auth/login", json={"email": "nonexistent-limit@example.org", "password": PASSWORD})
        statuses.append(response.status_code)
    assert statuses[:60] == [401] * 60
    assert statuses[60] == 429, f"{world.service.name}: 61st login was not rate limited"
    assert int(response.headers["retry-after"]) > 0


@pytest.mark.interpretation
def test_forwarded_ip_cannot_bypass_login_limit(strict_world):
    # The app is run with its stock uvicorn proxy defaults. This probe exposes
    # deployment trust assumptions; the docs specify no trusted proxy topology.
    statuses = [strict_world.service.api("POST", "/auth/login", headers={"X-Forwarded-For": f"198.51.100.{i+1}"},
        json={"email": "nonexistent-forwarded@example.org", "password": PASSWORD}).status_code for i in range(61)]
    assert statuses[:60] == [401] * 60
    assert statuses[60] == 429, "Changing an unverified forwarded IP bypassed the login bucket"


def test_exact_registration_ip_limit(security_world):
    world = security_world
    import uuid
    statuses = [world.service.api("POST", "/auth/register", json={"email": f"limit-{uuid.uuid4().hex}@example.org",
                "password": PASSWORD, "full_name": "Limit", "role": "student"}).status_code for _ in range(11)]
    assert statuses[:10] == [201] * 10
    assert statuses[10] == 429, f"{world.service.name}: 11th registration was not rate limited"


def test_checkin_limit_counts_failed_attempts_per_user(security_world):
    world = security_world
    import uuid
    actor = world.student
    missing = {"id": str(uuid.uuid4())}
    statuses = [world.checkin(missing, actor).status_code for _ in range(11)]
    assert statuses[:10] == [404] * 10
    assert statuses[10] == 429, f"{world.service.name}: 11th check-in attempt was not rate limited"
    # Another authenticated student has an independent bucket.
    assert world.checkin(missing, world.user()).status_code == 404


def test_authenticated_api_limit_has_exact_user_boundary(security_world):
    world = security_world
    actor = world.student
    world.service.runtime.clear_limits(world.service)
    for _ in range(1000):
        expect(world.service.api("GET", "/users/me", actor), 200)
    response = world.service.api("GET", "/users/me", actor)
    assert response.status_code == 429, f"{world.service.name}: 1001st API request was not rate limited"
    assert int(response.headers["retry-after"]) > 0
    # Expire the owned Redis key instead of sleeping an hour.
    import hashlib, redis
    with redis.Redis.from_url(world.service.env["REDIS_URL"]) as store:
        key = "saiv:limit:api:" + hashlib.sha256(actor.id.encode()).hexdigest()
        assert 0 < store.ttl(key) <= 3600
        store.pexpire(key, 1)
        import time
        deadline = time.monotonic() + 1
        while store.exists(key) and time.monotonic() < deadline:
            time.sleep(.005)
    expect(world.service.api("GET", "/users/me", actor), 200)

