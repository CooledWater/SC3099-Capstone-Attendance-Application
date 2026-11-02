"""Collect only scoped scalar diagnostics and maintain the local replay report.

No raw Docker log file is written. Image mode stops after attendance commits;
video mode also observes terminal motion failures. Disable diagnostics on exit.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phone_test_diagnostics', ROOT / 'module2-backend/app/checkin_diagnostics.py')
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
SGT = timezone(timedelta(hours=8))
BEGIN = '<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->'
END = '<!-- PHONE_REPLAY_DIAGNOSTICS_END -->'


def decode_record(line, session_ids):
    if not line.startswith(diag.PREFIX) or len(line) > 32768:
        return None
    try:
        raw = json.loads(line[len(diag.PREFIX):])
        sid = str(uuid.UUID(raw['session_id']))
        diagnostic_id = str(uuid.UUID(raw['diagnostic_id']))
        timestamp = datetime.fromisoformat(raw['timestamp'])
        stage = raw['stage']
        if sid not in session_ids or timestamp.tzinfo is None or stage not in diag.SCHEMAS:
            return None
        clean = {'timestamp': timestamp.astimezone(timezone.utc).isoformat(),
                 'diagnostic_id': diagnostic_id, 'session_id': sid, 'stage': stage,
                 'values': diag.sanitize(raw.get('values'), diag.SCHEMAS[stage])}
        if 'challenge_id' in raw:
            clean['challenge_id'] = str(uuid.UUID(raw['challenge_id']))
        return clean
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None


def classification(rows, mode='image'):
    if mode == 'video':
        verified = next((r['values'] for r in reversed(rows) if r['stage'] == 'motion_verified'), None)
        committed = next((r['values'] for r in reversed(rows) if r['stage'] == 'attendance_committed'), None)
        if verified is not None and verified.get('passed') is False:
            return 'Server rejected the motion sequence; no attendance submission is required to record this outcome.'
        if verified is not None and verified.get('passed') is True:
            if committed is None:
                return 'Server accepted the motion sequence; attendance commitment not confirmed.'
            return ('Server accepted the motion sequence; saved attendance status: ' +
                    committed.get('status', 'unknown') + '. Physical presentation confirmation is still required.')
        if any(r['stage'] == 'motion_request_failed' for r in rows):
            return 'Inconclusive for replay detection: motion request failed, expired, or verification was unavailable.'
        return 'No completed server motion verification recorded; browser-only capture is not a server result.'
    decision = next((row['values'] for row in reversed(rows) if row['stage'] == 'decision'), None)
    committed = any(row['stage'] == 'attendance_committed' for row in rows)
    if decision is None:
        return 'No completed biometric decision recorded.'
    if not committed:
        return 'Decision calculated; attendance commitment not confirmed.'
    if not decision.get('liveness_available') or decision.get('liveness_passed') is None:
        return 'Inconclusive for replay detection: liveness was unavailable/not performed.'
    if decision['liveness_passed'] is False:
        return 'Passive liveness rejected this capture.'
    if not decision.get('face_match_available') or decision.get('face_match_passed') is None:
        return 'Passive liveness passed; identity verification unavailable.'
    return ('Passive liveness passed; enrolled-face match ' +
            ('passed.' if decision['face_match_passed'] else 'failed.'))


def video_groups(records):
    groups = {}
    for row in records:
        cid = row.get('challenge_id')
        if cid:
            groups.setdefault((row['session_id'], cid), []).append(row)
    return groups


def completed_sessions(records, mode='image'):
    if mode == 'image':
        return {row['session_id'] for row in records if row['stage'] == 'attendance_committed'}
    # A retry supersedes the older challenge, even if an older request finishes
    # after the retry starts. An unobserved issuance can use verification start.
    latest = {}
    groups = video_groups(records)
    for (sid, cid), rows in groups.items():
        starts = [r for r in rows if r['stage'] in ('motion_challenge_issued', 'motion_verification_started')]
        if not starts:
            continue
        issued = [r for r in starts if r['stage'] == 'motion_challenge_issued']
        started = min(r['timestamp'] for r in (issued or starts))
        if sid not in latest or started > latest[sid][0]:
            latest[sid] = (started, cid)
    completed = set()
    for sid, (_, cid) in latest.items():
        rows = groups[(sid, cid)]
        verified = next((r['values'] for r in reversed(rows) if r['stage'] == 'motion_verified'), {})
        if (verified.get('passed') is False
            or verified.get('passed') is True and any(r['stage'] == 'attendance_committed' for r in rows)
            or 'passed' not in verified and any(r['stage'] == 'motion_request_failed' for r in rows)):
            completed.add(sid)
    return completed


def frame_table(rows):
    details = next((r['values'].get('diagnostics', {}) for r in reversed(rows)
                    if r['stage'] == 'motion_sequence'), {})
    lines = ['| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for name in ('first_frame', 'last_frame'):
        frame = details.get(name, {})
        if frame.get('evaluated') is not True:
            label = 'not evaluated' if frame.get('evaluated') is False else 'unknown'
            lines.append(f'| {name} | {label} | — | — | — | — | not evaluated | — | — |')
            continue
        components = frame.get('details', {})
        values = [components.get('depth_score', 'unknown'), components.get('mesh_plausibility_score', 'unknown'),
                  frame.get('liveness_score', 'unknown'),
                  f'{components.get("depth_passed", "unknown")} / {components.get("mesh_passed", "unknown")}',
                  components.get('pad_status', 'unknown'),
                  components.get('pad_live_score'), components.get('pad_passed')]
        lines.append(f'| {name} | yes | ' + ' | '.join(map(str, values)) + ' |')
    lines += ['', 'Sequence stop reason: ' + details.get('reason', 'unknown') + '.', '']
    return lines


def pad_table(rows):
    """Keep the shadow PAD verdict separate from saved attendance outcomes."""
    response = next((r['values'] for r in reversed(rows) if r['stage'] == 'liveness'), {})
    details = response.get('details', {})
    status = details.get('pad_status', 'unknown')
    if response.get('outcome') == 'unavailable':
        status = 'unavailable'
    lines = ['PAD is observational in shadow mode; its verdict does not change attendance.', '']
    if details.get('pad_evaluated') is not True:
        return lines + [f'PAD status: **{status}**. No measured PAD verdict is available.', '']
    values = [
        ('Mode / status', f'{details.get("pad_mode", "unknown")} / {status}'),
        ('Model version', details.get('pad_model_version', 'unknown')),
        ('Ensemble live score', details.get('pad_live_score')),
        ('V2 / V1SE live scores', f'{details.get("pad_v2_live_score")} / {details.get("pad_v1se_live_score")}'),
        ('Exploratory PAD cutoff (uncalibrated)', details.get('pad_threshold')),
        ('PAD passed', details.get('pad_passed')),
        ('PAD processing time (ms)', details.get('pad_inference_ms')),
        ('Liveness before PAD / returned', f'{details.get("pre_pad_liveness_score")} / {response.get("liveness_score")}'),
        ('Would PAD veto a legacy pass?', details.get('pad_would_veto')),
    ]
    return lines + ['| PAD observation | Value |', '| --- | --- |'] + [
        f'| {name} | {value} |' for name, value in values] + ['']


def _display(value):
    return 'unknown' if value is None else str(value)


def _value_table(title, values):
    return [f'#### {title}', '', '| Measurement | Value |', '| --- | --- |'] + [
        f'| {name} | {_display(value)} |' for name, value in values] + ['']


def original_liveness_tables(rows):
    """Render the existing allowlisted measurements even when PAD cannot run."""
    response = next((r['values'] for r in reversed(rows) if r['stage'] == 'liveness'), {})
    identity = next((r['values'] for r in reversed(rows) if r['stage'] == 'face_match'), {})
    details = response.get('details') or {}
    lines = _value_table('Original liveness and identity', [
        ('Liveness response', response.get('outcome', 'not observed')),
        ('Identity response', identity.get('outcome', 'not observed')),
        ('Challenge type', response.get('challenge_type')),
        ('Liveness score (returned)', response.get('liveness_score')),
        ('Liveness threshold', response.get('liveness_threshold', details.get('threshold'))),
        ('Liveness passed', response.get('liveness_passed')),
        ('Identity score (face match)', identity.get('match_score')),
        ('Identity threshold', identity.get('match_threshold')),
        ('Identity passed', identity.get('match_passed')),
        ('Identity face detected', identity.get('face_detected')),
    ])
    lines += ['`unknown` means the value was absent or null in the scoped diagnostics. '
              'Identity is a separate enrolled-face comparison, not a liveness component.', '',
              '#### Original liveness components', '',
              '| Component | Score | Weight | Weighted contribution | Gate threshold | Gate passed |',
              '| --- | --- | --- | --- | --- | --- |']
    weights = details.get('component_weights') or {}
    contributions = details.get('weighted_contributions') or {}
    for label, key, score_key in (
        ('Depth', 'depth', 'depth_score'),
        ('Mesh', 'mesh', 'mesh_plausibility_score'),
        ('Texture', 'texture', 'texture_analysis_score'),
        ('Color', 'color', 'color_distribution_score'),
    ):
        values = [details.get(score_key), weights.get(key), contributions.get(key)]
        values += ([details.get(key + '_threshold'), details.get(key + '_passed')]
                   if key in ('depth', 'mesh') else ['—', '—'])
        lines.append(f'| {label} | ' + ' | '.join(_display(value) for value in values) + ' |')
    lines += ['', 'Depth and mesh must each pass their gate. A failed gate can set returned liveness to 0 '
              'even when the pre-gate score is high. Texture and color have no separate gate.', '']
    measurements = [(f'`{key}`', details.get(key)) for key in (
        'face_detection_confidence', 'face_mesh_complete', 'multiple_faces', 'landmark_count',
        'depth_detected', 'depth_quality', 'landmark_z_variance', 'relative_nose_depth',
        'weighted_component_score', 'presentation_integrity_score', 'challenge_evidence_score',
        'challenge_integrity_score', 'single_image_challenge_proxy', 'pre_gate_liveness_score',
    )]
    for group in ('presentation_integrity_checks', 'texture_signals', 'color_signals'):
        signals = details.get(group) or {}
        measurements += [(f'`{group}.{key}`', signals[key]) for key in diag.DETAILS[group]
                         if key in signals]
    return lines + _value_table('Original liveness details', measurements)


def decision_table(rows):
    decision = next((r['values'] for r in reversed(rows) if r['stage'] == 'decision'), {})
    committed = next((r['values'] for r in reversed(rows) if r['stage'] == 'attendance_committed'), {})
    return _value_table('Attendance decision', [
        ('Calculated status', decision.get('status')),
        ('Decision reason', decision.get('reason')),
        ('Final risk score', decision.get('risk_score')),
        ('Effective risk threshold', decision.get('effective_threshold')),
        ('Venue risk score', decision.get('venue_risk_score')),
        ('Module 3 risk score (at decision)', decision.get('module3_risk_score')),
        ('Saved attendance status', committed.get('status')),
        ('Saved attendance risk score', committed.get('risk_score')),
    ])


def update_report(path, config, records, state, mode='image'):
    groups = {}
    for record in records:
        key = record.get('challenge_id', record['diagnostic_id']) if mode == 'video' else record['diagnostic_id']
        groups.setdefault((record['session_id'], key), []).append(record)
    labels = {session['id']: session['label'] for session in config['sessions']}
    lines = [BEGIN, '## Instrumented observations', '', f'Monitor state: **{state}**.', '',
             'Updated: ' + datetime.now(SGT).isoformat(timespec='seconds') + '.', '',
             'Presentation labels identify the assigned session; they do not independently establish what the camera saw.', '']
    if not groups:
        lines += ['No diagnostic submissions observed yet. Neither test has a measured result.', '']
    for (_, attempt), rows in groups.items():
        lines += [f'### {labels[rows[0]["session_id"]]} / {attempt}', '',
                  classification(rows, mode), '']
        if mode == 'video':
            lines += frame_table(rows)
        else:
            lines += original_liveness_tables(rows)
            lines += ['#### PAD observation', '']
            lines += pad_table(rows)
            lines += decision_table(rows)
            lines += ['The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.', '']
        lines += ['```json', json.dumps(rows, indent=2, allow_nan=False), '```', '']
    lines += [END]
    original = path.read_text() if path.exists() else ''
    block = '\n'.join(lines)
    if BEGIN in original and END in original:
        prefix, rest = original.split(BEGIN, 1)
        _, suffix = rest.split(END, 1)
        output = prefix + block + suffix
    else:
        output = original.rstrip() + '\n\n' + block + '\n'
    temporary = path.with_suffix('.md.tmp')
    temporary.write_text(output)
    temporary.replace(path)


def disable_diagnostics(mode):
    env = dict(os.environ, CHECKIN_DIAGNOSTICS_ENABLED='false', CHECKIN_DIAGNOSTIC_SESSION_IDS='')
    services = ['backend', 'face-recognition'] if mode == 'video' else ['backend']
    try:
        result = subprocess.run(['docker', 'compose', '-f', 'docker-compose.yml',
            '-f', 'new-tests/docker-compose.phone-replay.yml', 'up', '-d', '--no-deps', *services],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--minutes', type=float, default=45)
    parser.add_argument('--mode', choices=('image', 'video'), default='image')
    args = parser.parse_args()
    if args.report is None:
        if args.mode == 'video':
            parser.error('--mode video requires a unique --report path')
        args.report = ROOT / 'new-documentations/test-logs/phone-replay-test.md'
    config = json.loads(args.config.read_text())
    if not 0 < args.minutes <= 1440:
        parser.error('--minutes must be greater than zero and at most 1440')
    sessions_config = config.get('sessions', [])
    if not sessions_config or len({s['id'] for s in sessions_config}) != len(sessions_config):
        parser.error('config requires unique session IDs')
    for session in sessions_config:
        uuid.UUID(session['id'])
        if session['label'] not in ('real_face_control', 'phone_screen', 'phone_video'):
            parser.error('use a fixed presentation label: real_face_control, phone_screen, or phone_video')
    sessions = {session['id'] for session in config['sessions']}
    records, seen = [], set()
    lines = queue.Queue()
    process = None
    state = 'monitoring; waiting for participant submissions'
    deadline = time.monotonic() + args.minutes * 60
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous_sigterm = signal.signal(signal.SIGTERM, interrupted)
    try:
        process = subprocess.Popen(['docker', 'logs', '--since', config['monitor_since'], '--follow', 'saiv-backend'],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        def read():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)
        threading.Thread(target=read, daemon=True).start()
        update_report(args.report, config, records, state, args.mode)
        print('MONITOR_READY: scoped diagnostics only; report updates after each event.', flush=True)
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=2)
            except queue.Empty:
                continue
            if line is None:
                state = 'log stream ended; results may be incomplete'
                break
            record = decode_record(line, sessions)
            if record is None:
                continue
            key = (record['diagnostic_id'], record['stage'], record['timestamp'])
            if key in seen:
                continue
            seen.add(key); records.append(record)
            update_report(args.report, config, records, state, args.mode)
            print(f'OBSERVED {record["stage"]} for {record["session_id"]}', flush=True)
            if record['stage'] == 'liveness':
                details = record['values'].get('details', {})
                print(f'PAD {details.get("pad_status", "unknown")}: live={details.get("pad_live_score")} '
                      f'passed={details.get("pad_passed")} mode={details.get("pad_mode", "unknown")} '
                      f'would_veto={details.get("pad_would_veto")}', flush=True)
            if completed_sessions(records, args.mode) == sessions:
                state = ('all sessions reached terminal motion outcomes' if args.mode == 'video'
                         else 'both sessions committed') + '; participant presentation confirmation still required'
                break
        else:
            state = 'monitor timeout; unobserved tests remain pending'
    except KeyboardInterrupt:
        state = 'monitor stopped by operator; incomplete tests remain pending'
    except Exception:
        state = 'monitor failed; results may be incomplete'
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        try:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
        finally:
            disabled = disable_diagnostics(args.mode)
        state += '; diagnostics disabled' if disabled else '; diagnostics shutdown FAILED: operator action needed'
        update_report(args.report, config, records, state, args.mode)
        print('MONITOR_FINISHED: ' + state, flush=True)


if __name__ == '__main__':
    main()
