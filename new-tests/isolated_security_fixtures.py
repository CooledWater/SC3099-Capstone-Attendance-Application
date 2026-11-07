"""Reset rate buckets between independent scenarios in the owned test runner.

Rates remain enabled inside every test. Refresh-use/revocation keys are retained.
"""
import os

import redis


def pytest_runtest_setup(item):
    store = redis.Redis.from_url(os.environ['SAIV_TEST_OWNED_REDIS_URL'])
    try:
        assert store.info('server')['process_id'] == int(os.environ['SAIV_TEST_OWNED_REDIS_PID'])
        keys = list(store.scan_iter('saiv:limit:*'))
        if keys:
            store.delete(*keys)
    finally:
        store.close()
