# Hidden-style assessment results — 5 November 2026

The completed **190-case** run produced **171 passed, 17 failed, 2 skipped,
0 errors**, in **88.78 seconds**. The existing public HTTP suite separately
produced **102 passed, 1 pre-existing skip**, in 55.69 seconds. These are local
results for independently written tests, not results from the assessors' unseen
suite or an estimated grade.

The source baseline is commit `fdd5d0820fbadf14470b58116a73742d76166878`.
Only `hidden-tests` was added. Product code, `docs`, public tests and existing
`new-tests` were unchanged. No endpoint was implemented or altered.

Per-case results, measurements and relevant source SHA-256 fingerprints are in
[`results.json`](results.json). The fixing-agent plan and approval constraints
are in [`HANDOFF.md`](HANDOFF.md).

## Execution and limits

The run used Python 3.11.10, real Redis 7.2.4 with persistence disabled, separate
backend/face subprocesses on random loopback ports, disposable SQLite databases,
and actual dlib 20.0.1 / MediaPipe 0.10.18 / OpenCV 4.11.0 and checked-in PAD/
landmarker models. No application transport or model results were mocked.
An additional canary exercised the enabled JSON privacy logger and confirmed
redaction of submitted password/image values; this was not an empty-log pass.

The workstation's native SDK required a build-only dlib PNG-support workaround;
the app decodes images through Pillow before native inference. Dependencies and
build products were installed only in temporary storage, not the project venv.
Default service telemetry/access logging was disabled for isolation; enabled
privacy logging was explicitly exercised by its dedicated test. No external
collector, backup store or live production deployment was audited.

The full reproduction command is:

```sh
python hidden-tests/run.py --redis-server=/path/to/redis-server \
  --include-interpretations --run-stress --junitxml=/tmp/hidden-tests.xml
```

The audited temporary Python/Redis executables and original JUnit/log paths are
listed in the handoff. Raw local artifacts include
`/private/tmp/saiv-hidden-handoff.xml` and `/private/tmp/saiv-hidden-handoff.log`;
those paths are session-local. The committed JSON report is the portable result.

## Failing findings

| Finding | Failed cases | Observed behavior |
|---|---:|---|
| Mixed concurrent identity comparisons | 1 | Serial controls pass; four same-person comparisons in the final mixed four-worker workload returned false with score 0.0 and face_detected=true. This is false rejection evidence, not demonstrated false acceptance. |
| Impossible travel interpretation | 1 | Immediate Singapore-to-London submissions at valid venue coordinates produced no impossible_travel signal. A trusted signed device was used so unrelated device flags could not count as GPS detection. |
| Database audit immutability | 2 | Direct SQL UPDATE and DELETE were allowed. The tests rolled back both attempts and verified that audit rows remained intact. HTTP read-only and other audit checks passed. |
| Check-in retention | 1 | A new check-in had scheduled_deletion_at=NULL rather than a thirty-day deadline. Student-request deletion/purge tests passed separately. |
| Refresh replay/logout, compatibility mode | 2 | Reusing a rotated refresh token and refreshing a logged-out cookie token both returned 200. Strict-mode equivalents passed. |
| Consent, compatibility mode | 2 | Check-ins were persisted after withdrawal of either camera or geolocation consent. Strict-mode equivalents returned 403. |
| Rate limits, compatibility mode | 4 | The 61st login, 11th registration, 11th check-in attempt and 1001st authenticated API call were not limited. Exact direct boundaries, TTL recovery and real Redis outage checks passed in strict mode. |
| Forwarded-IP interpretation | 1 | Varying X-Forwarded-For bypassed the strict login IP bucket under stock uvicorn loopback proxy defaults. Direct requests without this header were correctly limited. Actual deployment topology remains to be verified. |
| Local stress latency target | 3 | Hundred-user bcrypt login, native comparison and full biometric check-in p95 exceeded the inferred two-second target. All requests completed with expected HTTP statuses and the checked database invariants held. |

The failure count is seventeen. Findings are preserved as failures, with no
blanket `xfail` or reduced assertions to make the suite appear green. The
forwarded-IP and impossible-travel requirements are explicitly labelled
interpretations. Stress latency is a configurable local target, not a confirmed
hidden-assessment cutoff.

The mixed identity result reproduced in multiple complete runs. This does not
establish its native-library root cause; see the bounded diagnostic details and
investigation entry points in the handoff.

## Hundred-user measurements

Provisioning/enrollment was outside each timed request window. Each workload
used a synchronized start. The p95 calculation uses the nearest-rank 95th
percentile, and the checks fully consume response bodies before stopping timers.

| Workload | HTTP/correctness outcome | Measured p95 | Local result |
|---|---|---:|---|
| 100 distinct own-profile reads | 100 × 200; identity ownership preserved | 0.0834 s | Pass |
| 100 distinct bcrypt logins | 100 × 200; refresh tokens distinct | 2.3863 s | Fail against 2 s target |
| 100 distinct check-ins | 100 × 201; 100 unique student records and correct audit pairs | 0.3131 s | Pass |
| 100 native face comparisons | 100 × 200; expected same-identity matches | 2.1236 s | Fail against 2 s target |
| 100 backend check-ins with real face/PAD processing | 100 × 201; unique records; liveness and match results present | 5.8940 s | Fail against 2 s target |
| 100 simultaneous first submissions for one student/session | Exactly 1 × 201 and 99 × 400; one record | Not a latency assertion | Pass |
| Mixed load with 20 health probes | All requests 200; post-load DB/health probes succeed | Health p95 0.2524 s | Pass against 0.5 s health target |

These are SQLite/local-process measurements, not PostgreSQL/container/Supabase
benchmarks. The biometric load used the provided photograph as computational
input; returned attendance status is not evidence of a genuine live presentation.

## Skips and unverified requirements

1. **PostgreSQL device-slot race:** requires the disposable Compose profile.
   Compose configuration validated, but Docker's daemon was unavailable. The
   image build and PostgreSQL suite were not executed.
2. **Physical attack corpus:** no independent consented, labelled capture dataset
   was supplied. The test is skipped rather than populated with synthetic or
   assumed physical samples. `--require-physical` without the manifest was checked
   and correctly fails collection; required capture families are validated.

Broad encryption-at-rest/key-management scope is unspecified. Bcrypt, raw-image
absence, stored template format, log redaction and deletion were exercised; these
do not certify encrypted volumes or cryptographic template irreversibility.
HTTPS/TLS is explicitly exempted by the current security specification.
The test suite does not add a mandatory TLS or internal-service-auth requirement.

The README identifies manual follow-up for real camera/print/screen trials,
genuine-user mobile completion, GPS spoofing, actual proxy trust, external
storage/logging/backups and encryption configuration.

## Other checks

* All suite Python sources parse; isolated collection yields 190 cases.
* JSON example and Compose YAML parse; Docker Compose configuration validates.
* The privacy inspector and physical-corpus loader tests pass their deliberate
  leak/missing-evidence cases.
* Invalid CLI latency targets are rejected, and strict physical-evidence gating
  fails clearly when no manifest is provided.
* `git diff --check` passed. Source/docs/public/regression directories have no
  tracked changes from this task.

Default-profile security behavior, broad encryption scope, GPS/proxy policy,
the latency cutoff and the old session_name/SHA-256 examples remain explicit
specification gaps. The handoff requires policy approval where a product fix
would conflict with documentation or existing module contracts.
