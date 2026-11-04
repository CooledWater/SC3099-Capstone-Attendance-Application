# Live impersonation test

You present your **own live face in both attempts**:

| Attempt | Signed-in account | Expected identity result |
| --- | --- | --- |
| `genuine_control` | `wcstudent1@example.com` (your enrolled face) | Match |
| `impersonation_test` | `student1@gmail.com` (another person's enrolled face) | Mismatch |

Use the normal two-blink check-in flow and existing diagnostics. Run commands from
the repository root in macOS Terminal, with the local Docker stack running.

## 1. Prepare both accounts

- Both accounts must be actively enrolled in the same test course, with camera
  and location consent and their existing face enrollments. Keep those enrollments.
- Stay inside the course geofence. Keep the camera, lighting and location the same.
  Prefer an approved browser profile for each account on the same capture device;
  switching accounts in one browser can introduce a separate shared-device flag.
- Use an instructor/admin login for session setup. Submissions create real test
  attendance records; keep recognition thresholds and PAD settings unchanged.

## 2. Build the extended diagnostics and create fresh sessions

Build both service images so the new Hamming fields survive the full diagnostic
path. Keep the normal root `.env` and existing recognition/PAD settings:

```sh
docker compose build face-recognition backend
```

The existing setup helper now supports explicit impersonation assignments. It
enables **motion, liveness and face matching** for both sessions:

```sh
export IMP_TRIAL="$(date -u +%Y%m%dT%H%M%SZ)"
export IMP_CONFIG="new-tests/impersonation-${IMP_TRIAL}.json"
export IMP_REPORT="new-documentations/impersonation/impersonation-${IMP_TRIAL}.md"
python3 new-tests/prepare_video_replay.py --trial-type impersonation \
  --control-account wcstudent1@example.com --test-account student1@gmail.com \
  --config "$IMP_CONFIG"
```

Enter the instructor/admin credentials and choose the course containing both
accounts. Continue after both session IDs are printed; wait about one minute for
activation. They last 60 minutes. If setup fails, inspect the partial config and
use a fresh filename for another run.

The new session names contain **`genuine_control`** and **`impersonation_test`**.
The config records each intended account, the same live presenter, and expected
identity result. Check the printed assignments before continuing. Do not reuse
the old replay-labeled sessions or historical config.

## 3. Enable diagnostics and start collection

In the same terminal, enable diagnostics for only these two sessions:

```sh
export CHECKIN_DIAGNOSTICS_ENABLED=true
export CHECKIN_DIAGNOSTIC_SESSION_IDS="$(python3 -c \
  'import json,sys; print(",".join(s["id"] for s in json.load(open(sys.argv[1]))["sessions"]))' \
  "$IMP_CONFIG")"
docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend
python3 new-tests/monitor_phone_replay.py --mode video \
  --config "$IMP_CONFIG" --report "$IMP_REPORT" --minutes 45
```

Wait for `MONITOR_READY` and leave the terminal open. `--mode video` selects motion
challenge collection; the config selects impersonation reporting. The report
shows planned account assignments before any submission, then updates automatically
with scoped scalar measurements. Verify service health in another terminal if needed:
`curl -fsS http://localhost:8000/health` and `curl -fsS http://localhost:8001/health`.

## 4. Perform the attempts

1. **Control:** sign in as `wcstudent1@example.com`; confirm the displayed account.
   Open `genuine_control`, select **Start challenge**, blink twice, select
   **Verify this sequence**, then finish check-in if verification passes.
2. **Test:** sign out, sign in as `student1@gmail.com`, and confirm that account.
   Open `impersonation_test` and repeat the same steps with **your own live face**.
   If verification fails, record the message; no attendance submission is needed.
3. Record the account, session/challenge ID, time, UI result and any device/location
   flags for each attempt. Check saved attendance ownership/status in the dashboard.
   The report's account assignment is operator-provided; it does not prove which
   account was authenticated. Confirm it against the app and saved record.

## 5. Interpret results and stop

- **Valid control:** motion verification passes and attendance is saved for your
  account, ideally `approved`. Investigate a failed control before drawing conclusions.
- **Identity rejection:** the test records `motion_verified.passed=false`, with
  `motion_sequence.diagnostics.reason=identity_failed` or `identity_threshold`.
  Compare `face_match_score` with the recorded `face_match_threshold`; a failed
  challenge normally creates no attendance record.
- **Identity acceptance:** the test passes motion verification. An independently
  confirmed `approved` record for `student1@gmail.com` establishes end-to-end
  impersonation acceptance in this trial. A later device/location flag still
  requires reporting that the identity check passed.
- **Inconclusive for identity discrimination:** no-face/capture/blink failure,
  passive liveness/PAD rejection, unavailable service, or missing diagnostics.
  A blocked attempt alone does not establish a face mismatch. Liveness may be
  unevaluated when identity fails early; missing values are not measured zeros.

Each challenge now includes an **Identity comparison** table: the minimum score
and cutoff/margin, comparison count, template bit count, effective Hamming fraction
boundary, maximum accepted differing bits, observed distance extrema and version
labels. The per-comparison trace records frame/time, face detection, measured
Hamming distance/fraction, identity score and verdict. Lower Hamming distance means
more similar templates. No images, embeddings, template hashes or SimHash seed are
written to the report. At most 64 comparisons are displayed (first 63 plus latest);
truncation is explicit and extrema/count still cover every observed comparison.

`hamming_evaluated=false` means no usable comparison template; distance stays unknown.
Missing Hamming fields suggest older service images or an incomplete service result,
not zero distance. Historical logs cannot gain these measurements retroactively.
Changing `FACE_MATCH_THRESHOLD` alone rescales scores and cutoff together in the
current matcher. Evaluate the Hamming boundary across repeated genuine/impostor
trials before changing calibration; leave it unchanged for this repeat trial.

The monitor exits after both terminal outcomes, on timeout, or on Ctrl-C, and
attempts to disable diagnostics in both services. Preserve the report and attendance;
use fresh sessions for repetitions. For manual cleanup, run in another terminal:

```sh
CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
  docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend
unset CHECKIN_DIAGNOSTICS_ENABLED CHECKIN_DIAGNOSTIC_SESSION_IDS
docker compose exec -T backend python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
docker compose exec -T face-recognition python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
```

Both checks should print `false ''`. Service recreation briefly interrupts requests.
