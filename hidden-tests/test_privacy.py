"""Inspect stored values after real workflows, not merely response field names."""
import json
import re
import subprocess
import sys
from datetime import timedelta

import pytest
from sqlalchemy import select, inspect
from harness import PASSWORD, ROOT, expect, image_b64, assert_private, utc_now
from inspection import privacy_findings

pytestmark = pytest.mark.specification


def test_passwords_are_bcrypt_with_documented_cost(world):
    actor = world.student
    row = world.service.rows("users", id=actor.id)[0]
    stored = row["hashed_password"]
    assert re.fullmatch(r"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}", stored)
    assert int(stored.split("$")[2]) >= 10
    assert_private(json.dumps(row, default=str), PASSWORD)


@pytest.mark.parametrize("route", ["/users/me", "/users/", "/devices/my-devices"])
def test_user_and_device_reads_never_return_password_material(world, route):
    actor = world.admin if route == "/users/" else world.student
    response = world.service.api("GET", route, actor)
    assert response.status_code == 200
    payload = response.json()
    def visit(item):
        if isinstance(item, dict):
            assert not {"password", "hashed_password", "refresh_token", "private_key"} & item.keys()
            for value in item.values():
                visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)
    visit(payload)
    assert_private(response.text, PASSWORD)


def test_validation_errors_do_not_echo_password_or_image(world):
    secret = "private-hidden-validation-" + "x" * 80
    response = world.service.api("POST", "/auth/register", json={"email": "bad", "password": secret, "full_name": "Test"})
    expect(response, 422)
    assert_private(response.text, secret)
    response = world.service.api("POST", "/users/me/face/enroll", world.student, json={"image": [secret]})
    expect(response, 422)
    assert_private(response.text, secret)


def test_enabled_json_logging_redacts_sensitive_values(world):
    """Exercise the actual configured logger, including ordinary format strings.

    Successful HTTP requests need not emit logs. A separate canary proves the
    logging filter actually ran rather than passing because a log was empty.
    """
    image = image_b64()
    marker = "Hidden-logging-canary-password-42"
    code = """import json, logging, sys
from app.telemetry import configure_privacy_logging, safe_log
data = json.load(sys.stdin)
logger = configure_privacy_logging('INFO')
logger.warning('password=%s image=%s', data['password'], data['image'])
safe_log(logger, logging.WARNING, 'hidden privacy canary', password=data['password'], image=data['image'])
"""
    env = {**world.service.runtime.base_env(), "PYTHONPATH": str(ROOT / "module3-face-recognition"),
           "JSON_LOGGING_ENABLED": "true"}
    result = subprocess.run([sys.executable, "-c", code], input=json.dumps({"password": marker, "image": image}),
                            text=True, capture_output=True, env=env, cwd=world.service.runtime.directory, timeout=15)
    assert result.returncode == 0, "Privacy logging probe did not execute"
    output = result.stdout + result.stderr
    assert_private(output, marker, image, image[80:240])
    events = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    assert len(events) >= 2 and "hidden privacy canary" in output


def test_main_schema_has_no_blob_or_raw_biometric_columns(world):
    inspector = inspect(world.service.engine)
    forbidden = {"image", "face_image", "image_data", "raw_image", "raw_embedding", "embedding", "landmarks", "frames"}
    findings = []
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            if column["name"].lower() in forbidden or any(value in str(column["type"]).lower() for value in ("blob", "bytea", "binary")):
                findings.append(table + "." + column["name"])
    assert not findings, "Raw/binary storage columns: " + ", ".join(findings)


@pytest.mark.native
def test_enrollment_and_checkin_store_only_templates_and_no_submitted_images(world, face):
    image = image_b64()
    world.enroll_face(image=image)
    meeting = world.session(require_liveness_check=True, require_face_match=True)
    record = expect(world.checkin(meeting, liveness_challenge_response=image), 201)
    assert record["liveness_passed"] is not None and record["face_match_passed"] is not None
    # Inspect every row/column, including JSON text in audit and motion tables.
    # This is owned temporary storage; no query ever targets the user's DB.
    forbidden = (image, image[80:240], base64_bytes(image), PASSWORD)
    findings = []
    with world.service.engine.connect() as connection:
        for name, table in world.service.metadata.tables.items():
            for index, row in enumerate(connection.execute(select(table)).mappings()):
                findings.extend(privacy_findings(dict(row), forbidden, f"{name}.row[{index}]"))
    assert not findings, "; ".join(findings)
    user = world.service.rows("users", id=world.student.id)[0]
    assert re.fullmatch(r"[0-9a-f]{64}", user["face_embedding_hash"])
    saved = world.service.rows("checkins", id=record["id"])[0]
    assert re.fullmatch(r"[0-9a-f]{64}", saved["face_embedding_hash"])
    # Never equate shape checking with encryption or cryptographic irreversibility.
    assert not privacy_findings(record, (image, image[80:240]))


def base64_bytes(value):
    import base64
    return base64.b64decode(value)


@pytest.mark.native
def test_service_logs_and_work_directory_do_not_persist_captures(world, face):
    image = image_b64()
    world.enroll_face(image=image)
    meeting = world.session(require_liveness_check=True)
    expect(world.checkin(meeting, liveness_challenge_response=image), 201)
    for service in (world.service, face):
        content = service.log_path.read_text(errors="replace")
        assert_private(content, image, image[80:240], PASSWORD, world.student.access, world.student.refresh)
    found = [str(path.relative_to(world.service.runtime.directory))
             for path in world.service.runtime.directory.rglob("*")
             if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"}]
    assert not found, "Unexpected capture files: " + ", ".join(found)


def test_audit_is_append_only_over_http(world):
    actor = world.student
    rows = expect(world.service.api("GET", "/audit/", world.admin, params={"user_id": actor.id}), 200)["items"]
    assert rows
    identity = rows[0]["id"]
    before = world.service.rows("audit_logs", id=identity)[0]
    for method, path in (("PATCH", "/audit/" + identity), ("DELETE", "/audit/" + identity), ("POST", "/audit/")):
        response = world.service.api(method, path, world.admin, json={"details": "tampered"})
        assert response.status_code in (404, 405)
    assert world.service.rows("audit_logs", id=identity)[0] == before


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_audit_is_append_only_for_direct_database_writes(world, operation):
    """A privileged DB inspection goes beyond the ORM's event hooks.

    Roll back even when the DB permits the forbidden statement; report that
    missing protection without damaging evidence for later tests.
    """
    actor = world.student
    row = world.service.rows("audit_logs", user_id=actor.id)[0]
    table = world.service.table("audit_logs")
    statement = (table.update().values(success=False) if operation == "update" else table.delete()).where(table.c.id == row["id"])
    allowed = False
    with world.service.engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(statement)
            allowed = True
        except Exception as exc:
            # A lock/connection outage is inconclusive, not an immutability pass.
            from sqlalchemy.exc import DBAPIError
            if not isinstance(exc, DBAPIError):
                raise
            message = str(exc.orig).lower()
            assert any(term in message for term in ("immutable", "append-only", "permission", "not authorized", "denied")), "Database error did not establish append-only protection"
        finally:
            transaction.rollback()
    assert world.service.rows("audit_logs", id=row["id"])[0] == row
    assert not allowed, f"Direct SQL {operation.upper()} was allowed on audit_logs"


def test_checkin_has_thirty_day_retention_deadline(world):
    meeting = world.session()
    record = expect(world.checkin(meeting), 201)
    row = world.service.rows("checkins", id=record["id"])[0]
    assert row["scheduled_deletion_at"] is not None, "No retention deadline assigned to check-in"
    delta = row["scheduled_deletion_at"] - row["checked_in_at"]
    assert timedelta(days=29, hours=23) <= delta <= timedelta(days=30, hours=1)


def test_deletion_deadline_is_idempotent_and_cancel_requires_password(world):
    actor = world.student
    route = "/users/me/deletion-request"
    expect(world.service.api("POST", route, actor, json={"password": "wrong"}), 403)
    assert world.service.rows("users", id=actor.id)[0]["scheduled_deletion_at"] is None
    first = expect(world.service.api("POST", route, actor, json={"password": PASSWORD}), 200)
    second = expect(world.service.api("POST", route, actor, json={"password": PASSWORD}), 200)
    assert first == second and first["scheduled_deletion_at"] is not None
    expect(world.service.api("DELETE", route, actor, json={"password": "wrong"}), 403)
    expect(world.service.api("DELETE", route, actor, json={"password": PASSWORD}), 200)
    assert world.service.rows("users", id=actor.id)[0]["scheduled_deletion_at"] is None


def test_due_deletion_removes_personal_records_but_preserves_audit(world):
    actor = world.student
    other = world.user()
    meeting = world.session()
    expect(world.checkin(meeting), 201)
    route = "/users/me/deletion-request"
    expect(world.service.api("POST", route, actor, json={"password": PASSWORD}), 200)
    before = {row["id"] for row in world.service.rows("audit_logs", user_id=actor.id)}
    world.service.update("users", actor.id, scheduled_deletion_at=utc_now().replace(tzinfo=None) - timedelta(seconds=1))
    # Invoke the actual scheduled job immediately in a separate package namespace.
    command = "from app.main import app; from app.data_deletion import purge_due_students; purge_due_students()"
    env = {**world.service.env, "PYTHONPATH": str(ROOT / "module2-backend")}
    result = subprocess.run([sys.executable, "-c", command], cwd=world.service.runtime.directory,
                            env=env, capture_output=True, timeout=30)
    assert result.returncode == 0, "Scheduled deletion worker failed (output suppressed to avoid PII)"
    deleted = world.service.rows("users", id=actor.id)[0]
    assert deleted["is_active"] is False and deleted["face_embedding_hash"] is None
    assert deleted["email"].endswith("@deleted.invalid") and deleted["full_name"] == "Deleted student"
    for table, key in (("checkins", "student_id"), ("enrollments", "student_id"), ("devices", "user_id"), ("motion_challenges", "user_id")):
        assert not world.service.rows(table, **{key: actor.id})
    assert before <= {row["id"] for row in world.service.rows("audit_logs", user_id=actor.id)}
    expect(world.service.api("GET", "/users/me", actor), 401)
    expect(world.service.api("GET", "/users/me", other), 200)


def test_audit_details_and_error_logs_never_store_passwords(world):
    actor = world.student
    wrong = "Hidden-wrong-password-DO-NOT-STORE"
    expect(world.service.api("POST", "/auth/login", json={"email": actor.email, "password": wrong}), 401)
    rows = world.service.rows("audit_logs", user_id=actor.id)
    assert any(row["action"] == "login_failed" for row in rows)
    assert_private(json.dumps(rows, default=str), PASSWORD, wrong, actor.access, actor.refresh)

