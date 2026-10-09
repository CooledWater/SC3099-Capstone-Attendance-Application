"""Real-model smoke tests for the additive sequence endpoint (run with Module 3 dependencies)."""
import base64
from io import BytesIO
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'module3-face-recognition'))
from app.main import app


def test_real_model_rejects_static_photo_sequence():
    with Image.open(ROOT/'sample_images'/'obama.jpg') as photo:
        photo.thumbnail((480,480))
        buffer = BytesIO(); photo.convert('RGB').save(buffer, format='JPEG', quality=70)
        encoded = base64.b64encode(buffer.getvalue()).decode()
    with TestClient(app) as client:
        enrolled = client.post('/face/enroll', json={'user_id':'motion-native-smoke', 'image':encoded, 'camera_consent':True})
        assert enrolled.status_code == 201, enrolled.text
        response = client.post('/liveness/sequence', json={
            'reference_template_hash':enrolled.json()['face_template_hash'],
            'frames':[{'image':encoded, 'timestamp_ms':i*80} for i in range(20)],
        })
        assert response.status_code == 200, response.text
        assert response.json()['passed'] is False
        assert response.json()['blink_count'] == 0
        assert encoded[:100] not in response.text


@pytest.mark.parametrize('corrupt', [False, True])
def test_sequence_model_failure_returns_unavailable(monkeypatch, tmp_path, corrupt):
    from app import motion
    model = tmp_path / 'face_landmarker.task'
    if corrupt:
        model.write_bytes(b'not a valid model')
    monkeypatch.setattr(motion, 'LANDMARKER_MODEL', model)
    with TestClient(app) as client:
        response = client.post('/liveness/sequence', json={
            'reference_template_hash': 'a'*64,
            'frames': [{'image': 'aGVsbG8=', 'timestamp_ms': i*80} for i in range(20)],
        })
    assert response.status_code == 503
    assert response.json() == {'detail': 'Face models are unavailable'}
    assert 'aGVsbG8=' not in response.text
    assert str(model) not in response.text
