# Handoff: fix findings from the hidden-style assessment

Prepared 5 November 2026 (Asia/Singapore). Read `RESULTS.md` for measured results,
`results.json` for per-case outcomes, and `README.md` for scope and execution.

## Scope and baseline

The user requested a thorough hidden-style test suite and then documentation
and a handoff for subsequent agents. **No application fix was requested or made
in this implementation turn.** All additions are under `hidden-tests` per the
user's explicit instruction, overriding the ordinary `new-tests` destination for
this suite. The application source baseline is Git commit
`fdd5d0820fbadf14470b58116a73742d76166878`.

The suite launches unchanged application code in separate backend/face processes,
uses real native models and a private Redis process, and creates API data in
owned temporary databases. It does not touch the running application or the
root `.env` database. The public HTTP suite also ran against separate temporary
services: **102 passed, 1 existing concurrency skip**.

## Non-negotiable repository constraints

Read `AGENTS.md` and the user's instructions in the active conversation before
changing product code. In particular:

1. Read all four modules before modifications and evaluate cross-module impact.
2. Follow `docs/DATABASE-SCHEMA.md`, `docs/API-SPECIFICATION.md`, and
   `docs/INTEGRATION-GUIDE.md` for database/API work.
3. `docs` is read-only. Do not rewrite documentation to make code/tests agree.
4. Obtain explicit approval before changes conflicting with documentation, or
   unavoidable conflicts with existing modules. The current brief contains
   conflicting security/classroom assumptions; see the decision below.
5. Run relevant public and regression tests. Ordinary new implementation edge
   tests belong in `new-tests`; preserve this assessment suite's assertions.
6. Finish with files, endpoints, specification gaps and actual check results.

No finding should be hidden by loosening assertions, enabling blanket `xfail`,
changing all tests to strict mode, raising latency limits without disclosure, or
substituting synthetic captures for confirmed physical evidence.

## Reproduce first

Use Python 3.11 and dependencies from `hidden-tests/requirements.txt`:

```sh
python hidden-tests/run.py --redis-server=/path/to/redis-server \
  --include-interpretations --run-stress --junitxml=/tmp/hidden-tests.xml
```

On the audited workstation, an isolated working environment was provisioned at
`/private/tmp/saiv-hidden-venv/bin/python`, with Redis at
`/private/tmp/saiv-hidden-redis/src/redis-server`. These are temporary conveniences,
not project dependencies; do not assume they survive into another session.

Use the standalone Compose project in `hidden-tests/compose.yml` for authoritative
PostgreSQL row-lock verification. Docker configuration validated, but the daemon
was unavailable during this audit. Commands are in the README. Do not redirect
the suite or old concurrency scripts to Supabase/shared storage.

## Priority 1: inconsistent concurrent face verification

Failing case: `test_parallel_identity_comparisons_do_not_mix_results`.

Serial same/different-person controls pass. In the mixed four-worker workload,
some same-person requests return `match_passed=false` and `match_score=0.0`.
The final run returned `face_detected=true` for those failures. This reproduced
in multiple full runs. Inspect the multiple-face early-return path as well as
matching; the response alone does not establish which native stage raced. **This evidence
shows false rejection under concurrency; it does not demonstrate impersonation
or false acceptance.**

Start with:

* `module3-face-recognition/app/detection.py`: `_dlib_locations`, `detect_faces`,
  `detect_face`, the shared `face_recognition` backend and thread-local MediaPipe
  detector handling.
* `module3-face-recognition/app/embedding.py`: `extract_face_embedding` and calls
  through the shared native backend.
* `module3-face-recognition/app/main.py`: `_verify_image` and the no-face path.

The root cause has not been established. Investigate native detector/encoder
thread safety and model ownership, not only HTTP request handling. Diagnose with
bounded counts/booleans; do not log pixels, landmarks, templates or credentials.
Check isolation or a correctly scoped synchronization strategy against the
native throughput tests: a blanket lock may worsen the already measured load
latency. Preserve serial accuracy and repeated-request consistency.

```sh
python hidden-tests/run.py -k parallel_identity
```

Exit criteria: serial controls remain correct; mixed native comparisons remain
correct over justified repeated runs; native load is measured after the fix;
public and Module 3 regressions still pass. Do not retune identity thresholds to
mask a concurrency issue.

## Priority 2: resolve the default security profile decision

Default compatibility mode fails both consent checks, all four rate boundaries,
refresh replay and logout revocation. Strict mode passes those controls with
real Redis. See failing `[compat]` cases in `test_security.py` and
`test_replay.py`.

Sources: `module2-backend/app/security.py` (`strict_mode`, rate and refresh
helpers), `auth.py` (authenticated API bucket), and `main.py` (login, registration,
refresh/logout and check-in consent).

**Do not simply set `STRICT_SECURITY_MODE=true` by default.** Strict mode also
forbids privileged public registration, while the briefing explicitly allows
classroom role registration. Public fixtures create many accounts through that
endpoint. Mandatory consent/evidence enforcement also differs from some legacy
integration examples and fixtures. The user needs a concrete proposal explaining
which controls become unconditional, how classroom test setup remains possible,
and what is an explicit assessment/deployment profile. Seek approval for genuine
documentation/cross-module conflicts under `AGENTS.md`; do not edit `docs`.

After that decision, keep the tests showing the actual deployment profile and
verify exact 60/10/10/1000 boundaries, independent user buckets, expiry recovery,
real Redis outage behavior, atomic refresh rotation and logout revocation. Keep
public role creation compatibility unless explicitly authorized otherwise.

## Priority 3: enforce append-only audit data in the database

Failures: `test_audit_is_append_only_for_direct_database_writes[update/delete]`.
ORM update/delete hooks exist at the bottom of `app/models.py`; direct SQL writes
are currently accepted. The tests always roll back their attempted changes.

Inspect `module2-backend/app/models.py`, `audit.py`, database startup/migration
strategy and database-role privileges. Implement protection at the appropriate
storage boundary, then verify with the application DB role in PostgreSQL as well
as ORM/API tests. Do not rely exclusively on Python event hooks. Preserve all
existing immutable rows and keep normal audit inserts atomic with their actions.
Do not run migration experiments against live audit history.

## Priority 4: independent check-in retention

Failure: `test_checkin_has_thirty_day_retention_deadline`.
Created check-ins have `scheduled_deletion_at=NULL`. The documented field exists
in `app/models.py`, but `main.py:create_checkin` does not assign it.
`app/data_deletion.py:purge_due_students` handles student deletion requests; it
does not establish independent expiry of every check-in record after thirty days.

Implement the documented deadline and an actual cleanup path with meaningful
job tests. A deadline-only fix is insufficient for auto-deletion. Preserve audit
history, handle child risk/push records safely, and assess effects on historical
attendance statistics/snapshots and exports across all four modules. Specify the
job's scheduling/recovery behavior and test the exact due/not-due boundary in
disposable PostgreSQL. Do not accelerate real records for testing.

## Priority 5: GPS and proxy interpretations

`test_impossible_travel_between_two_valid_venues_is_detected` finds no
`impossible_travel` signal for valid venue coordinates in Singapore followed
immediately by London. Geofence/accuracy/range checks pass, but cannot prove
coordinate authenticity. Start at `main.py:_assess_checkin_geofence` and the
stored attendance history. The briefing names the feature without a speed rule.
Agree a documented policy before choosing thresholds; preserve plausible travel
and GPS-noise cases. It is an interpretation test, enabled explicitly.

`test_forwarded_ip_cannot_bypass_login_limit` bypasses the strict-mode IP bucket
by varying `X-Forwarded-For` with stock uvicorn defaults on loopback. Direct
61-attempt login limiting passes. This is **deployment/proxy-trust dependent**:
uvicorn can interpret headers before `request.client.host` reaches application
code. Inspect Docker/uvicorn startup, trusted upstream configuration and reverse
proxy behavior. Establish the actual trusted hop chain; do not blindly trust
headers or categorically disable valid proxy support. Test trusted and untrusted
paths. The docs do not define this topology.

## Priority 6: native load latency

The hundred-user reads, check-ins and duplicates preserve correctness in the
measured SQLite run. All hundred bcrypt logins, native face comparisons and full
biometric check-ins completed with the expected HTTP status, but exceeded the
local two-second p95 target. Exact values are in `RESULTS.md`/`results.json`.

The two-second target is inferred from public performance requirements; the
hidden briefing specifies concurrency without a latency/hardware threshold.
Report measurements and assumptions, rather than treating this target as a
confirmed assessor cutoff. Provisioning is outside measured windows.

Profile face detection, native model ownership, thread contention, connection
admission and repeated inference across backend/face calls. Preserve actual
liveness/face results: bypassing required inference or fabricating passes is not
an optimization. Validate in PostgreSQL on the intended machine/container budget.
Repeat meaningful performance checks after concurrency fixes, since the two
issues may interact. Maintain health responsiveness and one-record/audit
invariants.

## Outstanding evidence, not passing tests

* The physical corpus test is skipped because no independent raw capture dataset
  was supplied. Use `--attack-manifest` and `--require-physical`; the example and
  loader contract are in this directory. Include real genuine controls, prints,
  phone photos/videos, different identities and complete genuine sequences.
  Synthetic samples and old scalar reports do not replace pixel-level evidence.
* The PostgreSQL concurrent device-slot test is skipped outside its Compose
  profile. SQLite results do not establish row-lock behavior.
* Broad encryption-at-rest/cipher/key-management requirements are unspecified.
  The suite verifies bcrypt, data minimization and privacy storage/log scans; it
  does not certify encrypted volumes. The encrypted attestation-token path needs
  an exercised specimen and a defined contract. HTTP/TLS is explicitly exempted
  by the current security specification, and the internal face API is explicitly
  unauthenticated. Do not invent mandatory TLS/service-auth failures.
* Hex template shape does not prove cryptographic irreversibility. Existing code
  labels SimHash-derived codes as an approved cancelable matching representation;
  documents still describe SHA-256. Resolve that requirement explicitly before
  replacing the matcher or changing enrollment compatibility.
* PWA/browser permissions, physical presentation confirmation, deployment proxy
  behavior, external logging/backups and device GPS spoofing still require the
  manual checks in the README. No raw participant captures should be committed.

## Completion checklist for a fixing agent

Keep fixes scoped and reviewable. Confirm the failed behavior first, resolve any
required policy approval, implement the smallest correct change, run its focused
hidden-style tests and existing `new-tests` regressions, then run relevant public
HTTP tests in disposable services. Run native/stress/PostgreSQL checks when the
change affects those boundaries. Update the results with the exact environment,
remaining skips and measured limitations. Preserve this baseline report rather
than silently replacing historical evidence or claiming unseen assessor tests
have been passed.
