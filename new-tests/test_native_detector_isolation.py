"""Native stage isolation and repeated mixed HTTP comparisons; no fake models."""
import base64
import asyncio
import os
import sys
import time
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module3-face-recognition'))
os.environ.setdefault('TELEMETRY_ENABLED', 'false')
os.environ.setdefault('JSON_LOGGING_ENABLED', 'false')
from app.detection import _dlib_locations, get_dlib_face_detector
from app.imaging import decode_base64_image
from app.main import app
from fastapi.testclient import TestClient
from app.admission import InferenceAdmission


def test_inference_queue_releases_cancelled_slots_and_leaves_health_available():
    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(scope, receive, send):
            if scope['path'] == '/health':
                return
            entered.set()
            await release.wait()
        admission = InferenceAdmission(handler, concurrency=1)
        inference = {'type': 'http', 'method': 'POST', 'path': '/face/verify'}
        first = asyncio.create_task(admission(inference, None, None))
        await entered.wait()
        await asyncio.wait_for(admission({'type': 'http', 'method': 'GET', 'path': '/health'}, None, None), .1)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        await asyncio.wait_for(admission(inference, None, None), .1)
    asyncio.run(check())


def encoded(name):
    return base64.b64encode((ROOT / 'sample_images' / name).read_bytes()).decode()


def test_each_worker_owns_one_detector_and_mixed_boxes_remain_stable():
    images = [decode_base64_image(encoded(name)) for name in ('obama.jpg', 'biden.jpg')]
    expected = [_dlib_locations(image) for image in images]
    assert [len(boxes) for boxes in expected] == [1, 1]
    gate = Barrier(4)
    def worker(index):
        detector = get_dlib_face_detector()
        gate.wait(timeout=30)
        for iteration in range(20):
            identity = (index + iteration) % 2
            assert get_dlib_face_detector() is detector
            assert _dlib_locations(images[identity]) == expected[identity]
        return detector
    with ThreadPoolExecutor(max_workers=4) as pool:
        detectors = list(pool.map(worker, range(4)))
    assert len({id(detector) for detector in detectors}) == 4


def test_ten_rounds_of_mixed_native_http_comparisons():
    same, different = encoded('obama.jpg'), encoded('biden.jpg')
    with TestClient(app) as client:
        enrollment = client.post('/face/enroll', json={'user_id': 'isolation', 'image': same, 'camera_consent': True})
        assert enrollment.status_code == 201
        reference = enrollment.json()['face_template_hash']
        def verify(expected):
            response = client.post('/face/verify', json={'image': same if expected else different, 'reference_template_hash': reference})
            assert response.status_code == 200
            assert response.json()['face_detected'] is True
            assert response.json()['match_passed'] is expected
        for expected in (True, False):
            verify(expected)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for _ in range(10):
                list(pool.map(verify, [True, False] * 4))


def test_health_remains_responsive_during_native_load_across_lifespans():
    image = encoded('obama.jpg')
    # Reopening the app also catches event-loop-bound queue state leaking from
    # one lifespan into the next.
    for _ in range(2):
        with TestClient(app) as client:
            enrollment = client.post('/face/enroll', json={'user_id': 'health-load', 'image': image, 'camera_consent': True})
            assert enrollment.status_code == 201
            reference = enrollment.json()['face_template_hash']
            def verify(_):
                response = client.post('/face/verify', json={'image': image, 'reference_template_hash': reference})
                assert response.status_code == 200 and response.json()['match_passed'] is True
            with ThreadPoolExecutor(max_workers=8) as pool:
                work = [pool.submit(verify, index) for index in range(32)]
                latencies = []
                for _ in range(20):
                    started = time.monotonic()
                    assert client.get('/health').status_code == 200
                    latencies.append(time.monotonic() - started)
                    time.sleep(.01)
                for task in work:
                    task.result()
            assert sorted(latencies)[math.ceil(.95*len(latencies))-1] < .5
