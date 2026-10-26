"""Isolated new-password validation and existing-account compatibility checks."""
import os
import sys
import tempfile
import uuid
from pathlib import Path
import pytest
from pydantic import ValidationError
os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(prefix='saiv-password-', suffix='.db')
os.environ['JWT_SECRET'] = 'isolated-password-test-secret'
os.environ['STRICT_SECURITY_MODE'] = 'false'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'module2-backend'))
from app.main import app, hash_password
from app.schemas import UserRegister, UserLogin
from app.invitations import CompleteRequest
from app.database import SessionLocal
from app.models import User
from fastapi.testclient import TestClient

@pytest.mark.parametrize('password', ['shortA!', 'lowercase!', 'UPPERCASE!', 'Password123', 'Password ', 'Aa!' + 'é' * 35])
def test_registration_and_invitation_reject_weak_passwords(password):
    with pytest.raises(ValidationError):
        UserRegister(email='a@x.io', full_name='Student', password=password)
    with pytest.raises(ValidationError):
        CompleteRequest(token='token', password=password)

@pytest.mark.parametrize('password', ['Password!', 'StrongPass#123', 'Abcdefg!'])
def test_valid_passwords_do_not_require_digits_or_change_email_rules(password):
    assert UserRegister(email='a@x.io', full_name='Student', password=password).password == password
    assert CompleteRequest(token='token', password=password).password == password


def test_new_credential_http_validation_does_not_echo_passwords():
    with TestClient(app) as client:
        for path, payload in [('/api/v1/auth/register', {'email': 'a@x.io', 'full_name': 'Student'}), ('/api/v1/auth/invitations/complete', {'token': 'not-a-token'})]:
            weak = 'SecretPassword123'
            response = client.post(path, json={**payload, 'password': weak})
            assert response.status_code == 422, response.text
            assert weak not in response.text
        response = client.post('/api/v1/auth/register', json={'email': f'{uuid.uuid4()}@example.com', 'full_name': 'Student', 'password': 'StrongPass!'})
        assert response.status_code == 201, response.text


def test_existing_passwords_still_login():
    email = f'{uuid.uuid4()}@example.com'
    password = 'legacy123'
    assert UserLogin(email=email, password=password).password == password
    with SessionLocal() as db:
        db.add(User(email=email, full_name='Existing student', role='student', hashed_password=hash_password(password)))
        db.commit()
    with TestClient(app) as client:
        response = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
        assert response.status_code == 200, response.text
