# Handoff fix policies and deployment

Approved in the fixing conversation on 7 November 2026 (Asia/Singapore).
The authoritative `docs` directory has not been changed.

## Classroom and deployment security

The default classroom profile now enforces camera and geolocation consent before
check-in, Redis rate limits (60 login attempts/IP/hour, 10 registrations/IP/hour,
10 check-ins/user/minute, 1,000 authenticated calls/user/hour), atomic refresh
rotation/replay detection, and refresh-cookie revocation on logout. Redis is a
required dependency; outages return 503 on protected operations. Health remains
available. Revocation markers live until their token expires.

Classroom public registration still supports student, TA, instructor and admin.
`STRICT_SECURITY_MODE=true` additionally restricts public registration to students,
validates the deployment secret, and requires session-mandated biometric evidence.
The documented missing-biometric service fallback remains available in the default
profile, with missing evidence flagged and no fabricated pass. There is no new
security bypass or assessment-only switch in application code.

New password hashes use `BCRYPT_ROUNDS` (default 10, minimum 10), matching the
security specification. Previously stored cost-12 hashes continue to verify at
their stored cost. Operators can select 12 as recommended by the specification.
No stored hashes are rewritten by this change.

Independent regression scenarios use a private Redis instance and reset only
rate keys between tests. Controls remain enabled within each test. The hidden
assessment harness now supplies real private Redis to both existing profiles
and uses the backend's deployment entry point. Its assertions are unchanged.

## Impossible travel

The latest located check-in for the same student, of any status, is considered
when its server timestamp is within the preceding 24 hours. Future timestamps
and malformed historical coordinates/accuracy are ignored. No prior record means
no signal. The existing account lock in device resolution serializes PostgreSQL
check-ins before this history query.

Calculate great-circle distance, subtract both submitted GPS accuracy radii and
a 1 km noise allowance, and clamp the result to zero. Emit `impossible_travel`
when the remaining distance exceeds 1,200 km/h multiplied by elapsed server time.
Equality is allowed. At zero elapsed time, movement beyond the uncertainty/noise
allowance is flagged. This requests review and raises the combined risk to the
session review threshold; it never overrides an existing rejection or creates
a hard rejection. The signal contains type/severity/weight only. A zero signal
weight does not claim a calibrated additional contribution to biometric risk.

Client-provided coordinates/accuracy cannot establish authentic location. This
policy does not certify resistance to GPS spoofing or physical impersonation.

## Audit protection and migration

Fresh PostgreSQL/SQLite audit tables receive storage-level guards from metadata
creation. PostgreSQL rejects UPDATE, DELETE and TRUNCATE with an ALWAYS trigger;
SQLite rejects UPDATE, DELETE and replacement INSERT. Ordinary inserts remain
transactional with their business action. Existing ORM guards remain as well.

Upgrade existing, already provisioned databases with the schema-owner connection:

```sh
# Set DATABASE_URL explicitly to the intended database before executing.
python -m alembic -c module2-backend/alembic.ini upgrade head
```

The migration requires an explicit environment URL and does not load the root
`.env`. It installs the audit guards, adds the check-in deadline index and fills
NULL deadlines from `checked_in_at + 30 days` in bounded batches. It preserves
existing deadlines and every audit row. The existing metadata bootstrap still
provisions new application tables; this revision upgrades that existing schema.
Downgrade is refused because removing audit protection is not a safe rollback.

Use a separate schema owner for migration. The application role should have
SELECT/INSERT on audit logs and no schema ownership, DDL, TRUNCATE or trigger-
administration privileges. Triggers also block mistaken UPDATE/DELETE/TRUNCATE
grants, as verified using a non-owner PostgreSQL role. A database administrator
who can drop/disable database objects remains outside this protection boundary.
No migration was executed against live/shared data during this work.

## Independent check-in retention

API-created check-ins receive a deadline exactly 30 days after `checked_in_at`.
The existing deletion clock runs independent check-in and student cleanup jobs
immediately at backend startup, then every 60 seconds. Each check-in transaction
claims at most 500 due records, ordered by submission time, using PostgreSQL
`FOR UPDATE SKIP LOCKED`; multiple workers can process disjoint batches. A record
is due when its deadline is less than or equal to the job time. Legacy NULL
deadlines also expire at `checked_in_at + 30 days` during migration rollout.

Push deliveries and optional `risk_signals` children are removed before their
check-in. Parent/child deletion is one transaction; errors roll everything back
and the next clock tick retries. Audit rows, subscriptions, student accounts and
session enrollment-denominator snapshots are preserved. Startup after downtime
processes the backlog in the same bounded batches; a large backlog needs multiple
ticks. Cleanup requires a running backend and available database.

The frontend, dashboard, roster, statistics and exports already read check-ins
through the backend: expired rows disappear from those online results. Snapshot
denominators remain frozen, while check-in counts/numerators shrink. No new
per-student historical archive or export exception is introduced. Long-term
attendance analytics/absence semantics beyond retention remain a product-policy
gap; indefinite immutable audit rows are retained as required.
The PWA also stores minimal attendance status/time/risk snapshots in IndexedDB.
Ended sessions are filtered on read, and snapshots are pruned on writes/logout;
there is no independent browser timer that the server cleanup job can control.
Already downloaded exports likewise cannot be erased by a server database job.
Browser-storage retention remains a separate manual verification boundary.

## Proxy trust and native capacity

Start the backend using `python -m app.server` from `module2-backend` (the Docker
entry point uses this launcher). It trusts no forwarded headers by default.
`FORWARDED_ALLOW_IPS` can name the exact upstream IPs/CIDRs whose proxies sanitize
and append the real peer address. Compose passes this variable explicitly. Avoid
wildcard trust on an exposed backend. Raw uvicorn invocations can select different
trust settings and must be configured explicitly.

The repository includes Next.js and Vite proxy routes, but no stable deployed
trusted-hop inventory or proven upstream header-sanitization contract. Until
that topology is verified, proxied users share the upstream peer's IP bucket.
Actual trusted and untrusted Uvicorn paths were tested with explicit peer settings.

dlib HOG detectors are owned by each worker, rather than sharing the mutable
`face_recognition` singleton. MediaPipe already owns models per thread. Encoding,
identity thresholds, enrollment templates and PAD/liveness decisions are unchanged.
`FACE_INFERENCE_CONCURRENCY` bounds simultaneous face/liveness requests before
they occupy worker threads (default 4, range 1–64). This limits model initialization
and contention; health/risk/metrics requests do not join this inference queue.
Backend HTTP admission also follows the actual retained database pool capacity
(three connections for the current PostgreSQL configuration). This prevents
connection reacquisition starvation under biometric load, without increasing
the shared database connection budget.

Supplemental 100-client benchmarks use a separately configured, owned test proxy
with 100 distinct source addresses. They exercise real password checks, native
models, Redis and persistence, with provisioning outside timed windows. The raw
assessment's 100 same-IP logins and 100 same-user duplicates conflict with the
approved 60/10 limits; its assertions are preserved and reported separately.
The two-second p95 target is still an inferred local goal, not a confirmed
assessor threshold. Native computation benchmarks do not replace physical
genuine/attack capture evidence or benchmarks on the eventual deployment budget.
