"""Pinned native pose output and v2 static-replay rejection, without camera claims."""
import base64
from io import BytesIO
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'module3-face-recognition'))
from app import main, motion
from app.random_motion import yaw_degrees


def photo():
    with Image.open(ROOT/'sample_images/obama.jpg') as source:
        source.thumbnail((480, 480))
        buffer = BytesIO(); source.convert('RGB').save(buffer, format='JPEG', quality=70)
    return base64.b64encode(buffer.getvalue()).decode()


def test_pinned_model_outputs_finite_pose_and_horizontal_mirroring_reverses_yaw():
    image = motion.decode_base64_image(photo())
    yaws = []
    for pixels in (image, np.ascontiguousarray(image[:, ::-1])):
        mp, tracker = motion._create_landmarker()
        with tracker:
            output = tracker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=pixels), 0)
        assert len(output.face_landmarks) == len(output.facial_transformation_matrixes) == 1
        yaws.append(yaw_degrees(output.facial_transformation_matrixes[0]))
    assert yaws[0] * yaws[1] < 0
    assert abs(yaws[0] + yaws[1]) < 5  # Approximate symmetry, not an accuracy calibration.


def test_real_models_reject_a_static_photo_for_random_motion():
    encoded = photo()
    with TestClient(main.app) as client:
        enrolled = client.post('/face/enroll', json={'user_id': 'random-motion-native', 'image': encoded, 'camera_consent': True})
        assert enrolled.status_code == 201, enrolled.text
        response = client.post('/liveness/sequence', json={
            'reference_template_hash': enrolled.json()['face_template_hash'],
            'challenge': dict(version=2, blink_target=1, turn_direction='left', first_action='head_turn'),
            'frames': [{'image': encoded, 'timestamp_ms': index*80} for index in range(20)],
        })
    assert response.status_code == 200, response.text
    assert response.json()['passed'] is False
    assert response.json()['challenge_version'] == 2
    assert response.json()['turn_passed'] is False
    assert encoded[:100] not in response.text
