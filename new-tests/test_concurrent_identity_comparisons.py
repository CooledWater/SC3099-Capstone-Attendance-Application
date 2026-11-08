"""Standalone Module 3 concurrency reproducer; no backend or database required.

Start the face service locally, then run from the repository root:
    python -m pytest new-tests/test_concurrent_identity_comparisons.py -v -s

Requires pytest and httpx; defaults to http://127.0.0.1:8001.
Override FACE_TEST_URL for another local face-service port/container hostname.
Uses sample_images/obama.jpg (same identity) and biden.jpg (different identity).
Expected: serial controls are correct, then eight comparisons at four-worker
concurrency stay correct and the face service remains healthy. A disconnection
is a failure too. Inspect the face-service terminal/log for a native crash.
This reproduces the mixed-identity test, not the 100-request latency test.
"""
import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx


def test_concurrent_identity_comparisons():
    root = Path(__file__).resolve().parents[1]
    same = base64.b64encode((root / 'sample_images/obama.jpg').read_bytes()).decode('ascii')
    different = base64.b64encode((root / 'sample_images/biden.jpg').read_bytes()).decode('ascii')
    url = os.environ.get('FACE_TEST_URL', 'http://127.0.0.1:8001').rstrip('/')
    with httpx.Client(base_url=url, timeout=60, trust_env=False) as client:
        health = client.get('/health')
        assert health.status_code == 200, 'Start a healthy local Module 3 face service first'
        enrollment = client.post('/face/enroll', json={
            'user_id': 'concurrency-reproducer-' + uuid4().hex,
            'image': same, 'camera_consent': True,
        })
        assert enrollment.status_code == 201, f'Enrollment returned HTTP {enrollment.status_code}'
        reference = enrollment.json()['face_template_hash']
        cases = [('same_identity', same, True), ('different_identity', different, False)]

        def verify(case):
            name, image, expected = case
            result = {'identity': name, 'expected_match': expected}
            try:
                response = client.post('/face/verify', json={
                    'image': image, 'reference_template_hash': reference,
                })
                result['http_status'] = response.status_code
                if response.status_code == 200:
                    body = response.json()
                    result.update(actual_match=body['match_passed'],
                                  match_score=body['match_score'], face_detected=body['face_detected'])
                    result['passed'] = body['match_passed'] is expected and body['face_detected'] is True
                else:
                    result['passed'] = False
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                result.update(passed=False, error_type=type(exc).__name__)
            return result

        serial = [verify(case) for case in cases]
        print('Serial controls:', json.dumps(serial))
        assert all(row['passed'] for row in serial), 'Serial identity controls failed; resolve these before concurrency'
        with ThreadPoolExecutor(max_workers=4) as pool:
            concurrent = list(pool.map(verify, cases * 4))
        print('Concurrent results:', json.dumps(concurrent))
        try:
            healthy_after = client.get('/health', timeout=5).status_code == 200
        except httpx.HTTPError:
            healthy_after = False
        failures = [row for row in concurrent if not row['passed']]
        assert not failures and healthy_after, (
            f'Concurrent identity failures={failures}; service_healthy_after={healthy_after}. '
            'Inspect Module 3 logs; no input images or template hashes are printed.'
        )
