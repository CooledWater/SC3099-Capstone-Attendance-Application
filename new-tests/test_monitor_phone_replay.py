import importlib.util
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phone_replay_monitor_test', ROOT / 'new-tests/monitor_phone_replay.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def record(stage='decision', **values):
    return {'timestamp': '2026-10-24T04:00:00+00:00', 'session_id': str(uuid.uuid4()),
            'diagnostic_id': str(uuid.uuid4()), 'stage': stage, 'values': values}


def test_reader_drops_unrelated_logs_sessions_and_sensitive_fields():
    row = record(risk_score=.2, image='SECRET_IMAGE', liveness_score='SECRET_IMAGE')
    line = monitor.diag.PREFIX + json.dumps(row)
    assert monitor.decode_record('ordinary log SECRET_IMAGE', {row['session_id']}) is None
    assert monitor.decode_record(line, {str(uuid.uuid4())}) is None
    clean = monitor.decode_record(line, {row['session_id']})
    assert clean['values'] == {'risk_score': .2}
    assert 'SECRET_IMAGE' not in json.dumps(clean)


def test_uncommitted_or_missing_liveness_is_not_a_success_claim():
    decision = record(liveness_available=True, liveness_passed=True, face_match_available=True, face_match_passed=True)
    assert 'not confirmed' in monitor.classification([decision])
    committed = {**decision, 'stage': 'attendance_committed', 'values': {}}
    assert 'enrolled-face match passed' in monitor.classification([decision, committed])
    decision['values']['liveness_available'] = False
    assert 'Inconclusive' in monitor.classification([decision, committed])
    decision['values'].update(liveness_available=True, liveness_passed=False)
    assert 'rejected this capture' in monitor.classification([decision, committed])


def test_report_updates_preserve_participant_notes_and_dedicated_boundaries(tmp_path):
    path = tmp_path / 'report.md'
    path.write_text('# Report\n\nParticipant notes: preserve this.\n')
    row = record(risk_score=.2)
    config = {'sessions': [{'id': row['session_id'], 'label': 'phone_screen'}]}
    monitor.update_report(path, config, [], 'waiting')
    assert 'Neither test has a measured result' in path.read_text()
    monitor.update_report(path, config, [row], 'monitoring')
    result = path.read_text()
    assert 'Participant notes: preserve this.' in result
    assert result.count(monitor.BEGIN) == 1
    assert 'Neither test has a measured result' not in result
    assert row['diagnostic_id'] in result
