"""Container entry point for the documented isolated public-test command."""
import sys
import time
from pathlib import Path

import httpx
import pytest
from public_test_isolation import verify_target_configuration


def main():
    verify_target_configuration()
    deadline = time.monotonic() + 90
    with httpx.Client(timeout=3, trust_env=False) as client:
        for url in ('http://backend:8000/health', 'http://backend:8000/db-health', 'http://face:8001/health'):
            while True:
                try:
                    if client.get(url).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() >= deadline:
                    raise SystemExit('Public-test services did not become healthy; inspect Compose logs')
                time.sleep(0.5)
    Path('/results').mkdir(exist_ok=True)
    print('Disposable local PostgreSQL/Redis: quotas reset before each test, never during a test.', flush=True)
    args = sys.argv[1:] or ['tests/public', '-v']
    return pytest.main(['-p', 'public_test_isolation', '-p', 'no:cacheprovider',
                        '--junitxml=/results/public-tests.xml', *args])


if __name__ == '__main__':
    raise SystemExit(main())
