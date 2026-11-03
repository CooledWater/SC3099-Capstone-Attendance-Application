"""Course- and session-level access rules shared by the Module 2 endpoints.

Instructors reach a course only through ``courses.instructor_id``: a course with
no instructor is admin-only, and creating a session in a course grants nothing
on its own. TAs reach a course only through a ``course_assistants`` row, and a
session only through a ``session_assistants`` row plus that course assignment.
Course assignment alone grants no session or attendance access (approved
2026-11-03, superseding API-SPECIFICATION.md's course-level TA wording).

GET /sessions/{id}/attendance keeps its documented instructor rule (see
API-SPECIFICATION.md) and only uses ``assists_session`` for TAs.
"""
from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.models import Course, CourseAssistant, Enrollment, SessionAssistant, User
from app.models import Session as SessionModel


def teaches(user: User, course_instructor_id: str | None) -> bool:
    """True when ``user`` is the instructor assigned to the course."""
    return (
        user.role == "instructor"
        and course_instructor_id is not None
        and course_instructor_id == user.id
    )


def assists(db: Session, user: User, course_id: str) -> bool:
    """True when ``user`` is a TA assigned to the course."""
    return user.role == "ta" and db.query(
        exists()
        .where(CourseAssistant.course_id == course_id)
        .where(CourseAssistant.user_id == user.id)
    ).scalar()


def assists_session(db: Session, user: User, session_id: str, course_id: str) -> bool:
    """True when ``user`` is a TA assigned to the session and still to its course."""
    return user.role == "ta" and db.query(
        exists()
        .where(SessionAssistant.session_id == session_id)
        .where(SessionAssistant.user_id == user.id)
    ).scalar() and assists(db, user, course_id)


def can_staff_course(db: Session, user: User, course: Course) -> bool:
    """Staff access to one course as a whole (not to its sessions for TAs)."""
    if user.role == "admin":
        return True
    if user.role == "instructor":
        return teaches(user, course.instructor_id)
    if user.role == "ta":
        return assists(db, user, course.id)
    return False


def can_staff_session(db: Session, user: User, session: SessionModel, course: Course) -> bool:
    """Staff read/review access to one session's details and check-ins.

    Admins and the course's instructor as before; TAs need a session assignment.
    """
    if user.role == "ta":
        return assists_session(db, user, session.id, course.id)
    return can_staff_course(db, user, course)


def assigned_session_scope(user: User) -> list:
    """Extra WHERE conditions on ``Session`` for TAs: assigned sessions only.

    Combine with ``assigned_course_scope`` (which also needs ``Course`` joined).
    Other roles get no extra condition.
    """
    if user.role != "ta":
        return []
    return [
        exists()
        .where(SessionAssistant.session_id == SessionModel.id)
        .where(SessionAssistant.user_id == user.id)
    ]


def assigned_course_scope(user: User) -> list:
    """WHERE conditions on ``Course`` for the caller's own courses, by role.

    Student: active enrollments. Instructor: courses.instructor_id. TA: a
    course_assistants row. Admin: every course.
    """
    if user.role == "admin":
        return []
    if user.role == "instructor":
        return [Course.instructor_id == user.id]
    if user.role == "ta":
        return [
            exists()
            .where(CourseAssistant.course_id == Course.id)
            .where(CourseAssistant.user_id == user.id)
        ]
    if user.role == "student":
        return [
            exists()
            .where(Enrollment.course_id == Course.id)
            .where(Enrollment.student_id == user.id)
            .where(Enrollment.is_active == True)  # noqa: E712
        ]
    return [Course.id.is_(None)]  # unknown role: match nothing
