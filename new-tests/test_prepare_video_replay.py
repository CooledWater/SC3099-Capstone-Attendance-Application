"""Video trial setup uses real API contracts with all network calls replaced."""
from datetime import datetime, timedelta
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
import uuid
from urllib.error import HTTPError

import pytest

spec = importlib.util.spec_from_file_location('prepare_video_replay', Path(__file__).with_name('prepare_video_replay.py'))
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_pair_has_matched_motion_policy_timing_and_monitor_config(tmp_path, capsys):
    calls = []
    course_id = str(uuid.uuid4())
    def request(base, path, *, token, body):
        calls.append((base, path, token, body))
        return {**body, 'id': str(uuid.uuid4())}
    path = tmp_path / 'run.json'
    config = prepare.create_pair('http://test', 'SECRET_TOKEN', course_id, 60, path, request)
    assert config == json.loads(path.read_text())
    assert config['setup_complete'] is True
    assert config['pad_mode'] == 'enforce'
    assert [session['label'] for session in config['sessions']] == ['real_face_control', 'phone_video']
    assert len({session['id'] for session in config['sessions']}) == 2
    since = datetime.fromisoformat(config['monitor_since'])
    assert since.utcoffset() == timedelta(0)
    assert len(calls) == 2
    for base, endpoint, token, payload in calls:
        assert (base, endpoint, token) == ('http://test', '/sessions/', 'SECRET_TOKEN')
        assert payload['course_id'] == course_id
        assert all(payload[flag] is True for flag in (
            'require_motion_check', 'require_liveness_check', 'require_face_match'))
        assert datetime.fromisoformat(payload['scheduled_start']) == since + timedelta(minutes=1)
        assert datetime.fromisoformat(payload['scheduled_end']) == since + timedelta(minutes=61)
        assert datetime.fromisoformat(payload['checkin_opens_at']) == since
        assert payload['checkin_closes_at'] == payload['scheduled_end']
        assert not any(key in payload for key in ('venue_name', 'venue_latitude', 'venue_longitude',
                                                  'geofence_radius_meters', 'risk_threshold'))
    assert 'SECRET' not in path.read_text() + capsys.readouterr().out


def test_existing_config_is_preserved_before_any_session_creation(tmp_path):
    path = tmp_path / 'existing.json'
    path.write_text('keep this')
    with pytest.raises(FileExistsError):
        prepare.create_pair('http://test', 'SECRET', str(uuid.uuid4()), 60, path,
                            lambda *a, **k: pytest.fail('Must not create sessions'))
    assert path.read_text() == 'keep this'


@pytest.mark.parametrize('failed_call', [1, 2])
def test_partial_creation_preserves_successful_ids_and_incomplete_state(tmp_path, failed_call):
    ids = []
    def request(base, endpoint, **kwargs):
        if len(ids) + 1 == failed_call:
            raise OSError('SECRET network error')
        ids.append(str(uuid.uuid4()))
        return {**kwargs['body'], 'id': ids[-1]}
    path = tmp_path / 'partial.json'
    with pytest.raises(OSError):
        prepare.create_pair('http://test', 'SECRET', str(uuid.uuid4()), 60, path, request)
    config = json.loads(path.read_text())
    assert config['setup_complete'] is False
    assert [item['id'] for item in config['sessions']] == ids
    assert 'SECRET' not in path.read_text()


@pytest.mark.parametrize('flag', ['require_motion_check', 'require_liveness_check', 'require_face_match'])
@pytest.mark.parametrize('value', [False, None, 1])
def test_wrong_or_missing_policy_stops_but_keeps_created_session_id(tmp_path, flag, value):
    sid = str(uuid.uuid4())
    def request(base, endpoint, **kwargs):
        result = {**kwargs['body'], 'id': sid}
        if value is None:
            result.pop(flag)
        else:
            result[flag] = value
        return result
    path = tmp_path / 'wrong-policy.json'
    with pytest.raises(ValueError, match='verification policy'):
        prepare.create_pair('http://test', 'SECRET', str(uuid.uuid4()), 60, path, request)
    config = json.loads(path.read_text())
    assert config['setup_complete'] is False
    assert [item['id'] for item in config['sessions']] == [sid]


def test_duplicate_returned_session_id_never_completes_pair(tmp_path):
    sid = str(uuid.uuid4())
    path = tmp_path / 'duplicate.json'
    with pytest.raises(ValueError, match='session ID'):
        prepare.create_pair('http://test', 'SECRET', str(uuid.uuid4()), 60, path,
                            lambda *a, **k: {**k['body'], 'id': sid})
    assert json.loads(path.read_text())['setup_complete'] is False


@pytest.mark.parametrize('explicit_course', [False, True])
def test_cli_authenticates_selects_course_and_creates_only_new_sessions(tmp_path, monkeypatch, capsys, explicit_course):
    course_id = str(uuid.uuid4())
    path = tmp_path / 'cli.json'
    calls = []
    inputs = iter(['teacher@example.com', '1'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))
    monkeypatch.setattr(prepare.getpass, 'getpass', lambda prompt: 'SECRET_PASSWORD')
    def request(base, endpoint, *, token=None, body=None):
        calls.append(endpoint)
        assert base == 'http://test'
        if endpoint == '/auth/login':
            assert body == {'email': 'teacher@example.com', 'password': 'SECRET_PASSWORD'}
            return {'access_token': 'SECRET_TOKEN'}
        assert token == 'SECRET_TOKEN'
        if endpoint.startswith('/courses/'):
            return {'items': [{'id': course_id, 'code': 'SC3099', 'name': 'Test course'}]}
        assert endpoint == '/sessions/'
        return {**body, 'id': str(uuid.uuid4())}
    monkeypatch.setattr(prepare, 'api_request', request)
    argv = ['prepare_video_replay.py', '--config', str(path), '--api-url', 'http://test']
    if explicit_course:
        argv += ['--course-id', course_id]
    monkeypatch.setattr(sys, 'argv', argv)
    prepare.main()
    assert calls == ['/auth/login'] + ([] if explicit_course else ['/courses/?limit=100']) + ['/sessions/'] * 2
    assert json.loads(path.read_text())['setup_complete'] is True
    assert 'SECRET' not in path.read_text() + capsys.readouterr().out


@pytest.mark.parametrize('extra', [['--minutes', '4'], ['--minutes', '241'], ['--course-id', 'not-a-uuid']])
def test_invalid_arguments_fail_before_credentials_or_network(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(sys, 'argv', ['prepare_video_replay.py', '--config', str(tmp_path / 'run.json'), *extra])
    monkeypatch.setattr('builtins.input', lambda *a: pytest.fail('Must not request credentials'))
    with pytest.raises(SystemExit) as exc:
        prepare.main()
    assert exc.value.code == 2


def test_cli_redacts_http_error_body_and_server_reason(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['prepare_video_replay.py', '--config', str(tmp_path / 'run.json')])
    monkeypatch.setattr('builtins.input', lambda prompt: 'teacher@example.com')
    monkeypatch.setattr(prepare.getpass, 'getpass', lambda prompt: 'SECRET_PASSWORD')
    def fail(*args, **kwargs):
        raise HTTPError('http://test', 403, 'SECRET_REASON', {}, BytesIO(b'SECRET_BODY'))
    monkeypatch.setattr(prepare, 'api_request', fail)
    with pytest.raises(SystemExit) as exc:
        prepare.main()
    output = capsys.readouterr()
    assert exc.value.code == 1
    assert 'HTTP 403' in output.err
    assert 'SECRET' not in output.out + output.err


def test_http_transport_uses_bearer_auth_json_and_timeout(monkeypatch):
    calls = []
    def open_response(request, *, timeout):
        calls.append((request, timeout))
        return BytesIO(b'{"id": "response"}')
    monkeypatch.setattr(prepare, 'urlopen', open_response)
    assert prepare.api_request('http://test/', '/sessions/', token='TOKEN', body={'name': 'test'}) == {'id': 'response'}
    request, timeout = calls[0]
    assert request.full_url == 'http://test/api/v1/sessions/'
    assert request.get_method() == 'POST'
    assert request.get_header('Authorization') == 'Bearer TOKEN'
    assert json.loads(request.data) == {'name': 'test'}
    assert timeout == 30
    prepare.api_request('http://test', '/courses/?limit=100', token='TOKEN')
    assert calls[1][0].get_method() == 'GET'
