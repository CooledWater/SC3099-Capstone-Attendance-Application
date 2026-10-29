"""Exercise the real deletion handler without importing production DB startup.

Extract only the handler and role dependency; use FastAPI HTTP requests and a
mock database. Database FK/transaction integration still needs a scratch DB.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def load_function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)


@pytest.fixture
def world():
    db = MagicMock()
    actor = SimpleNamespace(id="owner", role="instructor")
    session = SimpleNamespace(id="session", instructor_id="owner", status="scheduled",
                              course_id="course", name="Lecture")
    session_query, checkin_query, challenge_query, policy_query = [MagicMock() for _ in range(4)]
    session_query.filter.return_value.with_for_update.return_value.first.return_value = session
    checkin_query.filter.return_value.first.return_value = None
    models = {name: SimpleNamespace(id=MagicMock(), session_id=MagicMock())
              for name in ("SessionModel", "CheckIn", "MotionChallenge", "MotionPolicy")}
    queries = {id(models[name]): query for name, query in zip(models, (
        session_query, checkin_query, challenge_query, policy_query))}
    queries[id(models["CheckIn"].id)] = checkin_query
    db.query.side_effect = lambda model: queries[id(model)]
    course = SimpleNamespace(id="course", instructor_id="owner")
    db.get.return_value = course
    audit = MagicMock()
    namespace = {
        "app": FastAPI(), "Depends": Depends, "HTTPException": HTTPException,
        "Response": Response, "status": status, "User": SimpleNamespace,
        "Session": object, "get_db": lambda: db, "get_session_db": lambda: db,
        "get_current_user": lambda: actor, "get_read_current_user": lambda: actor,
        "SessionModel": models["SessionModel"], "CheckIn": models["CheckIn"],
        "motion": SimpleNamespace(MotionChallenge=models["MotionChallenge"],
                                  MotionPolicy=models["MotionPolicy"]),
        "create_audit_log": audit, "Course": SimpleNamespace,
    }
    load_function(ROOT / "module2-backend/app/auth.py", "require_roles", namespace)
    load_function(ROOT / "module2-backend/app/permissions.py", "teaches", namespace)
    load_function(ROOT / "module2-backend/app/main.py", "_teaches_session_course", namespace)
    load_function(ROOT / "module2-backend/app/main.py", "delete_session", namespace)
    with TestClient(namespace["app"], raise_server_exceptions=False) as client:
        yield SimpleNamespace(db=db, actor=actor, session=session, course=course, client=client, audit=audit,
                              session_query=session_query, checkin_query=checkin_query,
                              challenge_query=challenge_query, policy_query=policy_query)


@pytest.mark.parametrize("role", ["instructor", "admin"])
def test_success_deletes_motion_records_and_session_and_keeps_audit(world, role):
    world.actor.role = role
    if role == "admin":
        world.actor.id = "admin"
    response = world.client.delete("/api/v1/sessions/session")
    assert response.status_code == 204
    assert response.content == b""
    world.challenge_query.filter.return_value.delete.assert_called_once_with(synchronize_session=False)
    world.policy_query.filter.return_value.delete.assert_called_once_with(synchronize_session=False)
    world.audit.assert_called_once_with(
        world.db, "session_deleted", world.actor.id, "session",
        details={"name": "Lecture", "course_id": "course", "status": "scheduled"})
    world.db.delete.assert_called_once_with(world.session)
    world.db.commit.assert_called_once()
    world.db.rollback.assert_not_called()


@pytest.mark.parametrize("role", ["student", "ta"])
def test_non_management_roles_denied(world, role):
    world.actor.role = role
    assert world.client.delete("/api/v1/sessions/session").status_code == 403
    world.db.query.assert_not_called()


@pytest.mark.parametrize("case,expected", [
    ("missing", 404), ("other_owner", 403), ("course_reassigned", 403), ("course_unassigned", 403),
    ("active", 400), ("closed", 400), ("cancelled", 400), ("checkins", 409),
])
def test_rejected_deletions_do_not_mutate_database(world, case, expected):
    if case == "missing":
        world.session_query.filter.return_value.with_for_update.return_value.first.return_value = None
    elif case == "other_owner":
        world.actor.id = "other"
    elif case == "course_reassigned":
        world.course.instructor_id = "someone-else"
    elif case == "course_unassigned":
        world.course.instructor_id = None
    elif case == "checkins":
        world.checkin_query.filter.return_value.first.return_value = ("checkin",)
    else:
        world.session.status = case
    assert world.client.delete("/api/v1/sessions/session").status_code == expected
    world.db.delete.assert_not_called()
    world.db.commit.assert_not_called()
    world.audit.assert_not_called()
    world.challenge_query.filter.return_value.delete.assert_not_called()
    world.policy_query.filter.return_value.delete.assert_not_called()


@pytest.mark.parametrize("failure", ["cleanup", "audit", "delete", "commit"])
def test_mutation_failure_rolls_back(world, failure):
    error = RuntimeError("simulated failure")
    if failure == "cleanup":
        world.challenge_query.filter.return_value.delete.side_effect = error
    elif failure == "audit":
        world.audit.side_effect = error
    else:
        getattr(world.db, failure).side_effect = error
    assert world.client.delete("/api/v1/sessions/session").status_code == 500
    world.db.rollback.assert_called_once()


def test_unauthenticated_request_denied(world):
    def unauthenticated():
        raise HTTPException(status_code=401, detail="Authentication required")
    # Override the real role dependency's current-user provider.
    role_dependency = world.client.app.routes[-1].dependant.dependencies[0]
    current_user_provider = role_dependency.dependencies[0].call
    world.client.app.dependency_overrides[current_user_provider] = unauthenticated
    assert world.client.delete("/api/v1/sessions/session").status_code == 401
    world.db.query.assert_not_called()
