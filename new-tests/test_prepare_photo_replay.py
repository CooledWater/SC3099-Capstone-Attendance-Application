import importlib.util
import json
from pathlib import Path
import uuid

import pytest

spec = importlib.util.spec_from_file_location('prepare_photo_replay', Path(__file__).with_name('prepare_photo_replay.py'))
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_setup_explicitly_creates_photo_sessions_and_never_saves_token(tmp_path):
    calls = []
    def request(base, path, *, token, body):
        calls.append((path, body))
        return {**body, 'id': str(uuid.uuid4())}
    path = tmp_path / 'run.json'
    config = prepare.create_pair('http://test', 'SECRET_TOKEN', str(uuid.uuid4()), 60, path, request)
    assert [s['label'] for s in config['sessions']] == ['real_face_control', 'phone_screen']
    assert len(calls) == 2
    for endpoint, payload in calls:
        assert endpoint == '/sessions/'
        assert payload['require_motion_check'] is False
        assert payload['require_liveness_check'] is payload['require_face_match'] is True
        assert payload['scheduled_start'] < payload['scheduled_end']
    assert 'SECRET' not in path.read_text()


def test_setup_wont_overwrite_previous_trials(tmp_path):
    path = tmp_path / 'existing.json'
    path.write_text('keep this')
    with pytest.raises(FileExistsError):
        prepare.create_pair('http://test', 'SECRET', str(uuid.uuid4()), 60, path,
                            lambda *a, **k: pytest.fail('Must not create sessions'))
    assert path.read_text() == 'keep this'


def test_partial_creation_is_preserved_for_operator(tmp_path):
    calls = 0
    def request(base, path, *, token, body):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('network error')
        return {**body, 'id': str(uuid.uuid4())}
    path = tmp_path / 'partial.json'
    with pytest.raises(OSError):
        prepare.create_pair('http://test', 'SECRET', str(uuid.uuid4()), 60, path, request)
    assert len(json.loads(path.read_text())['sessions']) == 1
