# Security, privacy, biometric, and load audit — 23 October 2026

This is an evidence-based audit, not a guarantee about unseen grading tests.
Tests ran in a separate Docker network with disposable PostgreSQL/Redis and
source-mounted backend/face containers. No stress traffic or test accounts were
sent to Supabase. The shared application was not restarted or put in strict mode.

## Findings and fixes

- **100-user worker/connection starvation:** database connection waiters occupied
  synchronous worker threads, preventing connection holders from completing.
  An asynchronous admission queue now limits database-backed requests before
  they enter that pool. Health and metrics remain available outside the queue.
- **Duplicate submission race:** concurrent requests could both pass the early
  duplicate check, then expose a uniqueness violation as HTTP 500. The commit
  now rolls back and returns the documented duplicate response. Verification
  consumption and audit inserts remain in the same transaction.
- **Malformed numeric inputs:** NaN could cause HTTP 500 while serializing a
  validation error. Numeric inputs must now be finite; coordinates, risk
  thresholds, radius, and GPS accuracy have appropriate range checks. Zero
  radius remains supported by the existing geofence logic.
- **Sensitive validation input:** HTTP 422 errors no longer echo the submitted
  input or validator context, including passwords and potential image payloads.
- **Bcrypt input length:** passwords are bounded to 72 UTF-8 bytes to prevent
  silent truncation or backend failures, including multi-byte Unicode cases.
- **Optional strict security:** enabled explicitly with `STRICT_SECURITY_MODE`.
  Its default is false to preserve the published classroom registration and
  legacy check-in contracts.
- Two additional regression tests had outdated assumptions: query counts now
  include the lifecycle synchronization queries, and audit-filter partitioning
  uses result totals rather than the first page's length. Public tests were
  not modified.

## Optional strict mode

Strict mode adds:

1. Student-only public self-registration; staff/admin creation uses existing
   administrator-controlled endpoints. Provision an administrator before
   enabling strict mode; a fresh strict installation has no public admin bootstrap.
2. Camera/location consent and required biometric evidence checks. Missing
   evidence is not treated as a successful verification.
3. Atomic Redis rate limits: registration 10/hour/IP; login 60/hour/IP;
   authenticated API 1000/hour/user; check-in 10/minute/user. Redis outages fail
   closed with HTTP 503. The IP is the server-observed peer, not an arbitrary
   forwarded header; proxy topology affects the effective IP bucket.
4. Unique refresh tokens, atomic one-use rotation, and logout revocation.
   Used token fingerprints expire with the token. Existing access tokens retain
   their normal expiry; logout does not revoke every issued access JWT.
5. Secure refresh cookies by default and startup checks for a non-placeholder
   JWT secret of at least 32 characters and a Redis URL.
6. Configurable exact CORS origins, rejecting wildcards and path-bearing origins.

Configure the untracked root `.env` before enabling strict mode:

```dotenv
STRICT_SECURITY_MODE=true
JWT_SECRET=<a securely generated secret of at least 32 characters>
# Optional exact browser origins; JSON arrays or comma-separated origins work.
CORS_ORIGINS=http://localhost:3000,http://localhost:8501
```

Compose supplies the existing Redis URL. Rebuild/recreate the backend to apply.
Do not turn strict mode on for the public suite: its fixtures explicitly depend
on privileged self-registration and legacy evidence-free check-ins. Secure
cookies require HTTPS for normal browser use; the ngrok HTTPS proxy supports it.

## Measured load results

Single local Docker instance, PostgreSQL 15, existing three-connection pool,
100 distinct authenticated students. Account setup and password hashing were
outside the measured request window; this does not measure 100 simultaneous
bcrypt logins or native face analyses.

| Test | Before | After |
|---|---|---|
| 100 concurrent own-profile reads | 22 HTTP 200; 78 HTTP 500 | 100 HTTP 200; p95 0.189 s |
| 100 concurrent distinct-student check-ins | 30 HTTP 201; 70 HTTP 500 | 100 HTTP 201; p95 1.207 s |
| 10 simultaneous first check-ins, one student/session | 1 HTTP 201; 7 HTTP 400; 2 HTTP 500 | 1 HTTP 201; 9 HTTP 400 |
| 100 refresh attempts reusing one token, strict mode + real Redis | Not protected in compatibility mode | 1 HTTP 200; 99 HTTP 401 |
| Strict-mode login limit, real Redis | Not enforced in compatibility mode | HTTP 429 at configured boundary |

Results are not Supabase/network benchmarks or guarantees on another machine.
The reproducible concurrency runner is `new-tests/run_concurrency_audit.py`.
It refuses Supabase URLs and requires `SAIV_AUDIT_DISPOSABLE_DATABASE=1`.
Run only with a disposable database and the isolated backend URL it targets.

## Privacy inspection

The scratch PostgreSQL database had no binary/BLOB columns, no matching common
raw-image/base64 prefixes in inspected text columns, no malformed non-null
64-hex template fields, and no non-bcrypt API-created password records. This is
schema/value inspection of the scratch dataset, not proof that arbitrary image
encodings can never be stored. Deliberate non-login stress-test placeholder
passwords were excluded from the bcrypt check.

The existing root database configuration uses Supabase with `sslmode=require`.
This checks configuration only: the audit did not inspect Supabase's storage
settings, verify encryption at rest, or establish certificate/hostname validation.
Password hashing and database transport encryption are different properties.

## Coverage and remaining risks

- The public suite passes with its pre-existing skipped concurrent-check-in test;
  the separate PostgreSQL load probes above exercise that missing category.
- Face-service regressions cover malformed/oversized images, same/different
  identity examples, template handling, synthetic presentation patterns,
  signature verification, temporal sequence validation, and native execution.
  Only six provided identity photos are available, not a held-out real print,
  screen-replay, mask, or deepfake attack corpus. No APCER/BPCER accuracy claim
  can be made; verify these attacks on real devices with consented test data.
- GPS range, distance, accuracy, and geofence checks do **not** prove a location
  is authentic. Browser coordinates are client-supplied. There is no trusted
  location attestation or demonstrated robust GPS-spoof detection.
- Network scoring uses IP/user-agent heuristics, not a verified VPN/proxy
  intelligence service. Private IP does not prove a VPN.
- Standalone device-signature verification proves possession of the submitted
  key, not freshness of a server-issued one-use challenge. The motion workflow
  has server-owned expiry, ownership, session binding, and consumption checks;
  do not generalize its replay guarantees to every device-attestation request.
- Matching templates are deterministic SimHash-derived biometric codes, not
  encrypted photographs or a demonstrated irreversible cryptographic embedding
  hash. Their privacy/linkability properties need separate assessment.
- Compatibility mode intentionally retains the published privileged-registration
  and legacy evidence-free check-in behavior. Hidden tests expecting strict
  production controls in default mode may therefore still fail.
- Default Compose credentials remain development placeholders. Strict mode
  refuses the default JWT placeholder. The patch does not claim to provide
  end-to-end encryption or harden every infrastructure service.

## Files and endpoints

Implementation: `module2-backend/app/admission.py`, `security.py`, `auth.py`,
`schemas.py`, `main.py`, and `docker-compose.yml`. New checks live under
`new-tests/`; accompanying count/pagination regression corrections are documented
above. Existing auth, course, session, and check-in endpoints are reused; no new
public endpoint or database schema is introduced.

Machine-readable evidence and final test totals accompany this report.

## Final verification totals

| Group | Result |
|---|---|
| Public HTTP suite | 102 passed, 1 pre-existing skip |
| Face, liveness, motion native/sequence checks | 47 passed |
| New security and admission checks | 26 passed |
| Nine backend regression suites | 170 passed; includes a wrapper running 28 motion subcases |
| Frontend client, attendance, PWA scope/gesture regressions | 33 passed |
| Frontend TypeScript, Compose validation, backend image build | Passed |

The initially skipped public concurrency case was supplemented by the separate
100-user PostgreSQL probes. The audit-log test was rerun successfully after
correcting its pagination assumption. Public tests remained unchanged.

## Reproduce in disposable storage

The audit Compose file uses tmpfs for PostgreSQL data and exposes no host ports.
It uses the locally built backend/face images and mounts source read-only.

```bash
mkdir -p /tmp/saiv-audit-results
docker --context desktop-linux compose -p saiv-hidden-audit -f new-tests/docker-compose.audit.yml up -d
# HTTP fixture plugin must be explicit when running tests under the face image.
docker --context desktop-linux compose -p saiv-hidden-audit -f new-tests/docker-compose.audit.yml exec -T --user 0 -e PYTHONPATH=/repo/tests -e TEST_BACKEND_URL=http://backend:8000 -e TEST_FACE_URL=http://face:8001 face python -m pytest /repo/tests/public -p conftest -q -p no:cacheprovider
# This seeds 100 users only in the disposable audit database.
docker --context desktop-linux compose -p saiv-hidden-audit -f new-tests/docker-compose.audit.yml exec -T -e PYTHONPATH=/app -e SAIV_AUDIT_DISPOSABLE_DATABASE=1 -e SAIV_AUDIT_BACKEND_URL=http://127.0.0.1:8000 -e AUDIT_RESULTS_DIR=/results backend python /repo/new-tests/run_concurrency_audit.py
# Removes only this disposable project; tmpfs test data is intentionally lost.
docker --context desktop-linux compose -p saiv-hidden-audit -f new-tests/docker-compose.audit.yml down --remove-orphans
```

The patched backend image was built but the shared running application was not
recreated. No commits or pushes were made as part of this audit.
