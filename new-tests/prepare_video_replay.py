"""Create two fresh motion/PAD trial sessions and a scoped monitor config.

Uses the instructor/admin API. Does not enroll students, change existing sessions,
configure PAD, submit attendance, or save credentials.
"""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
from pathlib import Path
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def api_request(base, path, *, token=None, body=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(base.rstrip('/') + '/api/v1' + path, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def session_payload(course_id, label, now, minutes):
    start = now + timedelta(minutes=1)
    end = start + timedelta(minutes=minutes)
    return {
        'course_id': course_id, 'name': f'Video PAD {label} {now:%Y-%m-%d %H:%M UTC}',
        'session_type': 'lecture',
        'scheduled_start': start.isoformat(), 'scheduled_end': end.isoformat(),
        'checkin_opens_at': now.isoformat(), 'checkin_closes_at': end.isoformat(),
        'require_motion_check': True, 'require_liveness_check': True, 'require_face_match': True,
    }


def create_pair(base, token, course_id, minutes, config_path, request=None):
    request = request or api_request
    now = datetime.now(timezone.utc)
    config = {'monitor_since': now.isoformat(), 'pad_mode': 'enforce',
              'setup_complete': False, 'sessions': []}
    # Reserve the path before any API mutation, including concurrent invocations.
    with config_path.open('x') as output:
        output.write(json.dumps(config, indent=2) + '\n')
    for label in ('real_face_control', 'phone_video'):
        payload = session_payload(course_id, label, now, minutes)
        session = request(base, '/sessions/', token=token, body=payload)
        sid = str(uuid.UUID(session['id']))
        duplicate = any(item['id'] == sid for item in config['sessions'])
        config['sessions'].append({'id': sid, 'label': label, 'name': payload['name']})
        # Keep the created ID even if its returned policy is wrong or setup stops.
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        if duplicate or any(session.get(flag) is not True for flag in (
                'require_motion_check', 'require_liveness_check', 'require_face_match')):
            raise ValueError('Unexpected session ID or verification policy; inspect the partial config')
        print(f'Created {label}: {sid}', flush=True)
    config['setup_complete'] = True
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--api-url', default='http://localhost:8000', help='Backend origin, without /api/v1')
    parser.add_argument('--course-id', help='Skip the interactive course list')
    parser.add_argument('--minutes', type=int, default=60, help='Session duration, 5–240 minutes (default: 60)')
    args = parser.parse_args()
    if not 5 <= args.minutes <= 240:
        parser.error('--minutes must be between 5 and 240')
    if args.config.exists():
        parser.error('config already exists; choose a fresh filename')
    if not args.config.parent.is_dir():
        parser.error('config parent directory does not exist')
    course_id = args.course_id
    if course_id is not None:
        try:
            course_id = str(uuid.UUID(course_id))
        except ValueError:
            parser.error('--course-id must be a UUID')
    try:
        email = input('Instructor/admin email: ').strip()
        password = getpass.getpass('Password (not saved): ')
        login = api_request(args.api_url, '/auth/login', body={'email': email, 'password': password})
        del password
        token = login['access_token']
        if course_id is None:
            courses = api_request(args.api_url, '/courses/?limit=100', token=token)['items']
            if not courses:
                raise ValueError('No accessible courses; enroll the test student in a test course first')
            for index, course in enumerate(courses, 1):
                print(f'{index}. {course["code"]} — {course["name"]} ({course["id"]})')
            index = int(input('Course number (student must already be enrolled): '))
            if not 1 <= index <= len(courses):
                raise ValueError('Invalid course number')
            course_id = str(uuid.UUID(courses[index - 1]['id']))
        config = create_pair(args.api_url, token, course_id, args.minutes, args.config)
        print('Config: ' + str(args.config))
        print('Session allowlist: ' + ','.join(session['id'] for session in config['sessions']))
        print('Wait about one minute for activation; enable diagnostics before starting either challenge.')
    except HTTPError as exc:
        parser.exit(1, f'API returned HTTP {exc.code}. Check credentials/course access; inspect any partial config.\n')
    except (URLError, ValueError, KeyError, TypeError, OSError) as exc:
        # Never print arbitrary response/error bodies, which could contain secrets.
        parser.exit(1, f'Setup failed ({type(exc).__name__}). Inspect any partial config; use a fresh path to retry.\n')


if __name__ == '__main__':
    main()
