"""Deterministic scheduler tests using an isolated in-memory database."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))
from app.database import Base
from app.models import Session as AttendanceSession, AuditLog
from app.session_lifecycle import synchronize_sessions

NOW = datetime(2026, 10, 21, 8)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def session(db, start, end, status="scheduled"):
    item = AttendanceSession(
        course_id="test-course", name="Schedule test", status=status,
        scheduled_start=NOW + timedelta(minutes=start),
        scheduled_end=NOW + timedelta(minutes=end),
        checkin_opens_at=NOW + timedelta(minutes=start),
        checkin_closes_at=NOW + timedelta(minutes=end),
    )
    db.add(item)
    db.commit()
    return item


def test_start_and_end_boundaries_and_idempotency(db):
    item = session(db, 0, 60)
    assert synchronize_sessions(db, NOW - timedelta(microseconds=1)) == 0
    assert synchronize_sessions(db, NOW) == 1
    assert item.status == "active" and item.actual_start == NOW
    assert synchronize_sessions(db, NOW) == 0
    assert synchronize_sessions(db, NOW + timedelta(minutes=60)) == 1
    assert item.status == "closed" and item.actual_end == item.scheduled_end
    assert synchronize_sessions(db, NOW + timedelta(days=1)) == 0
    assert db.query(AuditLog).count() == 2


def test_downtime_catches_up_both_transitions(db):
    item = session(db, -120, -60)
    assert synchronize_sessions(db, NOW) == 2
    assert item.status == "closed"
    assert item.actual_start == item.scheduled_start
    assert item.actual_end == item.scheduled_end


@pytest.mark.parametrize("status", ["cancelled", "closed"])
def test_terminal_states_are_preserved(db, status):
    item = session(db, -120, -60, status)
    assert synchronize_sessions(db, NOW) == 0
    assert item.status == status
    assert db.query(AuditLog).count() == 0


def test_rescheduled_session_uses_new_deadline(db):
    item = session(db, 0, 60)
    item.scheduled_start += timedelta(hours=1)
    item.scheduled_end += timedelta(hours=1)
    db.commit()
    assert synchronize_sessions(db, NOW) == 0
    assert synchronize_sessions(db, NOW + timedelta(hours=1)) == 1
    assert item.status == "active"


def test_no_change_reconciliation_ends_transaction(db):
    session(db, 60, 120)
    assert synchronize_sessions(db, NOW) == 0
    assert not db.in_transaction()


def test_scheduler_dependency_shares_authentication_connection(monkeypatch):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from app import session_lifecycle

    app = FastAPI()
    connections = []
    def database():
        connection = object()
        connections.append(connection)
        yield connection

    def authenticate(db=Depends(session_lifecycle.get_db)):
        return db

    @app.get("/")
    def endpoint(auth=Depends(authenticate), db=Depends(session_lifecycle.get_session_db)):
        return {"shared": auth is db}

    app.dependency_overrides[session_lifecycle.get_db] = database
    monkeypatch.setattr(session_lifecycle, "synchronize_sessions", lambda db: None)
    with TestClient(app) as client:
        assert client.get("/").json() == {"shared": True}
    assert len(connections) == 1


def test_session_summary_queries_do_not_grow_with_session_count(db):
    import ast
    from sqlalchemy import event, func
    from app import motion
    from app.models import Course, Enrollment

    # Load the real serializers without importing main's database startup.
    tree = ast.parse((Path(__file__).resolve().parents[1] / "module2-backend/app/main.py").read_text())
    names = {"_effective_venue", "_serialize_session", "_session_summary_context", "_serialize_session_summary"}
    namespace = {"Session": Session, "SessionModel": AttendanceSession, "Course": Course,
                 "Enrollment": Enrollment, "func": func, "motion": motion}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]), "main.py", "exec"), namespace)
    Base.metadata.create_all(db.get_bind())
    db.add(Course(id="test-course", code="SCHEDULE", name="Scheduling", semester="test"))
    db.commit()
    for _ in range(10):
        session(db, 60, 120)
    rows = db.query(AttendanceSession).all()
    queries = []
    def record(*args):
        queries.append(args[2])
    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        context = namespace["_session_summary_context"](db, rows)
        summaries = [namespace["_serialize_session_summary"](db, row, context) for row in rows]
        assert len(queries) == 4
        assert len(summaries) == 10
        assert all(row["course_code"] == "SCHEDULE" and row["total_enrolled"] == 0 for row in summaries)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)


def test_manual_start_and_custom_checkin_window_are_preserved(db):
    item = session(db, -60, 0, "active")
    item.actual_start = NOW - timedelta(minutes=70)
    item.checkin_closes_at = NOW - timedelta(minutes=30)
    db.commit()
    assert synchronize_sessions(db, NOW) == 1
    assert item.actual_start == NOW - timedelta(minutes=70)
    assert item.checkin_closes_at == NOW - timedelta(minutes=30)


@pytest.mark.asyncio
async def test_background_clock_persists_without_requests(db, monkeypatch):
    import asyncio
    from app import session_lifecycle

    item = session(db, -1, 1)
    current = datetime.utcnow()
    item.scheduled_start = current - timedelta(minutes=1)
    item.scheduled_end = current + timedelta(minutes=1)
    db.commit()
    engine = db.get_bind()
    monkeypatch.setattr(session_lifecycle, "SessionLocal", lambda: Session(engine))
    async with session_lifecycle.session_lifespan(None):
        db.refresh(item)
        assert item.status == "active"
        item.scheduled_end = current - timedelta(seconds=1)
        db.commit()
        for _ in range(60):
            await asyncio.sleep(0.05)
            db.refresh(item)
            if item.status == "closed":
                break
        assert item.status == "closed"


@pytest.mark.asyncio
async def test_lifespan_reconciles_before_serving_and_stops_worker(monkeypatch):
    import asyncio
    from app import session_lifecycle

    calls = []
    monkeypatch.setattr(session_lifecycle, "tick_sessions", lambda: calls.append("tick"))
    async with session_lifecycle.session_lifespan(None):
        assert calls  # Startup reconciliation completes before requests are served.
        for _ in range(50):
            if len(calls) > 1:
                break
            await asyncio.sleep(0.01)
        assert len(calls) > 1  # Clock runs without HTTP requests.
    count = len(calls)
    await asyncio.sleep(0.02)
    assert len(calls) == count


@pytest.mark.asyncio
async def test_clock_retries_after_database_failure(monkeypatch):
    import asyncio
    from app import session_lifecycle

    calls = []
    def failing_tick():
        calls.append("tick")
        if len(calls) == 1:
            raise RuntimeError("Temporary database outage")

    async def next_tick(_):
        if len(calls) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(session_lifecycle, "tick_sessions", failing_tick)
    monkeypatch.setattr(session_lifecycle.asyncio, "sleep", next_tick)
    with pytest.raises(asyncio.CancelledError):
        await session_lifecycle.session_clock()
    assert len(calls) == 2
