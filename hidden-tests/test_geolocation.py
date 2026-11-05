"""Geofence boundaries, invalid numbers and an explicit impossible-travel probe."""
import json
import math
from datetime import timedelta
import pytest
from harness import VENUE, expect, register_device, device_proof, utc_now

pytestmark = pytest.mark.specification


@pytest.mark.parametrize("field,value", [("latitude", 90.001), ("latitude", -90.001),
    ("longitude", 180.001), ("longitude", -180.001), ("latitude", float("nan")),
    ("longitude", float("inf")), ("longitude", float("-inf")), ("location_accuracy_meters", -1),
    ("location_accuracy_meters", float("nan")), ("location_accuracy_meters", float("inf"))])
def test_invalid_gps_never_creates_attendance(world, field, value):
    meeting = world.session()
    payload = world.payload(meeting, **{field: value})
    response = world.service.api("POST", "/checkins/", world.student,
                                content=json.dumps(payload), headers={"Content-Type": "application/json"})
    expect(response, 422)
    assert not world.service.rows("checkins", session_id=meeting["id"])


@pytest.mark.parametrize("meters,expected_status", [(0, "approved"), (99, "approved"),
    (101, "flagged"), (199, "flagged"), (201, "rejected"), (10000, "rejected")])
def test_geofence_boundaries_with_trusted_device(world, meters, expected_status):
    meeting = world.session()
    identity, _ = register_device(world)
    proof = device_proof(world, meeting, identity)
    latitude = VENUE[0] + math.degrees(meters / 6_371_000)
    record = expect(world.checkin(meeting, latitude=latitude, **proof), 201)
    assert record["status"] == expected_status
    assert abs(record["distance_from_venue_meters"] - meters) < .1
    assert 0 <= record["risk_score"] <= 1


def test_effective_session_venue_overrides_course_defaults(world):
    meeting = world.session(venue_latitude=VENUE[0] + .02, venue_longitude=VENUE[1])
    record = expect(world.checkin(meeting), 201)
    assert record["status"] == "rejected" and record["distance_from_venue_meters"] > 2000


def test_low_accuracy_is_visible_in_risk_evidence(world):
    meeting = world.session()
    record = expect(world.checkin(meeting, location_accuracy_meters=5000), 201)
    factors = world.service.rows("checkins", id=record["id"])[0]["risk_factors"]
    if isinstance(factors, str):
        factors = json.loads(factors)
    assert "geo_accuracy_low" in {factor.get("type", factor.get("signal_type")) for factor in factors}


@pytest.mark.interpretation
def test_impossible_travel_between_two_valid_venues_is_detected(world):
    """Very permissive physical bound: Singapore to London within one minute.

    The briefing names impossible travel but gives no speed threshold. Require
    its own signal so unrelated device flags cannot masquerade as GPS detection.
    """
    identity, _ = register_device(world)
    first = world.session()
    expect(world.checkin(first, **device_proof(world, first, identity)), 201)
    second = world.session(world.course(venue_latitude=51.5074, venue_longitude=-.1278))
    record = expect(world.checkin(second, latitude=51.5074, longitude=-.1278,
                                  **device_proof(world, second, identity)), 201)
    factors = world.service.rows("checkins", id=record["id"])[0]["risk_factors"] or "[]"
    if isinstance(factors, str):
        factors = json.loads(factors)
    assert "impossible_travel" in {factor.get("type", factor.get("signal_type")) for factor in factors}
    assert record["status"] in ("flagged", "rejected")

