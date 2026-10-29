"""Admin device owner names against disposable in-memory SQLite data."""
import pytest

from test_ta_assignment_admin import world
from app.models import Device


def seed_devices(db):
    db.add_all([
        Device(id="device-a", user_id="sa", device_fingerprint="fingerprint-a", is_active=True),
        Device(id="device-b", user_id="t_off", device_fingerprint="fingerprint-b", is_active=False),
    ])
    db.commit()


def test_device_list_includes_owner_name_and_email(world):
    call, db = world
    seed_devices(db)
    response = call("admin", "/devices/?user_id=sa")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    row = result["items"][0]
    assert row["user_name"] == "User sa"
    assert row["user_email"] == "sa@example.edu"
    assert row["user_id"] == "sa"
    assert row["id"] == "device-a"
    assert "shared_browser" in row


def test_disabled_device_and_inactive_owner_keep_identity_and_pagination(world):
    call, db = world
    seed_devices(db)
    response = call("admin", "/devices/?is_active=false&limit=1&offset=0")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["items"][0]["user_name"] == "Off"
    assert result["items"][0]["user_email"] == "t_off@example.edu"
    assert call("admin", "/devices/?is_active=false&limit=1&offset=1").json()["items"] == []


@pytest.mark.parametrize("uid", ["sa", "ia", "t1", None])
def test_owner_identity_list_remains_admin_only(world, uid):
    call, _ = world
    response = call(uid, "/devices/")
    assert response.status_code in (401, 403)
