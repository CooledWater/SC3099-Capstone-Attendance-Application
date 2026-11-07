"""Run existing public/backend tests on private services, SQLite and real Redis.

Usage: python new-tests/run_hidden_fix_regressions.py [pytest targets/options]
No live URL or root .env database is accepted. Rate keys reset between scenarios,
never during one scenario. Native tests should run separately (both apps are
named app). The physical corpus is not provisioned by this runner.
"""
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hidden-tests'))
from harness import Runtime


class Config:
    def getoption(self, name):
        return {'--redis-server': os.getenv('SAIV_TEST_REDIS_SERVER') or shutil.which('redis-server') or '/private/tmp/saiv-hidden-redis/src/redis-server',
                '--postgres': False, '--backend-only': False}.get(name)


with tempfile.TemporaryDirectory(prefix='saiv-fix-regressions-') as directory:
    runtime = Runtime(Path(directory), Config())
    try:
        backend = runtime.backend()
        face = runtime.face()
        env = {**backend.env,
               'TEST_BACKEND_URL': backend.url, 'API_BASE_URL': backend.url, 'TEST_API_URL': backend.url,
               'TEST_FACE_URL': face.url, 'SAIV_TEST_OWNED_REDIS_URL': backend.env['REDIS_URL'],
               'SAIV_TEST_OWNED_REDIS_PID': str(runtime.redis_process.pid),
               'PYTHONPATH': os.pathsep.join(str(ROOT / path) for path in ('tests', 'new-tests', 'module2-backend'))}
        # Do not inherit an old regression script's shared-database override.
        # The sole alternative target is the dedicated DB in our Compose project.
        device_database = 'postgresql://hidden:hidden-disposable-password@hidden-db:5432/hidden_device_regressions'
        for name in list(env):
            if name != 'DATABASE_URL' and name.endswith('DATABASE_URL'):
                if (name == 'DEVICE_TEST_DATABASE_URL' and env.get('SAIV_HIDDEN_COMPOSE') == '1'
                        and env[name] == device_database):
                    continue
                env.pop(name)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'isolated_security_fixtures',
                                 '-q', *(sys.argv[1:] or ['tests/public'])], env=env, cwd=ROOT)
    finally:
        runtime.close()
sys.exit(result.returncode)
