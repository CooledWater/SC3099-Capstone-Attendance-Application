# Attendance approval notifications

Students enable push from **Profile → Settings → Attendance notifications**, using the **Allow attendance notifications** switch.
Permission is requested only after pressing the button. Notification preferences apply
to that browser/PWA installation. HTTPS is required except for localhost. On iOS/iPadOS,
add the PWA to the Home Screen and launch it there before enabling notifications.
Existing installations must accept the app update before this feature is available.

An authorised instructor, TA or admin approving a flagged/appealed check-in through
`POST /api/v1/checkins/{id}/review` atomically queues one delivery per opted-in browser.
Submitting an appeal alone, a rejection, and automatic check-in approval do not notify.
The title is **Attendance approved**. The body uses the instructor’s review message
when present (decoded as plain text, trimmed and capped at 500 characters), otherwise
it says “Your attendance has been approved. Tap to view your attendance.” Review
messages can appear on the device lock screen. No student name, class, appeal
reason, location, or biometric data is added. iOS may separately show “from SAIV”
as app attribution; this is outside the notification title. Tapping opens `/dashboard/` on
the same origin, where the existing authentication and attendance history apply.

## Configuration

Run `python scripts/configure-push.py` from the repository root using a Python
environment containing `cryptography`. It writes a persistent VAPID key pair and
contact subject to the ignored root `.env`, preserving existing keys. The private
key is never printed or exposed to the frontend. `VAPID_SUBJECT` defaults to the
public project GitHub URL; a monitored `mailto:` address is also valid. The earlier
`mailto:attendance@example.test` placeholder is replaced by the script without
rotating keys, because Apple may reject placeholder contact URIs with
`403 BadJwtToken`. Keep the same pair between rebuilds; rotating it
requires students to enable notifications again.

Docker Compose passes `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT`
to the backend. Rebuild with `docker compose up -d --build frontend backend`.
Without all three values the configuration endpoint reports disabled and new
subscriptions return 503. No Firebase account or APNs certificate is needed.

## API additions

All endpoints require an active authenticated student. These are additive extensions;
the existing API and database specifications under `docs/` remain unchanged.

| Endpoint | Behaviour |
| --- | --- |
| `GET /api/v1/push/config` | `{enabled, public_key}`; no private signing material |
| `PUT /api/v1/push/subscriptions` | Upsert browser `{endpoint, keys: {p256dh, auth}}`; 204 |
| `POST /api/v1/push/subscriptions/remove` | Remove the caller's `{endpoint}` and pending deliveries; 204 |

Subscription endpoints accept only HTTPS browser push providers for Chrome/Firefox/
Safari/Edge. Public keys must be valid P-256 points; auth secrets must be 16 bytes.
Provider requests have a timeout and cannot follow redirects. Endpoints and keys
are sensitive capabilities: they are never returned, included in errors, or logged.

## Persistence and delivery

Two additive tables (`push_subscriptions`, `push_deliveries`) are registered with
the existing SQLAlchemy `create_all` startup mechanism; no existing columns change.
The database stores browser subscription capabilities and a delivery record linking
each check-in/subscription pair. It does not store notification bodies or review data.

The backend lifespan runs an outbox worker every five seconds. Jobs use row locks
and two-minute leases, release the DB connection during provider requests, retry
failures up to six times with backoff, and discard jobs older than one day. Provider
404/410 removes expired subscriptions. Delivery records are removed after seven days.
Provider acceptance is not a device delivery receipt. Delivery is at least once:
a process crash after sending can cause a retry, with a stable notification tag
to replace an earlier notification. OS/browser policies may delay or suppress delivery.

Signing out or turning notifications off clears the local owner marker and visible
notifications, removes the server subscription when online, and unsubscribes in the
browser. The worker suppresses old pushes after logout/account changes. The same
endpoint can belong to only one student; enabling it for another account cancels
the previous account's queued jobs. Subscriptions are capped at ten per account.
No historical approvals are sent when notifications are enabled later.

## Verification

- `pytest new-tests/test_push_notifications.py new-tests/test_checkin_roster.py -q`
- `node --test new-tests/pwa/push-notifications.test.mjs`
- `cd module1-frontend && npm run typecheck`

The transport regression exercises real VAPID signing and payload encryption with
a stub HTTPS transport; it does not send to a real student's device. To verify
actual delivery: update/install the PWA over HTTPS, sign in as a student and enable
notifications, close the PWA, then approve that student's flagged/appealed check-in
from an authorised reviewer account. Verify the notification and its dashboard link.
