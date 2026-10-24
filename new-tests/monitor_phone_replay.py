"""Collect only scoped scalar diagnostics and maintain the local replay report.

No raw Docker log file is written. Stop after both sessions commit or timeout,
then recreate only the backend with diagnostics disabled.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
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
        return {'timestamp': timestamp.astimezone(timezone.utc).isoformat(),
                'diagnostic_id': diagnostic_id, 'session_id': sid, 'stage': stage,
                'values': diag.sanitize(raw.get('values'), diag.SCHEMAS[stage])}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None


def classification(rows):
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


def update_report(path, config, records, state):
    groups = {}
    for record in records:
        groups.setdefault(record['diagnostic_id'], []).append(record)
    labels = {session['id']: session['label'] for session in config['sessions']}
    lines = [BEGIN, '## Instrumented observations', '', f'Monitor state: **{state}**.', '',
             'Updated: ' + datetime.now(SGT).isoformat(timespec='seconds') + '.', '',
             'Presentation labels identify the assigned session; they do not independently establish what the camera saw.', '']
    if not groups:
        lines += ['No diagnostic submissions observed yet. Neither test has a measured result.', '']
    for attempt, rows in groups.items():
        lines += [f'### {labels[rows[0]["session_id"]]} / {attempt}', '',
                  classification(rows), '',
                  'The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.', '',
                  '```json', json.dumps(rows, indent=2, allow_nan=False), '```', '']
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--report', type=Path, default=ROOT / 'new-documentations/test-logs/phone-replay-test.md')
    parser.add_argument('--minutes', type=float, default=45)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    sessions = {session['id'] for session in config['sessions']}
    records, seen = [], set()
    lines = queue.Queue()
    process = subprocess.Popen(['docker', 'logs', '--since', config['monitor_since'], '--follow', 'saiv-backend'],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    def read():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
    threading.Thread(target=read, daemon=True).start()
    state = 'monitoring; waiting for participant submissions'
    update_report(args.report, config, records, state)
    print('MONITOR_READY: scoped diagnostics only; report updates after each event.', flush=True)
    deadline = time.monotonic() + args.minutes * 60
    try:
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
            update_report(args.report, config, records, state)
            print(f'OBSERVED {record["stage"]} for {record["session_id"]}', flush=True)
            committed = {row['session_id'] for row in records if row['stage'] == 'attendance_committed'}
            if committed == sessions:
                state = 'both sessions committed; participant presentation confirmation still required'
                break
        else:
            state = 'monitor timeout; unobserved tests remain pending'
    except KeyboardInterrupt:
        state = 'monitor stopped by operator; incomplete tests remain pending'
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
        env = dict(os.environ, CHECKIN_DIAGNOSTICS_ENABLED='false', CHECKIN_DIAGNOSTIC_SESSION_IDS='')
        result = subprocess.run(['docker', 'compose', '-f', 'docker-compose.yml',
            '-f', 'new-tests/docker-compose.phone-replay.yml', 'up', '-d', '--no-deps', 'backend'],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state += '; diagnostics disabled' if result.returncode == 0 else '; diagnostics shutdown FAILED: operator action needed'
        update_report(args.report, config, records, state)
        print('MONITOR_FINISHED: ' + state, flush=True)


if __name__ == '__main__':
    main()
