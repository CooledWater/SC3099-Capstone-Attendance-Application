"""Persist schedule transitions, including catch-up after backend downtime."""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime

from fastapi import Depends
from sqlalchemy import func, update
from starlette.concurrency import run_in_threadpool

from app.database import SessionLocal, get_db
from app.models import Session as AttendanceSession


def synchronize_sessions(db, now=None, *, session_id=None):
    from app.audit import create_audit_log

    now = now or datetime.utcnow()
    transitions = (
        ("scheduled", "active", AttendanceSession.scheduled_start,
         {"actual_start": func.coalesce(AttendanceSession.actual_start, AttendanceSession.scheduled_start)}),
        ("active", "closed", AttendanceSession.scheduled_end,
         {"actual_end": func.coalesce(AttendanceSession.actual_end, AttendanceSession.scheduled_end)}),
    )
    changed = 0
    for previous, target, deadline, timestamps in transitions:
        # The conditional UPDATE rechecks status after concurrent workers/edits.
        statement = update(AttendanceSession).where(AttendanceSession.status == previous, deadline <= now)
        if session_id is not None:
            statement = statement.where(AttendanceSession.id == session_id)
        ids = db.execute(
            statement
            .values(status=target, **timestamps)
            .returning(AttendanceSession.id)
            .execution_options(synchronize_session=False)
        ).scalars().all()
        for transitioned_id in ids:
            create_audit_log(
                db, "session_updated", resource_id=transitioned_id,
                details={"automatic": True, "status": {"from": previous, "to": target}},
            )
        changed += len(ids)
    from app.attendance_snapshots import capture_attendance_snapshots
    capture_attendance_snapshots(db, now, session_id=session_id)
    # Even zero-row UPDATEs open a transaction. End it before handlers run.
    db.commit()
    if changed:
        db.expire_all()
    return changed


def synchronize_checkin_session(db, session, now):
    """Reconcile the loaded target only when a deadline actually needs work.

    The independent clock still reconciles every session and captures snapshots.
    Check-ins must validate fresh deadlines even if that clock is delayed, but
    an already-current session needs neither global UPDATEs nor a commit that
    expires authentication and every other ORM object in the request.
    """
    if ((session.status == 'scheduled' and session.scheduled_start <= now)
            or (session.status == 'active' and session.scheduled_end <= now)):
        synchronize_sessions(db, now, session_id=session.id)


def get_session_db(db=Depends(get_db)):
    # Share authentication's request session instead of checking out a second
    # connection while the first remains held.
    synchronize_sessions(db)
    yield db


def tick_sessions():
    with SessionLocal() as db:
        synchronize_sessions(db)


async def session_clock():
    while True:
        try:
            await run_in_threadpool(tick_sessions)
        except Exception:
            logging.getLogger(__name__).exception("Session scheduling failed; retrying")
        await asyncio.sleep(1)


@asynccontextmanager
async def session_lifespan(app):
    # Reconcile before serving requests, then continue independently of clients.
    await run_in_threadpool(tick_sessions)
    from app.push_notifications import push_clock
    from app.data_deletion import deletion_clock
    task = asyncio.create_task(session_clock())
    push_task = asyncio.create_task(push_clock())
    deletion_task = asyncio.create_task(deletion_clock())
    try:
        yield
    finally:
        task.cancel()
        push_task.cancel()
        deletion_task.cancel()
        for pending_task in (task, push_task, deletion_task):
            with suppress(asyncio.CancelledError):
                await pending_task
