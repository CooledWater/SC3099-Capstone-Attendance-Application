# Account privacy, device-key renewal, and authentication refresh

These extensions preserve the existing public API contracts. `docs/` is unchanged.

## Authentication refresh

The Module 1 API client shares one in-flight refresh between concurrent 401s and
retries a delayed old-token 401 using a token already refreshed by another request.
Each caller can still choose whether connectivity errors propagate. Logout/new
login invalidates pending responses so an old request cannot restore another
account's access token or replay a request under the new login.

## Signing-key renewal

The browser's installation identifier remains stable while its P-256 signing key
changes. This preserves device IDs, check-ins, trust/approval, active/removed state,
and verified shared-browser associations for every account on that browser.
Keys last 90 days, using the existing `public_key_created_at` and
`public_key_expires_at` fields. Existing keys derive expiry from creation/first-seen
when an explicit deadline is absent. Module 1 renews within seven days of expiry
when registering/using the browser online. Students can also choose **Profile →
My devices → Renew this device’s security key**. No device approval is granted by
renewal, and removed/inactive devices cannot initiate it.

- `POST /api/v1/devices/key-rotation/challenges`: active verified owner supplies
  `{device_fingerprint, new_public_key}`; returns a five-minute challenge.
- `POST /api/v1/devices/key-rotation/complete`: `{challenge_id, old_signature,
  new_signature}` proves both private keys and performs an atomic renewal.

The additional `device_key_rotations` table stores expiring challenges/public keys,
never private keys. Existing registration endpoints validate against the current
key for a known stable browser identifier; arbitrary key substitution is rejected.
Check-in proofs issued before renewal are invalidated. Completion is idempotent
for a lost response, but cannot restore an old key after a newer renewal. Browser
Web Locks coordinate tabs; an IndexedDB compare-and-store also elects one pending
renewal when locks are unavailable. Both non-exportable keys are persisted before
server completion, so re-opening the same account can finish a dropped request.

Renewal affects all accounts on the same browser installation. If connection is
lost during renewal, finish it while signed into the account that started it
before switching to another account. Lost browser storage/private keys cannot be
recovered by this protocol; register a new browser through the usual approval flow.

## Student data-deletion request

**Profile → Settings → Delete my data** explains deletion and requires the current
password. Students can view, schedule, or cancel their own request:

- `GET /api/v1/users/me/deletion-request`
- `POST /api/v1/users/me/deletion-request`, body `{password}`
- `DELETE /api/v1/users/me/deletion-request`, body `{password}`

The existing `users.scheduled_deletion_at` stores the deadline, thirty days after
the first request. Repeated requests do not postpone it. Cancellation requires the
password and is allowed before the deadline. Existing accounts remain usable
until deletion; staff accounts cannot use these student endpoints. Normal
authentication/rate limits apply, with a separate password-confirmation limit.

A background worker checks due requests every minute, in batches of ten, with
row locks. It removes the student's check-ins and associated risk signals, device
registrations/proofs/renewal challenges, course enrollments, invitation metadata,
push subscriptions/deliveries and motion challenges. It clears the face template,
consent and login metadata, anonymises name/email, replaces the password with an
unusable random secret and disables the account. The anonymous user ID remains
as an FK anchor for immutable audit/reviewer history. Audit records are retained
as explicitly required by the project. Other users' registrations and records
are not deleted. Network/DB failures roll back cleanup and are retried; actual
processing can occur shortly after the deadline.

No test or deployment command submits a deletion request for a real account.
The regression tests simulate the deadline using an isolated database.
