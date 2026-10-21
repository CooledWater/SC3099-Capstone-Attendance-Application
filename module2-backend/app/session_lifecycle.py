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


def synchronize_sessions(db, now=None):
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
        ids = db.execute(
            update(AttendanceSession)
            .where(AttendanceSession.status == previous, deadline <= now)
            .values(status=target, **timestamps)
            .returning(AttendanceSession.id)
            .execution_options(synchronize_session=False)
        ).scalars().all()
        for session_id in ids:
            create_audit_log(
                db, "session_updated", resource_id=session_id,
                details={"automatic": True, "status": {"from": previous, "to": target}},
            )
        changed += len(ids)
    # Even zero-row UPDATEs open a transaction. End it before handlers run.
    db.commit()
    if changed:
        db.expire_all()
    return changed


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
    from app.invitations import invitation_clock
    task = asyncio.create_task(session_clock())
    email_task = asyncio.create_task(invitation_clock())
    try:
        yield
    finally:
        task.cancel()
        email_task.cancel()
        for pending_task in (task, email_task):
            with suppress(asyncio.CancelledError):
                await pending_task
