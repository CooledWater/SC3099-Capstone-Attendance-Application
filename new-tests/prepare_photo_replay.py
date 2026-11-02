"""Create a fresh, paired photo-replay trial using an instructor's normal API.

Explicitly creates sessions with motion disabled for passive-photo evaluation.
Does not enroll students, alter existing sessions, or save login credentials.
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
    return {
        'course_id': course_id, 'name': f'PAD shadow {label} {now:%Y-%m-%d %H:%M UTC}',
        'session_type': 'lecture',
        'scheduled_start': (now + timedelta(minutes=1)).isoformat(),
        'scheduled_end': (now + timedelta(minutes=minutes)).isoformat(),
        'checkin_opens_at': now.isoformat(),
        'checkin_closes_at': (now + timedelta(minutes=minutes)).isoformat(),
        'require_liveness_check': True, 'require_face_match': True, 'require_motion_check': False,
    }


def create_pair(base, token, course_id, minutes, config_path, request=api_request):
    now = datetime.now(timezone.utc)
    config = {'monitor_since': now.isoformat(), 'pad_mode': 'shadow', 'sessions': []}
    # Refuse to overwrite historical trial configuration before creating anything.
    with config_path.open('x') as output:
        json.dump(config, output, indent=2)
        output.write('\n')
    for label in ('real_face_control', 'phone_screen'):
        session = request(base, '/sessions/', token=token,
                          body=session_payload(course_id, label, now, minutes))
        sid = str(uuid.UUID(session['id']))
        if (session.get('require_motion_check') is not False
                or session.get('require_liveness_check') is not True
                or session.get('require_face_match') is not True):
            raise ValueError('Created session has unexpected verification policy; inspect it before testing')
        config['sessions'].append({'id': sid, 'label': label, 'name': session['name']})
        # Preserve every successful creation if a later API request fails.
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        print(f'Created {label}: {sid}', flush=True)
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--api-url', default='http://localhost:8000')
    parser.add_argument('--course-id')
    parser.add_argument('--minutes', type=int, default=60)
    args = parser.parse_args()
    if not 5 <= args.minutes <= 240:
        parser.error('--minutes must be between 5 and 240')
    if args.config.exists():
        parser.error('config already exists; choose a fresh filename')
    if not args.config.parent.is_dir():
        parser.error('config parent directory does not exist')
    try:
        email = input('Instructor/admin email: ').strip()
        password = getpass.getpass('Password (not saved): ')
        login = api_request(args.api_url, '/auth/login', body={'email': email, 'password': password})
        del password
        token = login['access_token']
        course_id = args.course_id
        if course_id is None:
            page = api_request(args.api_url, '/courses/?limit=100', token=token)
            courses = page['items']
            if not courses:
                raise ValueError('No accessible courses; create a test course and enroll the test student first')
            for index, course in enumerate(courses, 1):
                print(f'{index}. {course["code"]} — {course["name"]} ({course["id"]})')
            index = int(input('Course number (student must already be enrolled): '))
            if not 1 <= index <= len(courses):
                raise ValueError('Invalid course number')
            course_id = courses[index - 1]['id']
        course_id = str(uuid.UUID(course_id))
        config = create_pair(args.api_url, token, course_id, args.minutes, args.config)
        print('Config: ' + str(args.config))
        print('Session allowlist: ' + ','.join(s['id'] for s in config['sessions']))
        print('Wait about one minute for activation, then start diagnostics before submitting photos.')
    except HTTPError as exc:
        parser.exit(1, f'API returned HTTP {exc.code}. Check credentials/course access; any created session IDs remain in the config.\n')
    except (URLError, ValueError, KeyError, OSError) as exc:
        # Avoid printing response bodies, credentials or arbitrary server errors.
        parser.exit(1, f'Setup failed ({type(exc).__name__}). Check the API and config; do not overwrite a partial trial.\n')


if __name__ == '__main__':
    main()
