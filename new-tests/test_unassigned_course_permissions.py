"""Unit tests for the unassigned-course instructor compatibility rule.

Pure function tests (no DB, no server): run from the repo root with
    module2-backend\\venv\\Scripts\\python.exe -m pytest new-tests/test_unassigned_course_permissions.py
"""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))

from app.permissions import can_staff_session, instructs_course, instructs_session, teaches  # noqa: E402

ALICE = NS(id="alice", role="instructor")
BOB = NS(id="bob", role="instructor")
ADMIN = NS(id="admin", role="admin")
STUDENT = NS(id="alice", role="student")  # same id as Alice on purpose

UNASSIGNED = NS(id="c-un", instructor_id=None)
ALICES_COURSE = NS(id="c-alice", instructor_id="alice")

ALICE_SESSION_UNASSIGNED = NS(id="s1", instructor_id="alice", course_id="c-un")
BOB_SESSION_IN_ALICES = NS(id="s2", instructor_id="bob", course_id="c-alice")


def test_teaches_stays_strict_for_unassigned_courses():
    assert teaches(ALICE, None) is False


@pytest.mark.parametrize("course, instructor_id, expected", [
    (UNASSIGNED, "alice", True),
    (UNASSIGNED, "bob", True),
    (ALICES_COURSE, "alice", True),
    (ALICES_COURSE, "bob", False),
    (None, "alice", False),
])
def test_instructs_course(course, instructor_id, expected):
    assert instructs_course(course, instructor_id) is expected


def test_creator_reaches_own_session_on_unassigned_course():
    assert instructs_session(ALICE, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is True


def test_other_instructor_cannot_reach_session_on_unassigned_course():
    assert instructs_session(BOB, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is False


def test_creating_a_session_in_an_assigned_course_grants_nothing():
    assert instructs_session(BOB, BOB_SESSION_IN_ALICES, ALICES_COURSE) is False


def test_assigned_instructor_reaches_every_session_in_their_course():
    assert instructs_session(ALICE, BOB_SESSION_IN_ALICES, ALICES_COURSE) is True


def test_non_instructor_roles_are_not_widened():
    assert instructs_session(STUDENT, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is False
    assert can_staff_session(None, STUDENT, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is False
    assert can_staff_session(None, ADMIN, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is True


def test_can_staff_session_uses_session_rule_for_instructors():
    assert can_staff_session(None, ALICE, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is True
    assert can_staff_session(None, BOB, ALICE_SESSION_UNASSIGNED, UNASSIGNED) is False
