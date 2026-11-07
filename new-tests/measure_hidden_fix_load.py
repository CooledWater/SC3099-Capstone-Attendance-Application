"""Supplemental native load on private services with 100 distinct test clients.

The default deployment's rate limits stay enabled. This owned benchmark backend
explicitly trusts its loopback test proxy; login requests carry distinct source
addresses to model 100 clients. No inference, storage or authentication is mocked.
The unchanged assessment suite is run separately and retains its assertions.
"""
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hidden-tests'))
from harness import Runtime, World, Actor, PASSWORD, expect, image_b64
from test_stress import burst


class Config:
    def getoption(self, name):
        return {'--redis-server': shutil.which('redis-server') or '/private/tmp/saiv-hidden-redis/src/redis-server',
                '--postgres': '--postgres' in sys.argv, '--backend-only': False}.get(name)


class LoadRuntime(Runtime):
    def base_env(self):
        return {**super().base_env(), 'FORWARDED_ALLOW_IPS': '127.0.0.1'}


def measurement(rows):
    durations = sorted(row[1] for row in rows)
    return {'requests': len(rows), 'p95_seconds': round(durations[math.ceil(.95*len(rows))-1], 4),
            'status_counts': {str(status): sum(row[0] == status for row in rows) for status in {row[0] for row in rows}}}


def run():
    report = {'database': 'postgresql' if '--postgres' in sys.argv else 'sqlite',
              'clients': 100, 'login_proxy': 'explicitly trusted owned loopback; distinct forwarded clients',
              'inference': 'native dlib/MediaPipe/PAD; no physical presentation claim', 'workloads': {}}
    def record(name, rows):
        report['workloads'][name] = measurement(rows)
        print(name + ': ' + json.dumps(report['workloads'][name]), file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix='saiv-fix-load-') as directory:
        runtime = LoadRuntime(Path(directory), Config())
        try:
            service = runtime.backend()
            world = World(service)
            face = runtime.face()
            batch = [{'email': 'load-'+uuid.uuid4().hex+'@example.org', 'password': PASSWORD,
                      'full_name': 'Disposable load student', 'role': 'student'} for _ in range(100)]
            data = expect(service.api('POST', '/admin/users/bulk', world.admin, json={'users': batch}), 201)
            assert data['created'] == 100
            def login(index):
                return service.api('POST', '/auth/login', headers={'X-Forwarded-For': '198.51.100.'+str(index+1)},
                                   json={'email': batch[index]['email'], 'password': PASSWORD})
            # Provisioning (including hash creation, enrollment and one login per
            # client) is outside measured windows, as in the assessment harness.
            actors = []
            for index in range(100):
                body = expect(login(index), 200)
                actors.append(Actor(body['user']['id'], batch[index]['email'], 'student', body['access_token'], body['refresh_token']))
                expect(service.api('PUT', '/users/me', actors[-1], json={'camera_consent': True, 'geolocation_consent': True}), 200)
            runtime.clear_limits(service)
            rows = burst(login)
            assert all(row[0] == 200 for row in rows)
            assert len({row[2].json()['refresh_token'] for row in rows}) == 100
            record('100_distinct_client_logins', rows)
            runtime.clear_limits(service)
            rows = burst(lambda index: service.api('GET', '/users/me', actors[index]))
            assert all(row[0] == 200 and row[2].json()['id'] == actors[index].id for index, row in enumerate(rows))
            record('100_profile_reads', rows)
            image = image_b64()
            reference = expect(face.request('POST', '/face/enroll', json={'user_id': 'load-reference', 'image': image, 'camera_consent': True}), 201)['face_template_hash']
            rows = burst(lambda _: face.request('POST', '/face/verify', json={'image': image, 'reference_template_hash': reference}))
            assert all(row[0] == 200 and row[2].json()['match_passed'] is True for row in rows)
            record('100_native_comparisons', rows)
            course = world.course()
            meeting = world.session(course, actors[0], require_liveness_check=True, require_face_match=True)
            for actor in actors:
                world.enroll_face(actor, image)
            for actor in actors[1:]:
                world.enroll(course, actor)
            runtime.clear_limits(service)
            rows = burst(lambda index: world.checkin(meeting, actors[index], liveness_challenge_response=image))
            record('100_native_checkins', rows)
            stored = service.rows('checkins', session_id=meeting['id'])
            assert all(row[0] == 201 for row in rows)
            assert len(stored) == len({row['student_id'] for row in stored}) == 100
            assert all(row['liveness_passed'] is not None and row['face_match_passed'] is not None for row in stored)
            for row in stored:
                actions = [event['action'] for event in service.rows('audit_logs', resource_id=row['id'])]
                assert len(actions) == 2 and 'checkin_attempted' in actions
            runtime.clear_limits(service)
            duplicate_meeting = world.session(actor=actors[0])
            rows = burst(lambda _: world.checkin(duplicate_meeting, actors[0]))
            codes = [row[0] for row in rows]
            assert codes.count(201) == 1 and codes.count(400) == 9 and codes.count(429) == 90
            assert len(service.rows('checkins', session_id=duplicate_meeting['id'])) == 1
            record('100_duplicate_attempts_with_limits', rows)
            runtime.clear_limits(service)
            def mixed(index):
                return service.request('GET', '/health') if index % 5 == 0 else service.api('GET', '/users/me', actors[index])
            rows = burst(mixed)
            assert all(row[0] == 200 for row in rows)
            record('health_during_mixed_reads', [row for index, row in enumerate(rows) if index % 5 == 0])
            expect(service.request('GET', '/db-health'), 200)
            report['correctness'] = 'all workload and storage invariants passed'
        except Exception:
            diagnostics = os.getenv('SAIV_LOAD_DIAGNOSTICS')
            if diagnostics:
                destination = Path(diagnostics)
                destination.mkdir(parents=True, exist_ok=True)
                for owned_service in runtime.services:
                    shutil.copyfile(owned_service.log_path, destination / owned_service.log_path.name)
            report['correctness'] = 'failed; inspect workload status counts and owned diagnostics'
            print(json.dumps(report, indent=2), flush=True)
            raise
        finally:
            runtime.close()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run()
