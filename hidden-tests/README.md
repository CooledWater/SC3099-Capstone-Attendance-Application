# Hidden-style assessment suite

Post-handoff fixes and current execution results are recorded separately in
[`FIX_SUMMARY.md`](FIX_SUMMARY.md). The baseline reports below and in `RESULTS.md`
remain historical evidence. The current harness uses private real Redis for both
profiles and the backend deployment entry point; assessment assertions are unchanged.

These are independently written tests based on `docs/Briefing.md`, the API,
database, security and integration specifications, and the prior coverage audit.
They are not the assessors' undisclosed tests and do not predict a grade. The
suite is intentionally broader than forty cases; category points do not define
the number of useful regressions.

All additions live in `hidden-tests`, as requested. Application code, existing
public/regression tests, and `docs` are unchanged.

## Run locally

Use Python **3.11** (matching the project's containers), the project's backend
and face dependencies, and a `redis-server` executable. Face dependencies include
native dlib, MediaPipe, OpenCV and the checked-in PAD/landmark models. Installation
of dlib can require CMake and a working compiler/SDK.

From the repository root:

```sh
python3.11 -m venv /tmp/saiv-hidden-env
/tmp/saiv-hidden-env/bin/python -m pip install -r hidden-tests/requirements.txt
/tmp/saiv-hidden-env/bin/python hidden-tests/run.py
```

`run.py` always selects this suite. The equivalent direct command is:

```sh
python -m pytest -c hidden-tests/pytest.ini hidden-tests
```

Include the directory argument when using pytest from the repository root; a
nested pytest configuration alone does not restrict discovery to its directory.
Run without pytest-xdist: rate-limit tests reset their own Redis database.

Useful variants:

```sh
# Native dependency installation is optional for this explicitly reduced run.
python hidden-tests/run.py --backend-only --redis-server=/path/to/redis-server

# Include additional interpretations and all seven 100-user workloads.
python hidden-tests/run.py --include-interpretations --run-stress \
  --junitxml=/tmp/hidden-tests.xml

# Require real physical evidence; missing corpus/families becomes an error.
python hidden-tests/run.py --attack-manifest=/private/path/captures.json \
  --require-physical --include-interpretations --run-stress

# Focused rerun; selectors are applied only within this suite.
python hidden-tests/run.py -k 'geofence or replay'
```

Missing Redis explicitly skips strict-mode cases; it never substitutes an
in-memory mock. Missing native dependencies cause startup failures unless
`--backend-only` is requested. Stress and interpretation cases are skipped unless
enabled. Missing physical evidence is skipped unless `--require-physical` is set.
Read skip totals as missing coverage, never as passing evidence.

## Isolation and execution model

The harness starts unchanged backend and face services in **separate processes**,
binds them to random loopback ports, and sends real HTTP requests. It accepts no
live backend URL and never targets `TEST_BACKEND_URL` or the root `.env` database.
Each backend uses a temporary SQLite file. A private real Redis process uses an
ephemeral port and disables persistence. Both default compatibility mode and
`STRICT_SECURITY_MODE=true` are tested independently.

The only database bootstrap is a disposable administrator, because strict mode
has no public admin registration. Other users, courses, sessions and enrollments
are created through the APIs. Public registration tests continue to allow the
briefing's documented role choices; the suite does not require removing staff
self-registration from the classroom contract.

Direct database access is used for the explicitly privileged privacy audit,
record/audit invariants, expiry manipulation, rollback probes and scheduled
deletion. It is not presented as black-box HTTP evidence. Model results and
application transport are not mocked. Tests use `name` for session creation,
matching the implementation and current clients; the older `session_name`
example remains a documented contract gap.

Temporary data and service logs are retained in pytest's temporary directory for
inspection. The harness terminates every process it starts. Logs and assertion
messages suppress submitted secret/image values. No real capture is copied into
the repository, and no raw image is included in the JUnit properties.

## Disposable PostgreSQL assessment

SQLite does not establish PostgreSQL row-lock behavior or production load
performance. A separate Compose project runs the same suite against PostgreSQL
15 with temporary database storage and no published ports:

```sh
mkdir -p /tmp/saiv-hidden-results
docker compose -p saiv-hidden-tests -f hidden-tests/compose.yml build tests
docker compose -p saiv-hidden-tests -f hidden-tests/compose.yml run --rm tests
docker compose -p saiv-hidden-tests -f hidden-tests/compose.yml down --remove-orphans
```

The default Compose command enables PostgreSQL, interpretations, stress, and a
JUnit report at `/tmp/saiv-hidden-results/hidden-tests.xml`. It uses its own
database service and credentials; it does not extend or restart the app's
Compose project. It builds from the current source rather than potentially
stale application images. The direct-run PostgreSQL guard permits only this
fixed disposable network hostname and database pair.

To run just a subset in Compose, replace its command, for example:

```sh
docker compose -p saiv-hidden-tests -f hidden-tests/compose.yml run --rm tests \
  --postgres -k 'replay or concurrent_registration'
```

## Coverage map

| Briefing category | Automated checks |
|---|---|
| Advanced security, 12 points | Forged/expired/wrong-type JWTs, DB-authoritative roles, cross-account and staff scope, mass assignment, SQL/XSS/CSV injection, exact CORS origins, refresh cookies, consent withdrawal, registration/login/check-in/API rate limits, Redis TTL recovery and real outage, device signature/owner/session/expiry/reuse, transactional nonce rollback, refresh replay/logout/concurrent rotation, geofence edges and impossible travel |
| Privacy audit, 8 points | Bcrypt and cost, sensitive validation responses, all-table schema/value inspection after real enrollment/check-in, JSON and encoded image detection, template format, filesystem/log checks, audit HTTP and direct SQL immutability, check-in retention deadline, password-confirmed deletion and actual purge with audit preservation |
| Advanced face recognition, 10 points | Native same/different identity samples, explicit consent, no/multiple faces, invalid images/references, size limits, concurrent result isolation, risk bounds/sums/monotonicity, metadata privacy, held-out physical capture manifest |
| Liveness, 3 points | Native static-sequence rejection, timing/order/frame/size validation, policy-override rejection, server-owned randomized challenges, owner/retry/expiry/reference binding, real failed sequence cannot become a backend proof, confirmed genuine and attack sequences via corpus |
| Stress, 7 points | 100 distinct profile reads, 100 bcrypt logins, 100 check-ins with database/audit invariants, 100 native face comparisons, 100 backend check-ins with real face/PAD processing, 100 first-submission duplicates, health availability during and after load |

The public suite's permissive checks are not reused: login limits must actually
return 429, retention must have a real deadline, and privacy assertions run only
after explicitly successful setup. Expected missing features are not blanket
`xfail` cases. A failing test remains a visible failure.

The tests do not automatically change code or configuration to make a finding
pass. A specification discrepancy in application behavior is a finding requiring
a separate implementation decision.

## Physical evidence

Copy `attack-manifest.example.json` to a private directory and replace its paths
and labels with independently confirmed captures. Each subject needs consented
enrollment and held-out captures. Include genuine and impostor controls, real
camera captures of prints/screens, and complete genuine/replayed sequences.
Record camera/display, lighting, distance and print conditions alongside the
manifest. A session name or a server decision alone cannot establish what was
physically shown to the camera.

Sequence entries use this shape (provide at least 15 frames with actual capture
timestamps; do not fabricate repeated frames as a genuine control):

```json
{
  "id": "phone-video-01",
  "kind": "screen_video",
  "presentation_confirmed": true,
  "challenge": {"version": 2, "blink_target": 2, "turn_direction": "left", "first_action": "blink"},
  "frames": [
    {"image": "private-captures/video/frame-00.jpg", "timestamp_ms": 0},
    {"image": "private-captures/video/frame-01.jpg", "timestamp_ms": 80}
  ]
}
```

Supported kinds: `genuine`, `impostor`, `print`, `screen_photo`, `screen_video`,
`genuine_sequence`, `deepfake`, `mask`. `--require-physical` requires the first
six kinds. Optional masks/deepfakes extend the briefing's broader vision.
The example deliberately contains no invented captures and is not runnable
evidence. The loader rejects missing files, absent confirmation, duplicate IDs,
enrollment-file reuse, invalid labels and malformed sequence timing.

The corpus tests assert individual outcomes rather than claiming an accuracy
rate from a handful of samples. Report APCER/BPCER or identity error rates only
with an appropriate held-out population and denominator. Direct sequence replay
tests do not by themselves prove freshness of a new server-issued challenge;
run the actual PWA challenge/check-in workflow as well.

## Interpretation and specification gaps

* The actual hidden tests are unavailable; no exact scoring thresholds can be
  inferred. The suite's p95 stress target defaults to **2 seconds**, borrowed from
  the public performance goal, and is configurable with `--stress-p95`. The
  briefing specifies 100 users but no hidden-load latency/hardware threshold.
  Provisioning is outside measured windows. Native biometric load uses the
  provided photograph as computation load, not as a labelled live capture.
* The impossible-travel test uses Singapore-to-London within a minute and
  requires its own `impossible_travel` signal. The briefing names the feature but
  supplies no speed rule. Plausible client-supplied coordinates cannot alone
  establish genuine location; manual spoofing trials remain necessary.
* Forwarded-IP spoofing is a separate interpretation test. It runs stock uvicorn
  defaults and exposes the deployment's proxy-trust assumptions. The documents
  do not define the trusted proxy chain.
* **HTTPS/TLS is explicitly exempted** by `SECURITY-REQUIREMENTS.md`. There is no
  mandatory TLS, certificate or HTTP-to-HTTPS redirect assertion. The internal
  face API is also explicitly unauthenticated by the integration guide.
* Password hashing, hash-only biometrics and encryption are distinct. Shape
  checking a 64-hex template does not prove SHA-256 irreversibility; the current
  matcher uses SimHash-derived codes. No cipher, key management or scope is
  supplied for the briefing's broader “encryption verification.” The suite
  detects raw/secret storage and tests bcrypt, but does not pretend to certify
  database-volume encryption. The documented encrypted attestation-token path
  needs an exercised specimen and defined encryption contract before a credible
  automated ciphertext/rotation test can be written.
* Default compatibility mode intentionally disables several security controls.
  The suite reports resulting failures alongside strict-mode results; it does
  not silently enable strict mode for every test or claim strict-mode results
  describe the default deployment.

Manual assessment still needs to confirm physical presentation and account
ownership, genuine-user completion on actual mobile browsers, GPS-spoofing
behavior, the deployed proxy topology, database/storage encryption and key
management, and coverage of external logging/backups. Filesystem inspection here
is limited to owned service working directories and logs; it cannot prove that
all possible external stores are clean.
