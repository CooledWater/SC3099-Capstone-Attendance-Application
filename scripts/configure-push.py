"""Create persistent local VAPID keys in the ignored root .env; never print them.

Run with a Python environment containing cryptography (or in the backend container).
"""
import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

path = Path('.env')
existing = path.read_text() if path.exists() else ''
values = {}
for line in existing.splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('\"\'')
project_contact = 'https://github.com/CooledWater/SC3099-Capstone-Attendance-Application'
subject = values.get('VAPID_SUBJECT') or project_contact
if subject == 'mailto:attendance@example.test':
    subject = project_contact
if bool(values.get('VAPID_PUBLIC_KEY')) != bool(values.get('VAPID_PRIVATE_KEY')):
    raise SystemExit('Incomplete VAPID pair in .env; restore both existing keys before continuing.')
if values.get('VAPID_PUBLIC_KEY'):
    if values.get('VAPID_SUBJECT') != subject:
        lines = [line for line in existing.splitlines() if line.split('=', 1)[0].strip() != 'VAPID_SUBJECT']
        path.write_text('\n'.join(lines) + '\nVAPID_SUBJECT=' + subject + '\n')
        os.chmod(path, 0o600)
        print('Updated push contact URI; signing keys are unchanged.')
    print('VAPID keys already configured; preserving existing subscriptions.')
else:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    encode = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
    # Replace empty settings rather than allowing duplicate dotenv definitions.
    lines = [line for line in existing.splitlines() if line.split('=', 1)[0].strip() not in ('VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'VAPID_SUBJECT')]
    lines.extend(['', '# Persistent Web Push signing keys; do not commit or rotate casually.',
                  'VAPID_PUBLIC_KEY=' + encode(public), 'VAPID_PRIVATE_KEY=' + encode(private), 'VAPID_SUBJECT=' + subject])
    path.write_text('\n'.join(lines) + '\n')
    os.chmod(path, 0o600)
    print('Web Push configured in .env. Private key was not printed.')
