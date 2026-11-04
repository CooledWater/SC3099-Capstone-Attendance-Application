"""Photo reports expose original biometrics without relying on a PAD verdict."""
import importlib.util
import json
from pathlib import Path
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('photo_replay_report', ROOT / 'new-tests/monitor_phone_replay.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def attempt(sid, *, mesh_passed=False, pad_status='evaluated'):
    diagnostic_id = str(uuid.uuid4())
    mesh_score = .84952 if mesh_passed else .76996
    pre_gate_score = .905823 if mesh_passed else .886016
    details = {
        'depth_score': .82596, 'mesh_plausibility_score': mesh_score,
        'texture_analysis_score': .99818, 'color_distribution_score': 1.,
        'depth_threshold': .8, 'mesh_threshold': .8,
        'depth_passed': True, 'mesh_passed': mesh_passed,
        'component_weights': {'depth': .3, 'mesh': .25, 'texture': .25, 'color': .2},
        'weighted_contributions': {'depth': .247788, 'mesh': .21238 if mesh_passed else .192489,
                                   'texture': .249546, 'color': .2},
        'weighted_component_score': .909714 if mesh_passed else .889822,
        'pre_gate_liveness_score': pre_gate_score,
        'face_mesh_complete': True, 'landmark_count': 468, 'depth_quality': 'good',
        'presentation_integrity_checks': {'periodicity': .995722},
        'texture_signals': {'laplacian_variance': 519.55, 'periodic_artifact_penalty': 0.},
        'color_signals': {'gamut_score': 1.},
        'pad_status': pad_status, 'pad_evaluated': pad_status == 'evaluated',
        'pad_mode': 'shadow', 'pad_live_score': .999863 if pad_status == 'evaluated' else None,
        'pad_passed': True if pad_status == 'evaluated' else None,
    }
    status = 'approved' if mesh_passed else 'rejected'
    values = {
        'liveness': {'outcome': 'received', 'liveness_score': pre_gate_score if mesh_passed else 0.,
                     'liveness_passed': mesh_passed, 'liveness_threshold': .85,
                     'challenge_type': 'passive', 'details': details},
        'face_match': {'outcome': 'received', 'match_score': .8888888010973244,
                       'match_threshold': .7, 'match_passed': True, 'face_detected': True},
        'decision': {'status': status, 'risk_score': .2, 'venue_risk_score': 0.,
                     'module3_risk_score': .2, 'effective_threshold': .5,
                     'reason': 'below_threshold' if mesh_passed else 'liveness_failed'},
        'attendance_committed': {'status': status, 'risk_score': .2},
    }
    return [{'timestamp': '2026-11-01T09:57:19+00:00', 'session_id': sid,
             'diagnostic_id': diagnostic_id, 'stage': stage, 'values': payload}
            for stage, payload in values.items()]


def render(tmp_path, records):
    sid = records[0]['session_id']
    config = {'sessions': [{'id': sid, 'label': 'real_face_control'}]}
    clean = [monitor.decode_record(monitor.diag.PREFIX + json.dumps(row), {sid}) for row in records]
    path = tmp_path / 'report.md'
    monitor.update_report(path, config, clean, 'finished')
    return path.read_text()


def test_geometry_rejection_identity_and_pad_disagreement_are_readable(tmp_path):
    report = render(tmp_path, attempt(str(uuid.uuid4())))
    tables = report.split('```json', 1)[0]
    assert '| Liveness score (returned) | 0.0 |' in tables
    assert '| Liveness passed | False |' in tables
    assert '| Liveness threshold | 0.85 |' in tables
    assert '| Identity score (face match) | 0.8888888010973244 |' in tables
    assert '| Identity threshold | 0.7 |' in tables
    assert '| Identity passed | True |' in tables
    assert '| Depth | 0.82596 | 0.3 | 0.247788 | 0.8 | True |' in tables
    assert '| Mesh | 0.76996 | 0.25 | 0.192489 | 0.8 | False |' in tables
    assert '| Texture | 0.99818 | 0.25 | 0.249546 | — | — |' in tables
    assert '| Color | 1.0 | 0.2 | 0.2 | — | — |' in tables
    assert '| `pre_gate_liveness_score` | 0.886016 |' in tables
    assert '| `landmark_count` | 468 |' in tables
    assert '| `texture_signals.periodic_artifact_penalty` | 0.0 |' in tables
    assert '| `presentation_integrity_checks.periodicity` | 0.995722 |' in tables
    assert '| `color_signals.gamut_score` | 1.0 |' in tables
    assert '| PAD passed | True |' in tables
    assert '| Decision reason | liveness_failed |' in tables
    assert '| Saved attendance status | rejected |' in tables


@pytest.mark.parametrize('status', ['off', 'not_evaluated', 'unavailable'])
def test_original_results_remain_visible_without_pad_measurements(tmp_path, status):
    report = render(tmp_path, attempt(str(uuid.uuid4()), mesh_passed=True, pad_status=status))
    tables = report.split('```json', 1)[0]
    assert '| Liveness passed | True |' in tables
    assert '| Identity passed | True |' in tables
    assert '| Mesh | 0.84952 | 0.25 | 0.21238 | 0.8 | True |' in tables
    assert f'PAD status: **{status}**' in tables
    assert 'No measured PAD verdict' in tables
    assert '| Saved attendance status | approved |' in tables


@pytest.mark.parametrize('outcome', ['unavailable', 'invalid_response'])
def test_missing_biometrics_and_uncommitted_decisions_stay_unknown(tmp_path, outcome):
    rows = attempt(str(uuid.uuid4()))[:3]
    rows[0]['values'] = {'outcome': outcome}
    rows[1]['values'] = {'outcome': outcome, 'match_score': None, 'match_passed': None}
    tables = render(tmp_path, rows).split('```json', 1)[0]
    assert f'| Liveness response | {outcome} |' in tables
    assert f'| Identity response | {outcome} |' in tables
    assert '| Liveness score (returned) | unknown |' in tables
    assert '| Liveness passed | unknown |' in tables
    assert '| Identity score (face match) | unknown |' in tables
    assert '| Identity passed | unknown |' in tables
    assert '| Depth | unknown | unknown | unknown | unknown | unknown |' in tables
    assert '| Calculated status | rejected |' in tables
    assert '| Saved attendance status | unknown |' in tables
    assert '| Saved attendance status | rejected |' not in tables


def test_partial_and_old_records_do_not_invent_defaults(tmp_path):
    rows = attempt(str(uuid.uuid4()))[:1]
    rows[0]['values'] = {'liveness_passed': False, 'liveness_score': 0., 'details': {
        'threshold': .6, 'depth_score': 0., 'mesh_plausibility_score': 0.,
        'texture_analysis_score': 0., 'color_distribution_score': 0., 'landmark_count': 0,
        'face_mesh_complete': False}}
    tables = render(tmp_path, rows).split('```json', 1)[0]
    assert '| Liveness threshold | 0.6 |' in tables
    assert '| Depth | 0.0 | unknown | unknown | unknown | unknown |' in tables
    assert '| `landmark_count` | 0 |' in tables
    assert '| `face_mesh_complete` | False |' in tables
    assert '| Identity response | not observed |' in tables
    assert '| Identity threshold | unknown |' in tables
    assert '| Identity passed | unknown |' in tables


def test_report_keeps_attempts_separate_and_preserves_notes_and_scalar_json(tmp_path):
    sid = str(uuid.uuid4())
    first = attempt(sid)
    second = attempt(sid, mesh_passed=True)
    # Simulate extra service fields; the existing decoder must still strip them.
    first[0]['values']['details'].update(image='SECRET', landmarks=['SECRET'], nose_tip_z=-.05)
    first[0]['values']['details']['texture_signals']['image'] = 'SECRET'
    clean = [monitor.decode_record(monitor.diag.PREFIX + json.dumps(row), {sid}) for row in first + second]
    config = {'sessions': [{'id': sid, 'label': 'real_face_control'}]}
    path = tmp_path / 'report.md'
    path.write_text('# Trial\n\nOperator notes: keep this.\n')
    monitor.update_report(path, config, clean, 'finished')
    monitor.update_report(path, config, clean, 'finished')
    report = path.read_text()
    assert 'Operator notes: keep this.' in report
    assert report.count(monitor.BEGIN) == report.count(monitor.END) == 1
    assert 'SECRET' not in report and 'nose_tip_z' not in report
    attempts = report.split('### real_face_control / ')[1:]
    assert len(attempts) == 2
    for section, rows, passed in zip(attempts, [clean[:4], clean[4:]], [False, True]):
        tables, rest = section.split('```json\n', 1)
        assert f'| Liveness passed | {passed} |' in tables
        assert f'| Liveness passed | {not passed} |' not in tables
        assert json.loads(rest.split('\n```', 1)[0]) == rows
