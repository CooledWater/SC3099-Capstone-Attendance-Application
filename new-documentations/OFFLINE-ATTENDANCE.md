# Offline student attendance view

The PWA caches its shell/static assets and saves a small account-scoped IndexedDB
snapshot for read-only browsing. Visit the app online first, then use the same
installed PWA/origin offline. An installation on a new ngrok hostname has separate
browser storage and needs an online visit of its own.

The earlier snapshot only saved check-in-open sessions, expired after fifteen
minutes, and filtered at the check-in deadline. It did not save attendance statuses.
It now retains session summaries and saved check-in status/time/risk score until each session's
`scheduled_end`, even after its check-in window closes. UTC API times without a
suffix are parsed as UTC. Cancelled/ended sessions are hidden; an empty active
session list does not discard still-running sessions already saved.

Online refresh uses existing `GET /sessions/active`, `GET /sessions/my-sessions`
(the recent day, including overlapping sessions), and `GET /checkins/my-checkins`.
The selected attendance lookup and successful check-in response also update the
snapshot. Sessions are merged in one IndexedDB transaction and capped at 100;
only sanitized status/time/risk score are copied from attendance responses. Existing records
remain compatible; no database version change is necessary.

The UI shows **Offline**, last-saved time, a saved-session dropdown and a check-in result panel matching the online layout. Empty or expired caches show a graceful fallback.
The view rechecks expiry every ten seconds. Normal network loss, fetch failure,
read timeout, and temporary 502/503/504 gateway outages enter read-only mode;
authorization/validation errors remain errors. Polling/focus refresh attempts to
recover connectivity and update reviewed attendance without interrupting an active
camera or submission. Browser `navigator.onLine` alone is not treated as proof of
server connectivity.

No authentication response, access/refresh token, image, biometric proof, precise
location, appeal reason, or reviewer note is saved in this snapshot.
No check-in/appeal is submitted or queued offline. The worker does not cache API
responses or the staff dashboard. Explicit sign-out clears snapshots for every
account and late writes are blocked by the account marker. A different account
cannot read the previous account's saved sessions through the cache API.

Verification:

- `npm --prefix module1-frontend run typecheck`
- `node --test new-tests/pwa/unit.test.mjs new-tests/pwa/consent.test.mjs`
- With the production frontend running, `node new-tests/pwa/offline-attendance-browser.mjs`

The browser test mocks API responses in a clean browser context, without changing
real attendance, and checks mobile offline reload, statuses after check-in closes,
expired sessions, browsing, poor connectivity, reconnection, and sign-out cleanup.

Older snapshots without a risk score show “Not saved” until an online refresh.
