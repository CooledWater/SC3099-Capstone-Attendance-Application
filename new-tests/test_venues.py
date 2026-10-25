"""Venue catalogue: GET /venues and venue resolution on session create/edit.

Isolated: in-memory SQLite + mocked face service; never touches Supabase or a
running server. Run from the repo root:

    module2-backend\\venv\\Scripts\\python.exe -m pytest new-tests/test_venues.py -v
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="saiv-venues-")) / "bootstrap.db")
os.environ["JWT_SECRET"] = "isolated-venues-test-secret-with-at-least-32-characters"
os.environ["STRICT_SECURITY_MODE"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.auth import create_access_token
from app.database import Base, get_db, get_read_db
from app.face_service import face_service
from app.models import Course, Enrollment, Session as Meeting, User, Venue

VENUES = {
    "LT26": ("LT26", 1.3434326, 103.6815837),
    "LT1A": ("LT1A", 1.3472192106767371, 103.68029662241148),
    "LT23": ("LT23 (South Spine)", 1.342874514880452, 103.68170913308671),
    "LKC-LT": ("LKC Lecture Theatre", 1.3426003343169257, 103.68234011222137),
    "LT2A": ("LT2A (North Spine)", 1.3466229722788177, 103.6813765829288),
    "LT19": ("LT19", 1.3466944790053756, 103.68034837522399),
}
# Course default far from every hall, so a fallback to it is unmistakable.
COURSE_VENUE = (1.3644, 103.9915)


def _iso(value):
    return value.isoformat() + "Z"


@pytest.fixture
def world(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def face_service_down(request):
        raise httpx.ConnectError("face service not used in venue tests")

    with Session(engine) as db, httpx.Client(transport=httpx.MockTransport(face_service_down), base_url="http://test") as service:
        db.add_all([
            User(id=role, role=role, email=f"{role}@example.edu", full_name=role, hashed_password="unused",
                 camera_consent=True, geolocation_consent=True)
            for role in ("admin", "instructor", "student")
        ])
        db.add(Course(id="course", code="SC3099", name="Capstone", semester="S1", instructor_id="instructor",
                      venue_name="Course default", venue_latitude=COURSE_VENUE[0], venue_longitude=COURSE_VENUE[1],
                      geofence_radius_meters=100.0, risk_threshold=0.5))
        db.add(Enrollment(id="enrolment", student_id="student", course_id="course",
                          enrolled_at=datetime.utcnow() - timedelta(days=1)))
        db.add_all([Venue(code=code, name=name, latitude=lat, longitude=lng) for code, (name, lat, lng) in VENUES.items()])
        db.add(Venue(code="OLD-LT", name="Retired Hall", latitude=1.35, longitude=103.68, is_active=False))
        db.commit()

        def override():
            yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        monkeypatch.setattr(face_service, "_client", service)
        client = TestClient(app, raise_server_exceptions=False)

        def headers(role="instructor"):
            return {"Authorization": "Bearer " + create_access_token(role, role)}

        yield client, db, headers
        app.dependency_overrides.clear()
    engine.dispose()


def create_session(client, headers, **venue):
    start = datetime.utcnow() + timedelta(minutes=5)
    body = {
        "course_id": "course", "name": "Lecture", "session_type": "lecture",
        "scheduled_start": _iso(start), "scheduled_end": _iso(start + timedelta(hours=1)),
        "checkin_opens_at": _iso(start), "checkin_closes_at": _iso(start + timedelta(hours=1)),
        "require_liveness_check": False, **venue,
    }
    return client.post("/api/v1/sessions/", headers=headers(), json=body)


def created(client, headers, **venue):
    response = create_session(client, headers, **venue)
    assert response.status_code == 201, response.text
    return response.json()


def location(body):
    return body["venue_name"], body["venue_latitude"], body["venue_longitude"], body["geofence_radius_meters"]


# --- GET /venues --------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/v1/venues", "/api/v1/venues/"])
@pytest.mark.parametrize("role", ["instructor", "admin"])
def test_staff_list_active_venues_sorted_by_code(world, path, role):
    client, _, headers = world
    response = client.get(path, headers=headers(role))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 6
    assert [item["code"] for item in body["items"]] == sorted(VENUES)
    for item in body["items"]:
        name, lat, lng = VENUES[item["code"]]
        assert set(item) == {"id", "code", "name", "latitude", "longitude", "default_radius_meters"}
        assert (item["name"], item["latitude"], item["longitude"], item["default_radius_meters"]) == (name, lat, lng, 100.0)


def test_students_and_anonymous_cannot_list_venues(world):
    client, _, headers = world
    assert client.get("/api/v1/venues/", headers=headers("student")).status_code == 403
    assert client.get("/api/v1/venues/").status_code in (401, 403)


# --- POST /sessions/ ------------------------------------------------------------

def test_code_fills_coordinates_canonical_name_and_default_radius(world):
    client, _, headers = world
    body = created(client, headers, venue_name="LT23")
    assert location(body) == ("LT23 (South Spine)", 1.342874514880452, 103.68170913308671, 100.0)


def test_display_name_matches_case_insensitively(world):
    client, _, headers = world
    body = created(client, headers, venue_name="  lkc lecture theatre ")
    assert location(body) == ("LKC Lecture Theatre", 1.3426003343169257, 103.68234011222137, 100.0)


def test_catalogue_overrides_client_coordinates_but_keeps_explicit_radius(world):
    client, _, headers = world
    body = created(client, headers, venue_name="lt26", venue_latitude=1.0, venue_longitude=104.0,
                   geofence_radius_meters=75)
    assert location(body) == ("LT26", 1.3434326, 103.6815837, 75.0)


def test_deactivated_venue_is_rejected(world):
    client, db, headers = world
    response = create_session(client, headers, venue_name="OLD-LT")
    assert response.status_code == 400
    assert response.json()["detail"] == "Venue is not available"
    assert db.query(Meeting).count() == 0


def test_free_text_venues_keep_existing_behaviour(world):
    client, _, headers = world
    raw = created(client, headers, venue_name="NTU LT1", venue_latitude=1.3483, venue_longitude=103.6831,
                  geofence_radius_meters=100.0)
    assert location(raw) == ("NTU LT1", 1.3483, 103.6831, 100.0)
    fallback = created(client, headers, venue_name="Lecture Hall B")
    assert location(fallback) == ("Lecture Hall B", *COURSE_VENUE, 100.0)
    unnamed = created(client, headers)
    assert location(unnamed) == ("Course default", *COURSE_VENUE, 100.0)


def test_sessions_in_one_course_can_use_different_venues(world):
    client, db, headers = world
    lt26 = created(client, headers, venue_name="LT26")
    lt1a = created(client, headers, venue_name="LT1A")
    assert lt26["course_id"] == lt1a["course_id"] == "course"
    assert location(lt26) == ("LT26", 1.3434326, 103.6815837, 100.0)
    assert location(lt1a) == ("LT1A", 1.3472192106767371, 103.68029662241148, 100.0)
    stored = {row.id: (row.venue_latitude, row.venue_longitude) for row in db.query(Meeting)}
    assert stored == {lt26["id"]: (1.3434326, 103.6815837), lt1a["id"]: (1.3472192106767371, 103.68029662241148)}


def test_editing_the_catalogue_does_not_move_existing_sessions(world):
    client, db, headers = world
    session = created(client, headers, venue_name="LT19")
    db.query(Venue).filter(Venue.code == "LT19").update({"latitude": 1.0, "longitude": 104.0})
    db.commit()
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=headers())
    assert location(detail.json()) == ("LT19", 1.3466944790053756, 103.68034837522399, 100.0)


# --- PATCH /sessions/{id} -------------------------------------------------------

def patch(client, headers, session_id, **fields):
    return client.patch(f"/api/v1/sessions/{session_id}", headers=headers(), json=fields)


def test_patch_switches_venue_and_leaves_radius_alone(world):
    client, _, headers = world
    session = created(client, headers, venue_name="LT26", geofence_radius_meters=75)
    response = patch(client, headers, session["id"], venue_name="LT2A")
    assert response.status_code == 200, response.text
    assert location(response.json()) == ("LT2A (North Spine)", 1.3466229722788177, 103.6813765829288, 75.0)


def test_patch_to_unknown_name_clears_old_hall_coordinates(world):
    client, _, headers = world
    session = created(client, headers, venue_name="LT26")
    response = patch(client, headers, session["id"], venue_name="Somewhere else")
    assert response.status_code == 200, response.text
    assert location(response.json()) == ("Somewhere else", *COURSE_VENUE, 100.0)


def test_patch_resending_legacy_name_keeps_its_coordinates(world):
    client, _, headers = world
    session = created(client, headers, venue_name="NTU LT1", venue_latitude=1.3483, venue_longitude=103.6831)
    response = patch(client, headers, session["id"], venue_name="NTU LT1", name="Renamed")
    assert response.status_code == 200, response.text
    assert location(response.json())[:3] == ("NTU LT1", 1.3483, 103.6831)


def test_patch_without_venue_name_is_unchanged(world):
    client, _, headers = world
    session = created(client, headers, venue_name="LT1A")
    response = patch(client, headers, session["id"], name="Renamed")
    assert response.status_code == 200, response.text
    assert location(response.json())[:3] == ("LT1A", 1.3472192106767371, 103.68029662241148)


def test_patch_to_deactivated_venue_is_rejected_without_changes(world):
    client, db, headers = world
    session = created(client, headers, venue_name="LT26")
    response = patch(client, headers, session["id"], venue_name="Retired Hall")
    assert response.status_code == 400
    assert response.json()["detail"] == "Venue is not available"
    db.expire_all()
    row = db.get(Meeting, session["id"])
    assert (row.venue_name, row.venue_latitude, row.venue_longitude) == ("LT26", 1.3434326, 103.6815837)


# --- Check-in geofencing uses the selected hall ---------------------------------

def test_checkin_geofence_uses_each_sessions_own_venue(world):
    client, db, headers = world
    lt26 = created(client, headers, venue_name="LT26")
    lt1a = created(client, headers, venue_name="LT1A")
    now = datetime.utcnow()
    for session_id in (lt26["id"], lt1a["id"]):
        row = db.get(Meeting, session_id)
        row.status, row.scheduled_start, row.checkin_opens_at = "active", now - timedelta(minutes=1), now - timedelta(minutes=1)
    db.commit()

    def check_in(session_id):
        response = client.post("/api/v1/checkins/", headers=headers("student"), json={
            "session_id": session_id, "latitude": 1.3434326, "longitude": 103.6815837,
            "location_accuracy_meters": 10, "device_fingerprint": "venue-test-device",
        })
        assert response.status_code == 201, response.text
        return response.json()

    at_lt26 = check_in(lt26["id"])
    assert at_lt26["distance_from_venue_meters"] == 0
    assert at_lt26["status"] == "approved"

    wrong_hall = check_in(lt1a["id"])  # standing in LT26, ~445 m from LT1A
    assert wrong_hall["distance_from_venue_meters"] > 400
    assert wrong_hall["status"] == "rejected"
