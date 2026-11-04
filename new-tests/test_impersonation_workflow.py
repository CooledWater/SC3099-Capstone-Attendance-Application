"""Impersonation assignments/reporting with no Docker, login or attendance mutations."""
import importlib.util
import json
from pathlib import Path
import sys
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'new-tests' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load('impersonation_setup_test', 'prepare_video_replay.py')
monitor = load('impersonation_monitor_test', 'monitor_phone_replay.py')


def setup_pair(tmp_path, request=None):
    return prepare.create_pair('http://mock', 'CREDENTIAL_MUST_NOT_PERSIST', str(uuid.uuid4()), 60,
        tmp_path / 'trial.json', request or (lambda *args, **kw: {**kw['body'], 'id': str(uuid.uuid4())}),
        trial_type='impersonation', control_account='wcstudent1@example.com', test_account='student1@gmail.com')


def event(session, challenge, stage, **values):
    return {'timestamp': '2026-11-02T08:00:00+00:00', 'diagnostic_id': str(uuid.uuid4()),
            'session_id': session, 'challenge_id': challenge, 'stage': stage, 'values': values}


def test_setup_assignments_match_session_names_and_never_enter_api_payload(tmp_path):
    payloads = []
    def request(*args, **kw):
        payloads.append(kw['body'])
        return {**kw['body'], 'id': str(uuid.uuid4())}
    config = setup_pair(tmp_path, request)
    assert config['trial_type'] == 'impersonation' and config['setup_complete'] is True
    assert 'pad_mode' not in config
    assert [s['label'] for s in config['sessions']] == ['genuine_control', 'impersonation_test']
    assert [s['account_email'] for s in config['sessions']] == ['wcstudent1@example.com', 'student1@gmail.com']
    assert [s['expected_identity_match'] for s in config['sessions']] == [True, False]
    for payload, session in zip(payloads, config['sessions']):
        assert payload['name'].startswith('Impersonation ' + session['label'])
        assert all(payload[flag] is True for flag in ('require_motion_check','require_liveness_check','require_face_match'))
        assert 'account_email' not in payload
        assert session['presenter'] == 'same_live_presenter'
    assert 'CREDENTIAL' not in (tmp_path / 'trial.json').read_text()
    monitor.validate_impersonation_config(config, 'video')


def test_partial_impersonation_setup_preserves_created_account_assignment(tmp_path):
    calls = []
    def request(*args, **kw):
        if calls:
            raise OSError('PRIVATE_ERROR')
        calls.append(kw['body'])
        return {**kw['body'], 'id':str(uuid.uuid4())}
    with pytest.raises(OSError):
        setup_pair(tmp_path, request)
    config = json.loads((tmp_path / 'trial.json').read_text())
    assert config['setup_complete'] is False and len(config['sessions']) == 1
    assert config['sessions'][0]['account_email'] == 'wcstudent1@example.com'
    assert config['sessions'][0]['label'] == 'genuine_control'
    assert 'PRIVATE_ERROR' not in json.dumps(config)
    with pytest.raises(ValueError):
        monitor.validate_impersonation_config(config,'video')


@pytest.mark.parametrize('control,test', [(None, None), ('same@account.test','SAME@account.test'),
                                         ('@aa','b@c'), ('a@b','name\n@domain.test'), ('a@b','x|y@z')])
def test_invalid_accounts_cannot_create_sessions_or_config(tmp_path, control, test):
    path = tmp_path / 'never.json'
    with pytest.raises(ValueError):
        prepare.create_pair('http://mock', 'secret', str(uuid.uuid4()), 60, path,
            request=lambda *a, **k: pytest.fail('API mutation before account validation'),
            trial_type='impersonation', control_account=control, test_account=test)
    assert not path.exists()


def test_cli_rejects_missing_accounts_before_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['prepare_video_replay.py', '--trial-type','impersonation',
                                     '--config', str(tmp_path / 'never.json')])
    monkeypatch.setattr('builtins.input', lambda *a: pytest.fail('Must validate before credentials'))
    with pytest.raises(SystemExit) as exc:
        prepare.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('change', ['incomplete','wrong_mode','wrong_role','same_account','wrong_expectation'])
def test_collector_rejects_ambiguous_assignments(tmp_path, change):
    config = setup_pair(tmp_path)
    mode = 'video'
    if change == 'incomplete': config['setup_complete'] = False
    if change == 'wrong_mode': mode = 'image'
    if change == 'wrong_role': config['sessions'][0]['label'] = 'real_face_control'
    if change == 'same_account': config['sessions'][1]['account_email'] = config['sessions'][0]['account_email']
    if change == 'wrong_expectation': config['sessions'][1]['expected_identity_match'] = True
    with pytest.raises(ValueError):
        monitor.validate_impersonation_config(config, mode)


def test_report_preserves_assignments_hamming_measurements_and_participant_notes(tmp_path):
    config = setup_pair(tmp_path)
    sid, cid = config['sessions'][1]['id'], str(uuid.uuid4())
    sample = {'frame_index': 0, 'timestamp_ms': 2, 'match_score': .7111, 'match_passed': True,
              'face_detected': True, 'hamming_evaluated': True, 'hamming_distance': 39,
              'hamming_fraction': 39 / 256, 'image': 'SECRET'}
    records = [event(sid, cid, 'motion_sequence', passed=True, face_match_score=.7111, diagnostics={
        'face_match_threshold': .7, 'simhash_bits': 256, 'face_match_hamming_fraction': .158203,
        'max_accepted_hamming_distance':40, 'max_hamming_distance':39, 'min_hamming_distance':39,
        'identity_comparisons':[sample], 'reference_template_hash':'SECRET'}),
        event(sid, cid, 'motion_verified', passed=True),
        event(sid, cid, 'attendance_committed', status='approved')]
    records = [monitor.decode_record(monitor.diag.PREFIX + json.dumps(r), {sid}) for r in records]
    report = tmp_path / 'report.md'
    report.write_text('Participant notes: keep these.\n')
    for _ in range(2): monitor.update_report(report, config, records, 'finished', 'video')
    text = report.read_text()
    assert 'Participant notes: keep these.' in text and text.count(monitor.BEGIN) == 1
    assert f'### impersonation_test — student1@gmail.com / {cid}' in text
    assert 'wcstudent1@example.com' in text and 'operator-provided' in text
    assert 'Identity acceptance contrary to the expected mismatch' in text
    assert 'Saved attendance status: approved' in text
    assert '| Maximum observed differing bits | 39 |' in text
    assert '| 0 | 2 | True | True | 39 | 0.15234375 | 0.7111 | True |' in text
    assert 'SECRET' not in text and 'phone_video' not in text and 'real_face_control' not in text


@pytest.mark.parametrize('reason,measured,expected', [
    ('identity_failed',True,'expected impersonation rejection'),
    ('identity_failed',False,'Inconclusive'), ('face_count',False,'Inconclusive'),
    ('passive_first_failed',True,'Inconclusive'), ('insufficient_blinks',True,'Inconclusive')])
def test_rejection_requires_measured_identity_evidence(reason, measured, expected):
    sid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    rows = [event(sid,cid,'motion_sequence',diagnostics={'reason':reason,
        'identity_comparisons':[{'hamming_evaluated':measured}]}), event(sid,cid,'motion_verified',passed=False)]
    assert expected in monitor.impersonation_classification(rows, {'expected_identity_match':False})


def test_bounded_comparison_projection_drops_sensitive_invalid_and_oversized_values():
    sample = {'frame_index':0, 'hamming_evaluated':True, 'hamming_distance':39,
              'hamming_fraction':39/256, 'match_score':float('nan'), 'match_passed':'SECRET',
              'template':'SECRET', 'landmarks':['SECRET']}
    clean = monitor.diag.sanitize({'identity_comparisons':[sample]*200, 'matcher_version':'SECRET'},
                                  monitor.diag.SEQUENCE_DETAILS)
    assert len(clean['identity_comparisons']) == 64
    assert 'SECRET' not in json.dumps(clean) and 'NaN' not in json.dumps(clean)
    assert 'match_score' not in clean['identity_comparisons'][0]
    assert len(json.dumps(clean)) < 32768


def test_legacy_logs_display_unknown_distances_without_inventing_them():
    lines = monitor.identity_table([{'stage':'motion_sequence','values':{
        'face_match_score':.7111,'diagnostics':{'face_match_threshold':.7}}}])
    text = '\n'.join(lines)
    assert '| Maximum observed differing bits | unknown |' in text
    assert 'cannot be recovered' in text
