"""Student metrics and HTTP ownership in isolated SQLite, never shared storage."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp(prefix='student-overview-')) / 'bootstrap.db')
os.environ['JWT_SECRET'] = 'isolated-student-overview-test-key-at-least-32-characters'
os.environ['STRICT_SECURITY_MODE'] = 'false'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'module2-backend'))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.main import app
from app.auth import create_access_token
from app.database import Base, get_db, get_read_db
from app.models import AuditLog, CheckIn, Course, Enrollment, Session as Meeting, User
from app.student_overview import overview, eligible

NOW = datetime(2026, 10, 24, 4)

@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv('SEMESTER_START_DATE', '2026-08-08')
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(id=id, email=f'{id}@example.edu', full_name=id, role=role, hashed_password='unused') for id, role in [('student','student'),('other','student'),('instructor','instructor'),('admin','admin')]])
        db.add_all([Course(id='c', code='SC4000', name='Machine Learning', semester='S1'), Course(id='other-course', code='SC9999', name='Other', semester='S1'), Course(id='zero', code='SC0000', name='Empty', semester='S1')])
        db.add_all([Enrollment(id='e', student_id='student', course_id='c', enrolled_at=datetime(2026,8,8)), Enrollment(id='z', student_id='student', course_id='zero', enrolled_at=datetime(2026,8,8)), Enrollment(id='o', student_id='other', course_id='other-course', enrolled_at=datetime(2026,8,8))])
        db.commit()
        def meeting(id, start, status='closed', course='c', end=None):
            row = Meeting(id=id, course_id=course, name=id, status=status, scheduled_start=start, scheduled_end=end or start+timedelta(hours=1), checkin_opens_at=start, checkin_closes_at=end or start+timedelta(hours=1))
            db.add(row); db.flush(); return row
        def record(id, session, status='approved', owner='student'):
            row = CheckIn(id=id, session_id=session, student_id=owner, status=status, checked_in_at=NOW-timedelta(days=1), risk_score=0.1)
            db.add(row); db.flush(); return row
        def override(): yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_read_db] = override
        yield db, meeting, record, TestClient(app)
        app.dependency_overrides.clear()
    engine.dispose()

def data(world, section='all', course='c'):
    db, _, _, _ = world
    db.commit()
    return overview(db, 'student', section, course if section != 'flagged' else None, NOW)

def test_nine_of_ten_and_missing_checkins(world):
    _, meeting, record, _ = world
    for i in range(10):
        meeting(str(i), datetime(2026,9,1)+timedelta(days=i))
        if i < 9: record('r'+str(i),str(i))
    result = data(world)['attendance']
    assert (result['approved'], result['eligible'], result['percentage']) == (9,10,90)
    assert 'sessions' not in result  # No unused completed-session payload.

def test_nonapproved_and_unresolved_are_separate(world):
    _, meeting, record, _ = world
    for i, status in enumerate(['pending','flagged','rejected','appealed','approved']):
        meeting(str(i), datetime(2026,9,1)+timedelta(days=i)); record('r'+str(i),str(i),status)
    result = data(world)
    assert result['attendance']['percentage'] == 20
    assert result['attendance']['unresolved'] == 3
    assert result['flagged'] == {'total':2,'flagged':1,'appealed':1}

def test_lifecycle_period_and_enrollment_exclusions(world):
    db, meeting, _, _ = world
    meeting('before-semester',datetime(2026,8,1))
    for state in ['scheduled','active','cancelled']:
        meeting(state,NOW+timedelta(hours=2),state)
    meeting('cancelled-past',NOW-timedelta(days=2),'cancelled')
    meeting('before-enrollment',datetime(2026,8,9))
    db.get(Enrollment,'e').enrolled_at = datetime(2026,8,10)
    meeting('valid',datetime(2026,9,1))
    assert data(world)['attendance']['eligible'] == 1

def test_historical_drop_and_reenrollment_audit(world):
    db, meeting, _, _ = world
    db.get(Enrollment,'e').enrolled_at = datetime(2026,10,1)
    for id, action, stamp in [('a','enrollment_added',datetime(2026,8,8)),('b','enrollment_removed',datetime(2026,9,1)),('c','enrollment_added',datetime(2026,10,1))]:
        db.add(AuditLog(id=id, resource_id='e', resource_type='enrollment', action=action, timestamp=stamp, success=True))
    meeting('before',datetime(2026,8,7)); meeting('first',datetime(2026,8,20)); meeting('gap',datetime(2026,9,15)); meeting('second',datetime(2026,10,10))
    assert data(world)['attendance']['eligible'] == 2

def test_stored_interval_excludes_after_drop():
    enrollment = SimpleNamespace(enrolled_at=datetime(2026,8,8), dropped_at=datetime(2026,9,1), is_active=False)
    assert eligible(enrollment, [], datetime(2026,8,20))
    assert not eligible(enrollment, [], datetime(2026,9,1))

def test_zero_denominator_and_course_switch(world):
    assert data(world, 'attendance', 'zero')['attendance']['percentage'] is None
    assert data(world, 'attendance', 'zero')['attendance']['eligible'] == 0

def test_singapore_midnight_and_today_lifecycles(world):
    _, meeting, _, _ = world
    meeting('yesterday',datetime(2026,10,23,15,59),'closed')
    meeting('midnight',datetime(2026,10,23,16),'closed')
    meeting('active',NOW-timedelta(minutes=10),'active',end=NOW+timedelta(hours=1))
    meeting('upcoming',datetime(2026,10,24,15,59),'scheduled')
    meeting('tomorrow',datetime(2026,10,24,16),'scheduled')
    meeting('cancelled',NOW,'cancelled')
    result = data(world)['today']
    assert result['total'] == 3
    assert (result['active'], result['upcoming'], result['completed']) == (1,1,1)
    assert result['start'] == '2026-10-23T16:00:00Z'

def test_only_unresolved_appeals_count_and_student_scope(world):
    db, meeting, record, _ = world
    meeting('appeal',NOW-timedelta(days=1)); row=record('appeal','appeal','appealed')
    meeting('outsider',NOW-timedelta(days=1),course='other-course'); record('other','outsider','appealed','other')
    assert data(world,'flagged')['flagged']['appealed'] == 1
    row.status='rejected'; db.flush()
    assert data(world,'flagged')['flagged']['total'] == 0

def test_latest_duplicate_policy(world):
    # Database uniqueness prevents duplicate retries inflating the metric.
    db, meeting, record, _ = world
    meeting('one',datetime(2026,9,1)); record('one','one')
    result=data(world)['attendance']
    assert result['approved'] == result['eligible'] == 1
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError): record('retry','one')
    db.rollback()

def test_http_auth_course_scope_and_status_navigation(world):
    _, _, _, client = world
    def headers(id, role): return {'Authorization':'Bearer '+create_access_token(id,role)}
    assert client.get('/api/v1/stats/my-overview').status_code in (401,403)
    assert client.get('/api/v1/stats/my-overview',headers=headers('instructor','instructor')).status_code == 403
    h=headers('student','student')
    assert client.get('/api/v1/stats/my-overview?section=attendance&course_id=other-course',headers=h).status_code == 403
    result=client.get('/api/v1/stats/my-overview?section=flagged&student_id=other',headers=h)
    assert result.status_code == 200 and result.json()['flagged']['total'] == 0
    assert client.get('/api/v1/checkins/my-checkins?status=flagged,appealed&limit=50',headers=h).status_code == 200
    assert client.get('/api/v1/checkins/my-checkins?status=unknown',headers=h).status_code == 422

def test_http_filtered_records_include_only_selected_statuses(world):
    db, meeting, record, client = world
    for i, status in enumerate(['approved','flagged','appealed','pending','rejected']):
        meeting(str(i), NOW-timedelta(days=1)); record('r'+str(i),str(i),status)
    db.commit()
    headers={'Authorization':'Bearer '+create_access_token('student','student')}
    result=client.get('/api/v1/checkins/my-checkins?status=flagged,appealed&course_id=c&limit=50',headers=headers)
    assert result.status_code == 200
    assert {row['status'] for row in result.json()} == {'flagged','appealed'}

def test_missing_semester_configuration_is_explicit(world, monkeypatch):
    monkeypatch.delenv('SEMESTER_START_DATE')
    result=data(world)
    assert result['period']['error']
    assert result['attendance']['percentage'] is None
    assert result['today']['total'] == 0
