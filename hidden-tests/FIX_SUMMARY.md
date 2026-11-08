# Handoff fixes — 7 November 2026

Implemented the functional fixes from `HANDOFF.md`, including the classroom
security and travel policies explicitly approved in the conversation. `docs`
and the original `RESULTS.md` / `results.json` assessment evidence are unchanged.
All services, migrations and destructive cleanup tests used owned temporary
databases; the running application and shared database were not modified.

## Findings and fixes

- **Concurrent identity verification:** isolated the shared dlib HOG scanner as
  unsafe under mixed native concurrency. Serial detections found one face each;
  a direct concurrent detector probe aborted/crashed. A separate 40-call encoding
  probe using fixed boxes produced no descriptor changes. Each worker now owns
  its HOG detector, retaining the existing detector/upsampling/box conventions.
  Native identity thresholds, enrollment templates and PAD decisions are unchanged.
  New regressions cover 80 mixed detector calls, ten mixed HTTP rounds, and health
  during real native inference across repeated application lifespans.
- **Default classroom safeguards:** consent, exact Redis rate boundaries,
  refresh replay protection/atomic rotation and logout revocation now apply in
  both profiles. Default public registration retains all four classroom roles.
  Stricter registration/evidence rules remain opt-in. Redis outages fail closed;
  new default-profile tests explicitly verify outage and role compatibility.
- **Append-only audit storage:** PostgreSQL ALWAYS triggers reject UPDATE,
  DELETE and TRUNCATE; SQLite triggers reject UPDATE, DELETE and replacement
  INSERT. Existing ORM guards and transactional inserts remain. Tests exercise
  an intentionally write-granted, non-owner PostgreSQL role as well as migrations
  from an unprotected legacy schema. No audit rows were rewritten.
- **Independent retention:** check-ins receive exactly 30 days from submission.
  The existing deletion clock now purges due check-ins, push deliveries and
  optional risk children in one transaction, independently of account deletion.
  Equality, one-microsecond boundaries, legacy NULL deadlines, retry/rollback,
  snapshot/audit preservation and concurrent PostgreSQL cleanup workers are tested.
  Existing student-cleanup schema inspection now reuses its transaction connection.
- **Impossible travel:** approved policy compares the latest located submission
  within 24 hours, allowing both accuracy radii plus 1 km of noise. More than
  1,200 km/h flags for review without creating an automatic rejection. Threshold,
  plausible-travel, uncertainty and noise cases are covered.
- **Proxy trust:** a shared backend launcher trusts no forwarded headers unless
  exact upstreams are configured. Docker and the assessment runner use it; Compose
  passes `FORWARDED_ALLOW_IPS`. Real trusted/untrusted Uvicorn paths are tested.
- **Load correctness:** a PostgreSQL benchmark exposed connection-reacquisition
  starvation with eight HTTP slots and three pooled connections (97 successful
  check-ins, three HTTP 500s). HTTP admission now follows the retained pool size;
  the repeat completed 100/100 native check-ins with correct storage/audit pairs.
  Native inference admission defaults to four concurrent requests, and health
  bypasses its queue. New password hashes honor documented `BCRYPT_ROUNDS`
  (default/minimum 10); existing higher-cost hashes retain their verification cost.

Deployment instructions and the exact approved policies are in
[`new-documentations/HIDDEN-TEST-FIX-POLICIES.md`](../new-documentations/HIDDEN-TEST-FIX-POLICIES.md).
Existing databases require the explicit schema-owner Alembic upgrade described
there. It has **not** been applied to live data. Cleanup runs at startup and then
every 60 seconds, up to 500 due rows per worker/tick; failures roll back and retry.

## Endpoints reused

No new HTTP endpoints were introduced. Changed behavior uses existing routes:

- `/api/v1/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, their
  dashboard equivalents and existing authentication aliases.
- Authenticated API dependencies, especially `/api/v1/users/me` and
  `POST /api/v1/checkins/`.
- Existing audit, check-in history, attendance/statistics and export reads reflect
  database protection/expiry without changing their response contracts.
- `/face/enroll`, `/face/verify`, `/face/match`, `/liveness/check`,
  `/liveness/sequence` and `/health` reuse the isolated native models/queue.

## Checks and actual outcomes

Final results and measurements are also recorded in [`FIX_RESULTS.json`](FIX_RESULTS.json).

| Check | Outcome |
|---|---|
| Original full suite before fixes | 169 passed, 19 failed, 2 skipped; the extra load failures followed a stalled biometric workload. This run overlapped diagnostic/build work and is not a clean performance comparison. |
| Functional hidden-style suite, SQLite, interpretations enabled | 181 passed, 2 skipped, 7 stress cases deselected |
| Functional hidden-style suite, PostgreSQL, final source | 182 passed, 1 skipped, 7 stress cases deselected |
| Original full suite after functional fixes, assertions preserved | 181 passed, 2 skipped, 7 stress setup errors: see below |
| Public HTTP suite, final source | 102 passed, 1 existing SQLite concurrency skip |
| Relevant backend/security/audit/device/notification/history regressions | 222 passed, 8 PostgreSQL-only skips in the SQLite run |
| New storage regressions in disposable PostgreSQL | 18 passed, 1 SQLite-specific skip |
| Existing PostgreSQL-only device concurrency regressions | 4 passed, 31 other cases deselected |
| Native queue/identity/PAD/liveness plus older face/demo regressions | 104 passed, 3 pre-existing failures reproduced on unchanged Git source |
| Motion/landmarker/random-motion regressions, including native sequence smoke tests | 107 passed |
| Regression-runner inherited database override isolation | 1 passed using an intentionally invalid override; no external database contacted |
| Compilation and `git diff --check` | Passed |

The final native run's three failures concern an old expected 23-bit calibration
boundary and two tests for absent demo-override settings. The same three fail on
an unchanged `HEAD` snapshot (3 failed, 8 passed for that focused baseline).
They were not hidden by retuning thresholds or weakening assertions. An older
AST/mock session-deletion test also has two failures on unchanged `HEAD` (2
failed, 15 passed). An exploratory wider HTTP/session run returned 75 passed,
4 failed and 81 setup errors: legacy consent/device fixtures, those two stale
session mocks, and extra audit events from an intermediate fixture change. The
relevant final audit fixture now opts in students and supplies real
signed device proofs; test assertions are unchanged.

The full assessment's shared stress population tries to log in 100 users from
one IP during setup. With the approved 60/hour limit, setup receives 429 and all
seven workloads error before measurement. Its 100 same-user duplicate assertion
also conflicts with the 10/minute check-in limit. These assertions are preserved.
A separate benchmark models 100 source addresses through an explicitly trusted,
owned test proxy and keeps all security/native processing enabled. Its duplicate
workload requires exactly one 201, nine 400s and ninety 429s, with one stored row.

### Native load limitations

The supplemental benchmark checks all response and database/audit invariants,
uses native models, and excludes provisioning from timed windows. Photograph
results are computation evidence, not confirmed genuine live presentations.
SQLite runs use local macOS arm64 processes; PostgreSQL runs use the separate
PostgreSQL 15 Compose project. Docker reported 10 CPUs and about 7.75 GiB RAM;
existing application containers were left running. No intended assessor-machine
budget or authoritative load cutoff is available.
The owned assessment Compose stack was removed after results were retained.

Both environments completed 100 real logins, 100 native identity comparisons
and 100 full native biometric check-ins with correct status/storage invariants.
The final PostgreSQL p95s were 1.4411 s for login, 10.4443 s for comparisons,
22.0622 s for full native check-in, and 0.1942 s for health during mixed reads.
**The inferred two-second native p95 goal remains unmet.** Correctness and pool
timeouts are fixed; this work does not claim the native latency issue is solved.
See the JSON report for the final SQLite measurements and all workload counts.

## Specification gaps and remaining evidence

- Physical genuine/print/screen/video evidence was not supplied; that corpus
  remains skipped. PWA permissions, physical presentations and real GPS spoofing
  still need the manual checks in the original README.
- Actual deployed proxy hops/header sanitation remain unverified. Proxy users
  share the direct upstream's IP bucket until its exact trust configuration is
  established; raw uvicorn commands can override the launcher's safe defaults.
- The original same-IP/same-user stress expectations need reconciliation with
  mandatory rate boundaries. No assertion was changed to hide this contradiction.
- Native p95 remains above the local goal; profiling/optimization on the intended
  deployment budget is still required. No timeout or latency target was raised.
- Historical attendance numerators and exports lose expired check-ins while
  denominator snapshots/audit logs remain. Long-term absence/analytics semantics
  beyond the retention window need a product policy; no extra PII archive was added.
  Previously downloaded exports and PWA IndexedDB attendance snapshots are outside
  the server cleanup boundary. The PWA filters ended sessions on read and clears
  snapshots on writes/logout; independent browser-storage expiry remains unverified.
- SHA-256 wording versus the existing cancelable SimHash representation,
  encryption-at-rest/key management and encrypted attestation-token contracts
  remain unresolved. The matcher/storage contract was deliberately preserved.

## Files changed

- Backend: `module2-backend/app/{admission,auth,data_deletion,main,models,security}.py`;
  new `app/{audit_storage,server,travel}.py`; `module2-backend/Dockerfile`;
  `module2-backend/alembic.ini`; new `migrations/env.py` and
  `migrations/versions/20261107_01_audit_retention.py`.
- Face service: `module3-face-recognition/app/{config,detection,main}.py` and new
  `app/admission.py`.
- Deployment/test setup: `docker-compose.yml`, `hidden-tests/{harness,service_runner}.py`,
  `hidden-tests/README.md`, `tests/conftest.py`, and existing
  `new-tests/test_{advanced_security_audit,audit_logs,database_admission}.py` fixtures/checks.
- New regressions/runners: `new-tests/test_{classroom_security,hidden_storage,native_detector_isolation,proxy_trust}.py`,
  `isolated_security_fixtures.py`, `run_hidden_fix_regressions.py`, and
  `measure_hidden_fix_load.py`.
- New reports: `new-documentations/HIDDEN-TEST-FIX-POLICIES.md`, this summary and
  `hidden-tests/FIX_RESULTS.json`.

The pre-existing untracked impersonation report/JSON were left untouched.
