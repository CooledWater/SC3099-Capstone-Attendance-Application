"""Audit user search filters the full server-side result before paging."""
import pytest

from test_ta_scope import world
from app.models import AuditLog, User


@pytest.fixture
def audit_world(world):
    call, db = world
    alice = db.get(User, "ia")
    alice.full_name, alice.email = "Alice Example", "alice_test@example.edu"
    bob = db.get(User, "ib")
    bob.full_name, bob.email = "Bob Example", "bob@example.edu"
    db.add_all([
        AuditLog(user_id="ia", action="logout"),
        AuditLog(user_id="ia", action="device_registered"),
        AuditLog(user_id="ib", action="logout"),
        AuditLog(user_id=None, action="session_created"),
    ])
    db.commit()
    return call, db


@pytest.mark.parametrize("search,total", [
    ("ALICE", 2), (" alice_test@EXAMPLE.edu ", 2), ("Bob", 1),
    ("Example", 3), ("nobody", 0), ("%", 0), ("_test", 2), ("   ", 4),
])
def test_case_insensitive_partial_name_email_and_literal_wildcards(audit_world, search, total):
    call, _ = audit_world
    response = call("admin", "/audit/", user_search=search)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == total


def test_search_combines_with_action_pagination_and_inactive_user_history(audit_world):
    call, db = audit_world
    first = call("admin", "/audit/", user_search="alice", limit=1).json()
    second = call("admin", "/audit/", user_search="alice", limit=1, offset=1).json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    filtered = call("admin", "/audit/", user_search="alice", action="logout").json()
    assert filtered["total"] == 1
    db.get(User, "ia").is_active = False
    db.commit()
    assert call("admin", "/audit/", user_search="alice").json()["total"] == 2
    assert call("ia", "/audit/", user_search="Bob").status_code in (401, 403)


@pytest.mark.parametrize("uid", ["ib", "t1", "sa"])
def test_user_search_does_not_bypass_admin_access(audit_world, uid):
    call, _ = audit_world
    assert call(uid, "/audit/", user_search="alice").status_code == 403
