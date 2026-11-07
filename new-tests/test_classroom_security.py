"""Default-profile Redis outage with real owned services; no mocked store."""
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hidden-tests'))
from harness import Runtime, World, PASSWORD, expect


class Config:
    def getoption(self, name):
        return {'--redis-server': shutil.which('redis-server') or '/private/tmp/saiv-hidden-redis/src/redis-server',
                '--postgres': False, '--backend-only': True}.get(name)


def test_classroom_profile_preserves_role_choices_and_blocks_redis_outage(tmp_path):
    runtime = Runtime(tmp_path, Config())
    try:
        world = World(runtime.backend(strict=False))
        service = world.service
        actor = world.student
        for role in ('student', 'ta', 'instructor', 'admin'):
            expect(service.api('POST', '/auth/register', json={
                'email': role+'@classroom-fix.example.org', 'full_name': 'Test',
                'password': PASSWORD, 'role': role,
            }), 201)
        runtime.redis_process.terminate()
        runtime.redis_process.wait(timeout=5)
        expect(service.api('GET', '/users/me', actor), 503)
        expect(service.api('POST', '/auth/login', json={'email': actor.email, 'password': PASSWORD}), 503)
        expect(service.api('POST', '/auth/refresh', json={'refresh_token': actor.refresh}), 503)
        expect(service.api('POST', '/auth/logout', headers={'Cookie': 'saiv_refresh_token='+actor.refresh}), 503)
        expect(service.api('POST', '/auth/register', json={
            'email': 'outage@classroom-fix.example.org', 'full_name': 'Test', 'password': PASSWORD,
        }), 503)
        expect(service.request('GET', '/health'), 200)
    finally:
        runtime.close()
