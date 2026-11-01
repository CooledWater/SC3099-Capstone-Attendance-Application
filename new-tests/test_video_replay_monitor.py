"""Video reports distinguish biometric outcomes from attendance and outages."""
import importlib.util
import json
import signal
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace as N

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('video_replay_monitor', ROOT / 'new-tests/monitor_phone_replay.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def row(sid, cid, stage, second=0, **values):
    return {'timestamp': f'2026-10-30T02:00:{second:02d}+00:00', 'session_id': sid,
            'challenge_id': cid, 'diagnostic_id': str(uuid.uuid4()), 'stage': stage, 'values': values}


def test_motion_reader_filters_nested_details_and_invalid_correlation():
    sid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    record = row(sid, cid, 'motion_sequence', passed=False, diagnostics={
        'reason': 'passive_first_failed', 'first_frame': {'evaluated': True,
            'details': {'depth_score': .6, 'mesh_plausibility_score': .7, 'image': 'SECRET',
                        'pre_gate_liveness_score': float('inf'), 'depth_passed': 'SECRET'}},
        'last_frame': {'evaluated': False}, 'frames': ['SECRET']})
    line = monitor.diag.PREFIX + json.dumps(record)
    clean = monitor.decode_record(line, {sid})
    assert clean['challenge_id'] == cid
    assert clean['values']['diagnostics']['first_frame']['details'] == {'depth_score': .6, 'mesh_plausibility_score': .7}
    assert 'SECRET' not in json.dumps(clean)
    assert monitor.decode_record(line, {str(uuid.uuid4())}) is None
    record['challenge_id'] = 'SECRET'
    assert monitor.decode_record(monitor.diag.PREFIX + json.dumps(record), {sid}) is None


def test_video_completion_requires_commit_after_success_but_not_after_rejection():
    sid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    issued = row(sid, cid, 'motion_challenge_issued')
    accepted = row(sid, cid, 'motion_verified', 1, passed=True)
    rejected = row(sid, cid, 'motion_verified', 1, passed=False)
    committed = row(sid, cid, 'attendance_committed', 2, status='approved')
    assert monitor.completed_sessions([issued, accepted], 'video') == set()
    assert 'not confirmed' in monitor.classification([issued, accepted], 'video')
    assert monitor.completed_sessions([issued, accepted, committed], 'video') == {sid}
    assert 'saved attendance status: approved' in monitor.classification([issued, accepted, committed], 'video')
    assert monitor.completed_sessions([issued, rejected], 'video') == {sid}
    assert 'Server rejected' in monitor.classification([issued, rejected], 'video')
    failed = row(sid, cid, 'motion_request_failed', 2, http_status=503)
    assert monitor.completed_sessions([issued, failed], 'video') == {sid}
    assert 'Inconclusive' in monitor.classification([issued, failed], 'video')
    # A duplicate verification request's 409 must not finish an accepted trial.
    assert monitor.completed_sessions([issued, accepted, failed], 'video') == set()


def test_retry_supersedes_old_failure_and_cannot_borrow_its_attendance():
    sid, old, new = (str(uuid.uuid4()) for _ in range(3))
    records = [row(sid, old, 'motion_challenge_issued'), row(sid, old, 'motion_verified', 1, passed=False),
               row(sid, new, 'motion_challenge_issued', 2), row(sid, old, 'motion_request_failed', 3)]
    assert monitor.completed_sessions(records, 'video') == set()
    records += [row(sid, new, 'motion_verified', 4, passed=True),
                row(sid, old, 'attendance_committed', 5, status='approved')]
    assert monitor.completed_sessions(records, 'video') == set()
    records += [row(sid, new, 'attendance_committed', 6, status='flagged')]
    assert monitor.completed_sessions(records, 'video') == {sid}


def test_video_report_groups_by_challenge_and_marks_unevaluated_frames(tmp_path):
    sid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    path = tmp_path / 'report.md'
    path.write_text('# Video trial\n\nParticipant observations: preserve these.\n')
    records = [row(sid, cid, 'motion_challenge_issued'), row(sid, cid, 'motion_sequence', 1, diagnostics={
        'reason': 'passive_first_failed', 'first_frame': {'evaluated': True, 'liveness_score': 0.,
        'details': {'depth_score': .6, 'mesh_plausibility_score': .7, 'depth_passed': False, 'mesh_passed': False}},
        'last_frame': {'evaluated': False}}), row(sid, cid, 'motion_verified', 2, passed=False)]
    config = {'sessions': [{'id': sid, 'label': 'phone_video'}]}
    monitor.update_report(path, config, records, 'finished', 'video')
    monitor.update_report(path, config, records, 'finished', 'video')
    report = path.read_text()
    assert 'Participant observations: preserve these.' in report
    assert report.count(f'### phone_video / {cid}') == 1
    assert report.count(monitor.BEGIN) == 1
    assert '| first_frame | yes | 0.6 | 0.7 | 0.0 | False / False |' in report
    assert '| last_frame | not evaluated | — |' in report
    assert 'passive_first_failed' in report
    assert 'Server rejected' in report
    assert 'saved attendance status' not in report


@pytest.fixture
def monitor_run(monkeypatch, tmp_path):
    sessions = [{'id': str(uuid.uuid4()), 'label': label} for label in ('real_face_control', 'phone_video')]
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'monitor_since': '2026-10-30T02:00:00+00:00', 'sessions': sessions}))
    report = tmp_path / 'report.md'
    monkeypatch.setattr(sys, 'argv', ['monitor_phone_replay.py', '--mode', 'video', '--config', str(config),
                                    '--report', str(report)])
    commands = []
    def command(args, **kwargs):
        commands.append((args, kwargs))
        return N(returncode=0)
    monkeypatch.setattr(monitor.subprocess, 'run', command)
    state = {'lines': [], 'terminated': False}
    class Process:
        @property
        def stdout(self):
            return iter(state['lines'])
        def terminate(self):
            state['terminated'] = True
        def wait(self, timeout):
            return 0
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *args, **kwargs: Process())
    return sessions, report, commands, state


def test_monitor_finishes_control_commit_and_replay_failure_then_disables_both_services(monitor_run):
    sessions, report, commands, state = monitor_run
    records = []
    for index, session in enumerate(sessions):
        cid = str(uuid.uuid4())
        records += [row(session['id'], cid, 'motion_challenge_issued'),
                    row(session['id'], cid, 'motion_verified', 1, passed=index == 0)]
        if index == 0:
            records += [row(session['id'], cid, 'attendance_committed', 2, status='approved')]
    state['lines'] = [monitor.diag.PREFIX + json.dumps(r) + '\n' for r in records]
    previous = signal.getsignal(signal.SIGTERM)
    monitor.main()
    assert signal.getsignal(signal.SIGTERM) == previous
    assert 'all sessions reached terminal motion outcomes' in report.read_text()
    assert 'diagnostics disabled' in report.read_text()
    assert state['terminated']
    args, kwargs = commands[0]
    assert args[-2:] == ['backend', 'face-recognition']
    assert kwargs['env']['CHECKIN_DIAGNOSTICS_ENABLED'] == 'false'
    assert kwargs['env']['CHECKIN_DIAGNOSTIC_SESSION_IDS'] == ''


@pytest.mark.parametrize('failure', ['stream_end', 'launch', 'report', 'interrupt', 'timeout'])
def test_monitor_cleans_up_incomplete_and_failed_runs(monitor_run, monkeypatch, failure):
    _, report, commands, _ = monitor_run
    expected_exception = None
    if failure == 'launch':
        def fail(*args, **kwargs):
            raise OSError('failed to start stream')
        monkeypatch.setattr(monitor.subprocess, 'Popen', fail)
        expected_exception = OSError
    elif failure == 'report':
        original = monitor.update_report
        calls = []
        def fail_once(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise OSError('report unavailable')
            return original(*args, **kwargs)
        monkeypatch.setattr(monitor, 'update_report', fail_once)
        expected_exception = OSError
    elif failure == 'interrupt':
        class InterruptedQueue:
            def put(self, value):
                pass
            def get(self, timeout):
                raise KeyboardInterrupt
        monkeypatch.setattr(monitor.queue, 'Queue', InterruptedQueue)
    elif failure == 'timeout':
        times = iter([0, 100000])
        monkeypatch.setattr(monitor.time, 'monotonic', lambda: next(times))
    if expected_exception:
        with pytest.raises(expected_exception):
            monitor.main()
    else:
        monitor.main()
    assert len(commands) == 1
    assert commands[0][0][-2:] == ['backend', 'face-recognition']
    assert 'diagnostics disabled' in report.read_text()
    assert 'all sessions reached terminal motion outcomes' not in report.read_text()


def test_failed_cleanup_is_reported_and_old_image_cleanup_remains_backend_only(monitor_run, monkeypatch):
    _, report, _, _ = monitor_run
    monkeypatch.setattr(monitor.subprocess, 'run', lambda *args, **kwargs: N(returncode=1))
    monitor.main()
    assert 'shutdown FAILED' in report.read_text()
    commands = []
    monkeypatch.setattr(monitor.subprocess, 'run', lambda args, **kwargs: commands.append(args) or N(returncode=0))
    assert monitor.disable_diagnostics('image') is True
    assert commands[0][-1] == 'backend' and 'face-recognition' not in commands[0]
