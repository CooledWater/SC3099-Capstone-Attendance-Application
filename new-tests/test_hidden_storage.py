"""Disposable SQLite/PostgreSQL regressions for the handoff fixes.

PostgreSQL is accepted only in the owned hidden-tests Compose network/database:
  SAIV_FIX_POSTGRES=1 python -m pytest new-tests/test_hidden_storage.py
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, String, Table, create_engine, event, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
POSTGRES = os.getenv('SAIV_FIX_POSTGRES') == '1'
if POSTGRES:
    assert os.environ.get('SAIV_HIDDEN_COMPOSE') == '1'
    URL = 'postgresql://hidden:hidden-disposable-password@hidden-db:5432/hidden_fixes'
else:
    URL = 'sqlite:///' + str(Path(tempfile.mkdtemp(prefix='saiv-fix-bootstrap-')) / 'test.db')
os.environ['DATABASE_URL'] = URL
os.environ.setdefault('JWT_SECRET', 'disposable-fix-test-signing-secret-at-least-32')
os.environ.setdefault('REDIS_URL', 'redis://127.0.0.1:1/0')
sys.path.insert(0, str(ROOT / 'module2-backend'))

from app.database import Base
from app.models import AuditLog, CheckIn, Course, Session as Meeting, SessionAttendanceSnapshot, User
from app.data_deletion import deletion_clock, purge_due_checkins
from app.push_notifications import PushDelivery, PushSubscription
from app.travel import assess_impossible_travel, distance_meters

NOW = datetime(2026, 11, 7, 12, 0, 0, 123456)


@pytest.fixture
def storage(tmp_path):
    engine = create_engine(URL if POSTGRES else 'sqlite:///' + str(tmp_path / 'test.db'))
    if not POSTGRES:
        @event.listens_for(engine, 'connect')
        def foreign_keys(connection, record):
            connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add(User(id='student', email='student@example.org', full_name='Test', role='student', hashed_password='unused'))
        db.flush()
        db.add(Course(id='course', code='FIX', name='Fix', semester='test'))
        db.flush()
        db.add(Meeting(id='meeting', course_id='course', name='Test', status='closed',
                       scheduled_start=NOW-timedelta(days=31), scheduled_end=NOW-timedelta(days=30),
                       checkin_opens_at=NOW-timedelta(days=31), checkin_closes_at=NOW-timedelta(days=30)))
        db.flush()
        db.add(SessionAttendanceSnapshot(session_id='meeting', expected_attendances=1, captured_at=NOW))
    try:
        yield engine, factory
    finally:
        # Only this fixture's disposable DB, never an arbitrary environment URL.
        with engine.begin() as connection:
            if engine.dialect.has_table(connection, 'risk_signals'):
                Table('risk_signals', MetaData(), autoload_with=connection).drop(connection)
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_record(factory, identity='record', **fields):
    with factory.begin() as db:
        if identity != 'record':
            db.add(User(id=identity, email=identity+'@example.org', full_name=identity, role='student', hashed_password='unused'))
            db.flush()
        record = CheckIn(id=identity, student_id='student' if identity == 'record' else identity,
                         session_id='meeting', checked_in_at=NOW-timedelta(days=30), **fields)
        db.add(record)


@pytest.mark.parametrize('operation', [
    "UPDATE audit_logs SET success=false WHERE id='audit'",
    "DELETE FROM audit_logs WHERE id='audit'",
])
def test_direct_audit_writes_cannot_mutate_rows(storage, operation):
    engine, factory = storage
    with factory.begin() as db:
        db.add(AuditLog(id='audit', action='logout', user_id='student'))
    with pytest.raises(DBAPIError, match='immutable'):
        with engine.begin() as connection:
            connection.execute(text(operation))
    with factory() as db:
        assert db.get(AuditLog, 'audit').success is True


def test_sqlite_replace_cannot_overwrite_audit(storage):
    engine, factory = storage
    if POSTGRES:
        pytest.skip('SQLite-specific REPLACE path')
    with factory.begin() as db:
        db.add(AuditLog(id='audit', action='logout'))
    with pytest.raises(DBAPIError, match='immutable'):
        with engine.begin() as connection:
            connection.execute(text("INSERT OR REPLACE INTO audit_logs (id,action,success,timestamp) VALUES ('audit','logout',false,CURRENT_TIMESTAMP)"))


@pytest.mark.parametrize('operation', ['UPDATE audit_logs SET success=false', 'DELETE FROM audit_logs', 'TRUNCATE audit_logs'])
def test_postgres_non_owner_role_is_protected(storage, operation):
    if not POSTGRES:
        pytest.skip('Requires disposable PostgreSQL')
    engine, factory = storage
    with factory.begin() as db:
        db.add(AuditLog(id='audit', action='logout'))
    with engine.connect() as connection, connection.begin() as transaction:
        connection.execute(text('CREATE ROLE saiv_audit_test_writer NOLOGIN'))
        connection.execute(text('GRANT USAGE ON SCHEMA public TO saiv_audit_test_writer'))
        connection.execute(text('GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON audit_logs TO saiv_audit_test_writer'))
        connection.execute(text('SET LOCAL ROLE saiv_audit_test_writer'))
        assert connection.scalar(text('SELECT current_user')) == 'saiv_audit_test_writer'
        connection.execute(text("INSERT INTO audit_logs (id,action,success,timestamp) VALUES ('writer-insert','logout',true,CURRENT_TIMESTAMP)"))
        with pytest.raises(DBAPIError, match='immutable'):
            with connection.begin_nested():
                connection.execute(text(operation))
        assert connection.scalar(text('SELECT count(*) FROM audit_logs')) == 2
        transaction.rollback()


def test_retention_exact_boundary_children_audit_and_snapshots(storage):
    engine, factory = storage
    add_record(factory, scheduled_deletion_at=NOW)
    add_record(factory, 'future', scheduled_deletion_at=NOW+timedelta(microseconds=1))
    add_record(factory, 'legacy')
    with factory.begin() as db:
        db.add(AuditLog(id='audit', action='checkin_attempted', resource_id='record', user_id='student'))
        db.add(PushSubscription(id='sub', user_id='student', endpoint_hash='hash', endpoint='unused', p256dh='key', auth='secret'))
        db.flush()
        db.add(PushDelivery(id='delivery', checkin_id='record', subscription_id='sub'))
    metadata = MetaData()
    Table('checkins', metadata, autoload_with=engine)
    signals = Table('risk_signals', metadata, Column('id', String, primary_key=True),
                    Column('checkin_id', String, ForeignKey('checkins.id'), nullable=False))
    signals.create(engine)
    with engine.begin() as connection:
        connection.execute(signals.insert().values(id='risk', checkin_id='record'))
    assert purge_due_checkins(factory, NOW-timedelta(microseconds=1)) == 0
    assert purge_due_checkins(factory, NOW, batch_size=1) == 1
    assert purge_due_checkins(factory, NOW) == 1
    assert purge_due_checkins(factory, NOW) == 0
    with factory() as db:
        assert [row.id for row in db.query(CheckIn)] == ['future']
        assert db.get(User, 'student').is_active is True
        assert db.get(PushSubscription, 'sub') is not None
        assert db.query(PushDelivery).count() == 0
        assert db.get(AuditLog, 'audit').resource_id == 'record'
        assert db.get(SessionAttendanceSnapshot, 'meeting').expected_attendances == 1
        assert not db.execute(select(signals)).all()
    assert purge_due_checkins(factory, NOW+timedelta(microseconds=1)) == 1


def test_cleanup_rolls_back_children_when_parent_delete_fails(storage):
    engine, factory = storage
    add_record(factory, scheduled_deletion_at=NOW)
    with factory.begin() as db:
        db.add(PushSubscription(id='sub', user_id='student', endpoint_hash='hash', endpoint='unused', p256dh='key', auth='secret'))
        db.flush()
        db.add(PushDelivery(id='delivery', checkin_id='record', subscription_id='sub'))
    def fail_parent(connection, cursor, statement, parameters, context, many):
        if statement.startswith('DELETE FROM checkins'):
            raise RuntimeError('simulated database failure')
    event.listen(engine, 'before_cursor_execute', fail_parent)
    try:
        with pytest.raises(RuntimeError):
            purge_due_checkins(factory, NOW)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_parent)
    with factory() as db:
        assert db.get(CheckIn, 'record') is not None
        assert db.get(PushDelivery, 'delivery') is not None
    assert purge_due_checkins(factory, NOW) == 1


def test_migration_backfills_without_changing_existing_deadlines(storage):
    from alembic import command
    from alembic.config import Config
    engine, factory = storage
    add_record(factory)
    add_record(factory, 'future', scheduled_deletion_at=NOW+timedelta(days=1))
    with factory.begin() as db:
        db.add(AuditLog(id='legacy-audit', action='logout'))
    # Emulate a pre-fix schema, rather than merely reapplying the migration
    # to an already protected fresh database.
    with engine.begin() as connection:
        if POSTGRES:
            connection.execute(text('DROP TRIGGER saiv_audit_append_only ON audit_logs'))
        else:
            for name in ('update', 'delete', 'replace'):
                connection.execute(text('DROP TRIGGER saiv_audit_no_' + name))
        connection.execute(text('DROP INDEX ix_checkins_scheduled_deletion_at'))
        connection.execute(text("UPDATE audit_logs SET success=true WHERE id='legacy-audit'"))
    config = Config(str(ROOT / 'module2-backend/alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    with factory() as db:
        assert db.get(CheckIn, 'record').scheduled_deletion_at == NOW
        assert db.get(CheckIn, 'future').scheduled_deletion_at == NOW+timedelta(days=1)
        assert db.get(AuditLog, 'legacy-audit').success is True
    with pytest.raises(DBAPIError, match='immutable'):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_logs WHERE id='legacy-audit'"))
    with engine.begin() as connection:
        connection.execute(text('DROP TABLE alembic_version'))


def test_postgres_cleanup_workers_claim_disjoint_batches(storage):
    if not POSTGRES:
        pytest.skip('Requires PostgreSQL row locks')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    _, factory = storage
    for index in range(10):
        add_record(factory, 'due-' + str(index), scheduled_deletion_at=NOW)
    gate = Barrier(2)
    def cleanup(_):
        gate.wait(timeout=10)
        return purge_due_checkins(factory, NOW, batch_size=5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(cleanup, range(2))) == [5, 5]
    with factory() as db:
        assert db.query(CheckIn).count() == 0


def test_clock_runs_both_jobs_and_retries_independently(monkeypatch):
    import app.data_deletion as deletion
    calls = []
    def checkins():
        calls.append('checkins')
        raise RuntimeError('offline')
    def students():
        calls.append('students')
    async def stop(seconds):
        assert seconds == 60
        raise asyncio.CancelledError()
    monkeypatch.setattr(deletion, 'purge_due_checkins', checkins)
    monkeypatch.setattr(deletion, 'purge_due_students', students)
    monkeypatch.setattr(deletion.asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(deletion_clock())
    assert calls == ['checkins', 'students']


@pytest.mark.parametrize('hours,longitude,accuracy,flagged', [
    (0, 0.001, 0, False),  # nearby jitter at the same instant
    (0, 0.1, 0, True),
    (1, 5, 0, False),  # plausible high-speed travel
    (1, 20, 0, True),
    (1, 20, 2000000, False),  # uncertainty overlaps the plausible region
    (25, 100, 0, False),  # outside history window
])
def test_travel_noise_accuracy_time_and_plausible_speed(storage, hours, longitude, accuracy, flagged):
    _, factory = storage
    add_record(factory, latitude=0, longitude=0, location_accuracy_meters=accuracy)
    with factory.begin() as db:
        db.get(CheckIn, 'record').checked_in_at = NOW-timedelta(hours=hours)
    with factory() as db:
        result = assess_impossible_travel(db, 'student', SimpleNamespace(latitude=0, longitude=longitude, location_accuracy_meters=0), NOW)
        assert bool(result) is flagged
        if result:
            assert result == {'type': 'impossible_travel', 'severity': 'high', 'weight': 0.0}


@pytest.mark.parametrize('extra_meters,flagged', [(-1, False), (1, True)])
def test_travel_speed_threshold(storage, extra_meters, flagged):
    _, factory = storage
    add_record(factory, latitude=0, longitude=0, location_accuracy_meters=25)
    meters = 1200000 + 1000 + 25 + 50 + extra_meters
    longitude = meters / distance_meters(0, 0, 0, 1)
    with factory.begin() as db:
        db.get(CheckIn, 'record').checked_in_at = NOW-timedelta(hours=1)
    with factory() as db:
        result = assess_impossible_travel(db, 'student', SimpleNamespace(latitude=0, longitude=longitude, location_accuracy_meters=50), NOW)
        assert bool(result) is flagged
