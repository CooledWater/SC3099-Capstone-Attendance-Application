import importlib.util
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pad_replay_monitor', ROOT / 'new-tests/monitor_phone_replay.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def row(**details):
    return {'timestamp': '2026-11-01T09:00:00+00:00', 'diagnostic_id': str(uuid.uuid4()),
        'session_id': str(uuid.uuid4()), 'stage': 'liveness', 'values': {
            'outcome': 'received', 'liveness_passed': True, 'liveness_score': .97, 'details': details}}


def test_pad_shadow_disagreement_is_visible_and_privacy_projected(tmp_path):
    record = row(pad_mode='shadow', pad_status='evaluated', pad_evaluated=True,
        pad_model_version='minifasnet-v2-v1se-onnx-v1', pad_live_score=.01,
        pad_threshold=.5, pad_passed=False, pad_inference_ms=6.2,
        pad_v2_live_score=.02, pad_v1se_live_score=0.,
        pre_pad_liveness_score=.97, pre_pad_liveness_passed=True, pad_would_veto=True,
        image='SECRET', pad_features=['SECRET'])
    clean = monitor.decode_record(monitor.diag.PREFIX + json.dumps(record), {record['session_id']})
    path = tmp_path / 'report.md'
    monitor.update_report(path, {'sessions': [{'id': record['session_id'], 'label': 'phone_screen'}]},
                           [clean], 'monitoring')
    report = path.read_text()
    assert 'SECRET' not in report
    assert 'does not change attendance' in report
    assert '| Ensemble live score | 0.01 |' in report
    assert '| PAD passed | False |' in report
    assert '| Would PAD veto a legacy pass? | True |' in report
    assert '| Liveness before PAD / returned | 0.97 / 0.97 |' in report


def test_unperformed_and_unavailable_are_not_fabricated_scores():
    for status in ('off', 'not_evaluated', 'unavailable'):
        table = '\n'.join(monitor.pad_table([row(pad_status=status, pad_evaluated=False,
            pad_live_score=None, pad_passed=None)]))
        assert status in table and 'No measured PAD verdict' in table
        assert 'Ensemble live score' not in table
    assert 'No measured PAD verdict' in '\n'.join(monitor.pad_table([]))
