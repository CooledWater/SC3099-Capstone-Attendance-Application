"""HTTP harness plus explicitly privileged inspection of owned temporary storage.

No application imports in the pytest process: M2 and M3 both have an ``app``
package. No production URL or root .env value is used as a test target.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import MetaData, create_engine, select

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PASSWORD = "HiddenAssessment-9p!"
JWT_SECRET = "disposable-hidden-suite-signing-secret-" + uuid.uuid4().hex
VENUE = (1.3483, 103.6831)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def expect(response, status):
    assert response.status_code == status, f"{response.request.method} {response.request.url.path}: expected {status}, got {response.status_code}"
    return response.json() if response.content else None


def bounded_score(value):
    assert type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def assert_private(text, *values):
    for value in values:
        if value and str(value) in text:
            raise AssertionError("Sensitive submitted value was exposed (value redacted)")


def image_b64(name="obama.jpg"):
    return base64.b64encode((ROOT / "sample_images" / name).read_bytes()).decode("ascii")


def png_b64(color=(20, 150, 20), size=(160, 160)):
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def sequence_image(name="obama.jpg"):
    from PIL import Image
    with Image.open(ROOT / "sample_images" / name) as source:
        source.thumbnail((480, 480))
        stream = io.BytesIO()
        source.convert("RGB").save(stream, format="JPEG", quality=70)
    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
    assert len(encoded) <= 100_000
    return encoded


def frames(image, count=20):
    return [{"image": image, "timestamp_ms": i * 80} for i in range(count)]


@dataclass
class Actor:
    id: str
    email: str
    role: str
    access: str
    refresh: str

    @property
    def headers(self):
        return {"Authorization": "Bearer " + self.access}


class Service:
    def __init__(self, runtime, name, port, env):
        self.runtime, self.name, self.env = runtime, name, env
        self.url = f"http://127.0.0.1:{port}"
        self.log_path = runtime.directory / (name + ".log")
        self.log = self.log_path.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, str(HERE / "service_runner.py"), "face" if name == "face" else "backend", str(port)],
            cwd=runtime.directory, env=env, stdout=self.log, stderr=subprocess.STDOUT,
        )
        self.client = httpx.Client(base_url=self.url, timeout=60, trust_env=False,
                                   limits=httpx.Limits(max_connections=120, max_keepalive_connections=120))
        self.admin = None
        self.engine = None
        self.metadata = None
        runtime.services.append(self)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                pytest.fail(f"{name} exited during startup; inspect {self.log_path}")
            try:
                if self.client.get("/health", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(.1)
        else:
            pytest.fail(f"{name} did not become healthy; inspect {self.log_path}")
        if name != "face":
            self.engine = create_engine(env["DATABASE_URL"])
            self.metadata = MetaData()
            self.metadata.reflect(bind=self.engine)
            self.admin = self.login("hidden-admin@example.org")

    def request(self, method, path, actor=None, **kwargs):
        headers = {**(actor.headers if actor else {}), **kwargs.pop("headers", {})}
        # Cookies are supplied explicitly in cookie-specific tests. Do not let a
        # previous login silently authenticate or affect another test's request.
        request = self.client.build_request(method, path, headers=headers, **kwargs)
        if "Cookie" not in headers:
            request.headers.pop("cookie", None)
        return self.client.send(request)

    def api(self, method, path, actor=None, **kwargs):
        return self.request(method, "/api/v1" + path, actor, **kwargs)

    def login(self, email, password=PASSWORD, dashboard=False):
        route = "/auth/dashboard/login" if dashboard else "/auth/login"
        body = expect(self.api("POST", route, json={"email": email, "password": password}), 200)
        user = body["user"]
        return Actor(user["id"], email, user["role"], body["access_token"], body["refresh_token"])

    def table(self, name):
        return self.metadata.tables[name]

    def rows(self, name, **filters):
        table = self.table(name)
        statement = select(table)
        for key, value in filters.items():
            statement = statement.where(table.c[key] == value)
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement).mappings()]

    def update(self, name, identity, **values):
        table = self.table(name)
        with self.engine.begin() as connection:
            changed = connection.execute(table.update().where(table.c.id == identity).values(**values))
            assert changed.rowcount == 1

    def close(self):
        self.client.close()
        if self.engine is not None:
            self.engine.dispose()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log.close()


class Runtime:
    def __init__(self, directory, config):
        self.directory, self.config = directory, config
        self.services, self.backends = [], {}
        self.face_service = None
        self.face_port = free_port()
        self.redis_process = None
        self.redis_port = None
        self.redis_log = None

    def redis(self):
        if self.redis_process is not None:
            return self.redis_port
        executable = self.config.getoption("--redis-server") or shutil.which("redis-server")
        if not executable:
            pytest.skip("Real Redis unavailable: install redis-server or pass --redis-server=/path/to/redis-server")
        self.redis_port = free_port()
        self.redis_log = (self.directory / "redis.log").open("wb")
        self.redis_process = subprocess.Popen(
            [executable, "--bind", "127.0.0.1", "--port", str(self.redis_port),
             "--save", "", "--appendonly", "no", "--dir", str(self.directory)],
            stdout=self.redis_log, stderr=subprocess.STDOUT,
        )
        import redis
        client = redis.Redis(host="127.0.0.1", port=self.redis_port, socket_timeout=1)
        for _ in range(100):
            if self.redis_process.poll() is not None:
                pytest.fail(f"Redis exited; inspect {self.directory / 'redis.log'}")
            try:
                if client.ping():
                    client.close()
                    return self.redis_port
            except redis.RedisError:
                time.sleep(.05)
        pytest.fail("Disposable Redis did not start")

    def base_env(self):
        env = os.environ.copy()
        env.update(SAIV_HIDDEN_OWNED_PROCESS="1", SAIV_HIDDEN_PASSWORD=PASSWORD,
                   PYTHONDONTWRITEBYTECODE="1", TELEMETRY_ENABLED="false", JSON_LOGGING_ENABLED="false",
                   JWT_SECRET=JWT_SECRET, SECRET_KEY=JWT_SECRET, CORS_ORIGINS="http://localhost:3000,http://localhost:8501",
                   REFRESH_COOKIE_SECURE="false", VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="", VAPID_SUBJECT="",
                   CHECKIN_DIAGNOSTICS_ENABLED="false", CHECKIN_DIAGNOSTIC_SESSION_IDS="",
                   MPLCONFIGDIR=str(self.directory / "matplotlib"), PAD_MODE="enforce", PAD_THRESHOLD="0.75",
                   FACE_MATCH_THRESHOLD="0.70", LIVENESS_THRESHOLD="0.85")
        env['FORWARDED_ALLOW_IPS'] = ''
        env.pop("PYTHONPATH", None)
        return env

    def backend(self, strict=False):
        key = "strict" if strict else "compat"
        if key not in self.backends:
            env = self.base_env()
            # Optional PostgreSQL is accepted only inside the isolated Compose
            # network. No arbitrary DB URL, live backend URL or .env is accepted.
            if self.config.getoption("--postgres"):
                if os.environ.get("SAIV_HIDDEN_COMPOSE") != "1":
                    raise pytest.UsageError("--postgres must run inside hidden-tests/compose.yml")
                database = "hidden_strict" if strict else "hidden_compat"
                env["DATABASE_URL"] = f"postgresql://hidden:hidden-disposable-password@hidden-db:5432/{database}"
            else:
                env["DATABASE_URL"] = "sqlite:///" + str(self.directory / (key + ".sqlite3"))
            env["STRICT_SECURITY_MODE"] = str(strict).lower()
            env["REDIS_URL"] = f"redis://127.0.0.1:{self.redis()}/{'1' if strict else '0'}"
            env["FACE_SERVICE_URL"] = f"http://127.0.0.1:{self.face_port}"
            self.backends[key] = Service(self, key, free_port(), env)
        return self.backends[key]

    def face(self):
        if self.config.getoption("--backend-only"):
            pytest.skip("Native face tests explicitly disabled by --backend-only")
        if self.face_service is None:
            self.face_service = Service(self, "face", self.face_port, self.base_env())
        return self.face_service

    def clear_limits(self, service):
        if service.name in ("compat", "strict"):
            import redis
            with redis.Redis.from_url(service.env["REDIS_URL"]) as client:
                client.flushdb()  # Only the selected DB of the Redis process this harness owns.

    def close(self):
        for service in reversed(self.services):
            service.close()
        if self.redis_process is not None:
            self.redis_process.terminate()
            self.redis_process.wait(timeout=10)
            self.redis_log.close()


class World:
    def __init__(self, service):
        self.service = service
        self._student = None

    @property
    def admin(self):
        return self.service.admin

    @property
    def student(self):
        if self._student is None:
            self._student = self.user()
        return self._student

    def user(self, role="student", consent=True):
        email = "hidden-" + uuid.uuid4().hex + "@example.org"
        body = expect(self.service.api("POST", "/admin/users/bulk", self.admin, json={"users": [
            {"email": email, "password": PASSWORD, "full_name": "Hidden " + role, "role": role}]}), 201)
        assert body["created"] == 1 and body["failed"] == 0
        actor = self.service.login(email)
        if consent:
            expect(self.service.api("PUT", "/users/me", actor, json={"camera_consent": True, "geolocation_consent": True}), 200)
        return actor

    def course(self, instructor=None, **overrides):
        payload = dict(code="HT" + uuid.uuid4().hex[:10], name="Hidden assessment", semester="test",
                       instructor_id=(instructor or self.admin).id, venue_latitude=VENUE[0],
                       venue_longitude=VENUE[1], geofence_radius_meters=100, risk_threshold=.5)
        return expect(self.service.api("POST", "/courses/", self.admin, json={**payload, **overrides}), 201)

    def enroll(self, course, actor=None):
        return expect(self.service.api("POST", "/enrollments/", self.admin,
                                      json={"course_id": course["id"], "student_id": (actor or self.student).id}), 201)

    def session(self, course=None, actor=None, **overrides):
        course = course or self.course()
        actor = actor or self.student
        self.enroll(course, actor)
        now = utc_now()
        payload = dict(course_id=course["id"], name="Hidden " + uuid.uuid4().hex[:10],
                       scheduled_start=iso(now + timedelta(minutes=1)), scheduled_end=iso(now + timedelta(hours=1)),
                       checkin_opens_at=iso(now - timedelta(minutes=1)), checkin_closes_at=iso(now + timedelta(hours=1)),
                       require_liveness_check=False, require_face_match=False, require_motion_check=False)
        meeting = expect(self.service.api("POST", "/sessions/", self.admin, json={**payload, **overrides}), 201)
        expect(self.service.api("PATCH", "/sessions/" + meeting["id"], self.admin, json={"status": "active"}), 200)
        return meeting

    def payload(self, meeting, **overrides):
        return {"session_id": meeting["id"], "latitude": VENUE[0], "longitude": VENUE[1],
                "location_accuracy_meters": 10, "device_fingerprint": "unknown-" + uuid.uuid4().hex, **overrides}

    def checkin(self, meeting, actor=None, **overrides):
        return self.service.api("POST", "/checkins/", actor or self.student, json=self.payload(meeting, **overrides))

    def enroll_face(self, actor=None, image=None):
        self.service.runtime.face()
        actor = actor or self.student
        return expect(self.service.api("POST", "/users/me/face/enroll", actor,
                                      json={"image": image or image_b64()}), 200)


def new_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()
    der = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return private, pem, hashlib.sha256(der).hexdigest()


def sign(private, challenge):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    r, s = utils.decode_dss_signature(private.sign(challenge.encode(), ec.ECDSA(hashes.SHA256())))
    return base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode()


def register_device(world, actor=None, identity=None):
    actor = actor or world.student
    identity = identity or new_key()
    payload = {"device_fingerprint": identity[2], "public_key": identity[1]}
    challenge = expect(world.service.api("POST", "/devices/registration-challenges", actor, json=payload), 201)
    device = expect(world.service.api("POST", "/devices/", actor, json={**payload,
        "registration_challenge_id": challenge["challenge_id"], "registration_signature": sign(identity[0], challenge["challenge"])}), 201)
    return identity, device


def device_proof(world, meeting, identity, actor=None):
    body = expect(world.service.api("POST", "/devices/challenges", actor or world.student,
        json={"session_id": meeting["id"], "device_fingerprint": identity[2]}), 201)
    return {"device_fingerprint": identity[2], "device_challenge_id": body["challenge_id"],
            "device_signature": sign(identity[0], body["challenge"])}

