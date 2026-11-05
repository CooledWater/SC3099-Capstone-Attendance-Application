"""Seven asserting workloads. Account provisioning is outside the timed window."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import math
import threading
import time
import uuid
import pytest
from harness import World, PASSWORD, expect, image_b64

pytestmark = [pytest.mark.stress, pytest.mark.specification]


def burst(call, count=100):
    gate = threading.Barrier(count)
    def invoke(index):
        gate.wait(timeout=30)
        start = time.monotonic()
        try:
            response = call(index)
            # Fully consume the response before stopping the clock.
            response.read()
            return response.status_code, time.monotonic() - start, response
        except Exception as exc:
            return type(exc).__name__, time.monotonic() - start, None
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(invoke, range(count)))


def check_burst(rows, statuses, target, record_property):
    counts = {str(value): sum(row[0] == value for row in rows) for value in set(row[0] for row in rows)}
    durations = sorted(row[1] for row in rows)
    p95 = durations[math.ceil(.95 * len(durations)) - 1]
    record_property("requests", len(rows)); record_property("p95_seconds", round(p95, 4))
    record_property("status_counts", str(counts))
    assert all(row[0] in statuses for row in rows), f"Unexpected concurrent outcomes: {counts}"
    assert p95 < target, f"p95={p95:.3f}s exceeds local target {target:.3f}s; statuses={counts}"


@pytest.fixture(scope="module")
def population(runtime):
    world = World(runtime.backend())
    batch = [{"email": f"load-{uuid.uuid4().hex}@example.org", "password": PASSWORD,
              "full_name": f"Load student {i}", "role": "student"} for i in range(100)]
    data = expect(world.service.api("POST", "/admin/users/bulk", world.admin, json={"users": batch}), 201)
    assert data["created"] == 100 and data["failed"] == 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        actors = list(pool.map(lambda row: world.service.login(row["email"]), batch))
    for actor in actors:
        expect(world.service.api("PUT", "/users/me", actor, json={"camera_consent": True, "geolocation_consent": True}), 200)
    return world, actors


def test_one_hundred_distinct_profile_reads(population, pytestconfig, record_property):
    world, actors = population
    rows = burst(lambda i: world.service.api("GET", "/users/me", actors[i]))
    for index, row in enumerate(rows):
        if row[0] == 200:
            assert row[2].json()["id"] == actors[index].id
    check_burst(rows, {200}, pytestconfig.getoption("--stress-p95"), record_property)


def test_one_hundred_real_password_logins(population, pytestconfig, record_property):
    world, actors = population
    rows = burst(lambda i: world.service.api("POST", "/auth/login", json={"email": actors[i].email, "password": PASSWORD}))
    tokens = [row[2].json()["refresh_token"] for row in rows if row[0] == 200]
    assert len(tokens) == len(set(tokens))
    check_burst(rows, {200}, pytestconfig.getoption("--stress-p95"), record_property)


def prepare_session(world, actors, **policy):
    course = world.course()
    meeting = world.session(course, actors[0], **policy)
    for actor in actors[1:]:
        world.enroll(course, actor)
    return meeting


def test_one_hundred_checkins_preserve_records_and_audit(population, pytestconfig, record_property):
    world, actors = population
    meeting = prepare_session(world, actors)
    rows = burst(lambda i: world.checkin(meeting, actors[i]))
    stored = world.service.rows("checkins", session_id=meeting["id"])
    assert len(stored) == 100 and len({row["student_id"] for row in stored}) == 100
    for record in stored:
        actions = [item["action"] for item in world.service.rows("audit_logs", resource_id=record["id"])]
        assert sorted(actions) == ["checkin_attempted", "checkin_flagged"]
    check_burst(rows, {201}, pytestconfig.getoption("--stress-p95"), record_property)


@pytest.mark.native
def test_one_hundred_native_face_comparisons(face, population, pytestconfig, record_property):
    image = image_b64()
    reference = expect(face.request("POST", "/face/enroll", json={"user_id": "hidden-load-reference", "image": image, "camera_consent": True}), 201)["face_template_hash"]
    rows = burst(lambda _: face.request("POST", "/face/verify", json={"image": image, "reference_template_hash": reference}))
    assert all(row[2].json()["match_passed"] is True for row in rows if row[0] == 200)
    check_burst(rows, {200}, pytestconfig.getoption("--stress-p95"), record_property)


@pytest.mark.native
def test_one_hundred_full_native_biometric_checkins(population, face, pytestconfig, record_property):
    world, actors = population
    image = image_b64()
    for actor in actors:
        world.enroll_face(actor, image)
    meeting = prepare_session(world, actors, require_liveness_check=True, require_face_match=True)
    rows = burst(lambda i: world.checkin(meeting, actors[i], liveness_challenge_response=image))
    stored = world.service.rows("checkins", session_id=meeting["id"])
    assert len(stored) == 100 and len({record["student_id"] for record in stored}) == 100
    assert all(record["liveness_passed"] is not None and record["face_match_passed"] is not None for record in stored), "Biometric workload silently bypassed native inference"
    # A sample photograph is inference load, not a labelled live presentation.
    # Rejected/flagged records are legitimate; absent model results are not.
    check_burst(rows, {201}, pytestconfig.getoption("--stress-p95"), record_property)


def test_one_hundred_duplicate_submissions_have_one_winner(population, record_property):
    world, actors = population
    meeting = world.session(actor=actors[0])
    payload = world.payload(meeting)
    rows = burst(lambda _: world.service.api("POST", "/checkins/", actors[0], json=payload))
    statuses = [row[0] for row in rows]
    record_property("status_counts", str({str(code): statuses.count(code) for code in set(statuses)}))
    assert statuses.count(201) == 1 and statuses.count(400) == 99
    assert len(world.service.rows("checkins", session_id=meeting["id"])) == 1


def test_health_remains_available_during_and_after_load(population, record_property):
    world, actors = population
    def mixed(index):
        return world.service.request("GET", "/health") if index % 5 == 0 else world.service.api("GET", "/users/me", actors[index])
    rows = burst(mixed)
    assert all(row[0] == 200 for row in rows)
    health = [row for index, row in enumerate(rows) if index % 5 == 0]
    check_burst(health, {200}, .5, record_property)
    expect(world.service.request("GET", "/db-health"), 200)
    expect(world.service.request("GET", "/health"), 200)

