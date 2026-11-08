"""Opt-in quota isolation for compose.public-tests.yml; never application middleware."""
import os
from urllib.parse import urlsplit

import pytest
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def verify_target_configuration():
    """Reject ordinary application URLs, missing opt-in, and renamed targets."""
    if os.environ.get('SAIV_PUBLIC_TEST_ISOLATION') != '1':
        raise RuntimeError('Quota isolation requires the disposable public-test Compose environment')
    database = make_url(os.environ['DATABASE_URL'])
    cache = urlsplit(os.environ['REDIS_URL'])
    backend = urlsplit(os.environ['TEST_BACKEND_URL'])
    face = urlsplit(os.environ['TEST_FACE_URL'])
    if not (database.get_backend_name() == 'postgresql' and database.host == 'db'
            and database.port == 5432 and database.database == 'public_tests'
            and database.username == 'public_test'
            and cache.scheme == 'redis' and cache.hostname == 'redis'
            and cache.port == 6379 and cache.path == '/0'
            and backend.scheme == 'http' and backend.hostname == 'backend' and backend.port == 8000
            and not backend.username and backend.path in ('', '/')
            and face.scheme == 'http' and face.hostname == 'face' and face.port == 8001):
        raise RuntimeError('Refusing quota reset outside the dedicated local public-test targets')


def pytest_configure(config):
    verify_target_configuration()
    if hasattr(config, 'workerinput') or config.getoption('numprocesses', default=0):
        raise pytest.UsageError('Run quota-isolated public tests without pytest-xdist')


@pytest.fixture(scope='session')
def _owned_public_test_redis():
    verify_target_configuration()
    engine = create_engine(os.environ['DATABASE_URL'])
    cache = redis.Redis.from_url(os.environ['REDIS_URL'], socket_connect_timeout=5, socket_timeout=5)
    try:
        with engine.connect() as connection:
            database, role = connection.execute(text('SELECT current_database(), current_user')).one()
        if database != 'public_tests' or role != 'public_test':
            raise RuntimeError('Refusing quota reset: database ownership check failed')
        cache.ping()
        yield cache
    finally:
        cache.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def public_test_quota_window(_owned_public_test_redis):
    """Fresh allowance before each test's fixtures; no resets during the test."""
    keys = list(_owned_public_test_redis.scan_iter(match='saiv:limit:*'))
    if keys:
        _owned_public_test_redis.delete(*keys)
    # Refresh-token revocation keys, test data, application limits and assertions survive.
    yield
