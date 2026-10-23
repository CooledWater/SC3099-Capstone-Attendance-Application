"""Isolated security contracts; no Supabase or real image data is used."""
import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(prefix='saiv-security-', suffix='.db')
os.environ['JWT_SECRET'] = 'isolated-security-audit-secret-not-production'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'module2-backend'))
from app import security
from app.main import app
from app.schemas import CourseCreate, SessionCreate, CheckInCreate, UserRegister
from app.database import SessionLocal
from app.models import User, Course, Session, Enrollment

class MemorySecurityStore:
    def __init__(self): self.values = {}; self.lock = threading.Lock()
    def eval(self, script, count, key, seconds):
        with self.lock:
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]
    def exists(self, key): return key in self.values
    def set(self, key, value, nx=False, ex=None):
        with self.lock:
            if nx and key in self.values: return False
            self.values[key] = value
            return True

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('STRICT_SECURITY_MODE', 'false')
    store = MemorySecurityStore()
    monkeypatch.setattr(security, 'redis_client', lambda: store)
    with TestClient(app) as client: yield client, store

_counter = 0
def student(client):
    global _counter
    _counter += 1
    email = f'audit-{_counter}@example.com'
    response = client.post('/api/v1/auth/register', json={'email': email, 'password': 'StrongTest123!', 'full_name': 'Test Student'})
    assert response.status_code == 201, response.text
    login = client.post('/api/v1/auth/login', json={'email': email, 'password': 'StrongTest123!'})
    assert login.status_code == 200
    return response.json()['id'], login.json(), {'Authorization': 'Bearer '+login.json()['access_token']}

@pytest.mark.parametrize('field,value', [('venue_latitude',91), ('venue_longitude',-181), ('risk_threshold',1.1), ('risk_threshold',-.1), ('geofence_radius_meters',-1), ('risk_threshold',float('nan')), ('venue_latitude',float('inf'))])
def test_course_numeric_bounds(field, value):
    with pytest.raises(ValidationError): CourseCreate(code='A', name='A', semester='A', **{field:value})

@pytest.mark.parametrize('value', [-1, float('nan'), float('inf')])
def test_location_accuracy_is_finite_nonnegative(value):
    with pytest.raises(ValidationError): CheckInCreate(session_id='s', latitude=0, longitude=0, device_fingerprint='d', location_accuracy_meters=value)

def test_password_byte_limit_and_error_redaction(client):
    c,_=client
    secret='🔒'*30
    response=c.post('/api/v1/auth/register', json={'email':'a@example.com','password':secret,'full_name':'A'})
    assert response.status_code==422
    assert secret not in response.text and 'input' not in response.json()['detail'][0]

@pytest.mark.parametrize('role',['admin','instructor','ta'])
def test_strict_registration_cannot_escalate_privileges(client,monkeypatch,role):
    c,_=client;monkeypatch.setenv('STRICT_SECURITY_MODE','true')
    response=c.post('/api/v1/auth/register',json={'email':role+'@example.com','password':'StrongTest123!','full_name':'Test','role':role})
    assert response.status_code==403

def test_refresh_tokens_are_unique_rotated_and_replay_protected(client,monkeypatch):
    c,_=client;_,tokens,_=student(c);monkeypatch.setenv('STRICT_SECURITY_MODE','true')
    first=c.post('/api/v1/auth/refresh',json={'refresh_token':tokens['refresh_token']})
    assert first.status_code==200
    assert first.json()['refresh_token']!=tokens['refresh_token']
    assert c.post('/api/v1/auth/refresh',json={'refresh_token':tokens['refresh_token']}).status_code==401
    assert c.post('/api/v1/auth/refresh',json={'refresh_token':first.json()['refresh_token']}).status_code==200

def test_strict_logout_revokes_refresh_cookie(client,monkeypatch):
    c,_=client;_,tokens,_=student(c);monkeypatch.setenv('STRICT_SECURITY_MODE','true')
    assert c.post('/api/v1/auth/logout').status_code==200
    assert c.post('/api/v1/auth/refresh',json={'refresh_token':tokens['refresh_token']}).status_code==401

def test_strict_requires_consent_and_required_biometric_evidence(client,monkeypatch):
    c,_=client;uid,_,headers=student(c)
    with SessionLocal() as db:
        u=db.get(User,uid)
        course=Course(code='STRICT-'+uid[:8],name='Audit',semester='test',instructor_id=uid);db.add(course);db.flush()
        now=datetime.utcnow();s=Session(course_id=course.id,instructor_id=uid,name='Audit',status='active',scheduled_start=now-timedelta(minutes=1),scheduled_end=now+timedelta(hours=1),checkin_opens_at=now-timedelta(minutes=1),checkin_closes_at=now+timedelta(hours=1),require_liveness_check=True)
        db.add(s);db.flush();sid=s.id;db.add(Enrollment(course_id=course.id,student_id=uid));db.commit()
    payload={'session_id':sid,'latitude':0,'longitude':0,'device_fingerprint':'test'}
    monkeypatch.setenv('STRICT_SECURITY_MODE','true')
    assert c.post('/api/v1/checkins/',json=payload,headers=headers).status_code==403
    with SessionLocal() as db:
        u=db.get(User,uid);u.camera_consent=True;u.geolocation_consent=True;db.commit()
    assert c.post('/api/v1/checkins/',json=payload,headers=headers).status_code==400
    bad={**payload,'latitude':float('nan')}
    import json
    response=c.post('/api/v1/checkins/',content=json.dumps(bad),headers={**headers,'Content-Type':'application/json'})
    assert response.status_code==422

def test_rate_limit_is_atomic_at_boundary(client,monkeypatch):
    monkeypatch.setenv('STRICT_SECURITY_MODE','true')
    def attempt(_):
        try: security.enforce_rate_limit('test','same-user',10,60);return 200
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=25) as pool:results=list(pool.map(attempt,range(100)))
    assert results.count(200)==10 and results.count(429)==90

def test_strict_configuration_rejects_placeholder_secrets(monkeypatch):
    monkeypatch.setenv('STRICT_SECURITY_MODE','true');monkeypatch.setenv('JWT_SECRET','your-secret-key-change-in-production')
    with pytest.raises(RuntimeError):security.validate_settings()

@pytest.mark.parametrize('origin',['*','https://*.example.com','https://example.com/path'])
def test_cors_disallows_wildcards_and_paths(monkeypatch,origin):
    monkeypatch.setenv('CORS_ORIGINS',origin)
    with pytest.raises(RuntimeError):security.cors_origins()

def test_security_store_outage_fails_closed(client,monkeypatch):
    monkeypatch.setenv('STRICT_SECURITY_MODE','true')
    def unavailable():raise security.redis.ConnectionError('offline')
    monkeypatch.setattr(security,'redis_client',unavailable)
    with pytest.raises(HTTPException) as caught:security.enforce_rate_limit('test','user',10,60)
    assert caught.value.status_code==503


def test_concurrent_duplicate_checkins_return_one_record(client):
    c,_=client;uid,_,headers=student(c)
    with SessionLocal() as db:
        course=Course(code='RACE-'+uid[:8],name='Race',semester='test',instructor_id=uid);db.add(course);db.flush()
        now=datetime.utcnow();session=Session(course_id=course.id,instructor_id=uid,name='Race',status='active',scheduled_start=now-timedelta(minutes=1),scheduled_end=now+timedelta(hours=1),checkin_opens_at=now-timedelta(minutes=1),checkin_closes_at=now+timedelta(hours=1),require_liveness_check=False)
        db.add(session);db.flush();sid=session.id;db.add(Enrollment(course_id=course.id,student_id=uid));db.commit()
    payload={'session_id':sid,'latitude':0,'longitude':0,'device_fingerprint':'audit'}
    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses=list(pool.map(lambda _:c.post('/api/v1/checkins/',json=payload,headers=headers).status_code,range(10)))
    assert statuses.count(201)==1 and statuses.count(400)==9
