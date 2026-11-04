# Video replay diagnostic instrumentation

Implemented on 30 October 2026. This document describes the instrumentation and a future physical trial; it contains no measured video replay result. Existing image replay reports and everything under `docs/` are preserved.

## What is measured

The existing two-blink check-in flow is unchanged. Opt-in diagnostics record the existing passive-liveness checks on the first and last captured frames, identity sampling count, sequence size/duration, effective thresholds, blink count, stop reason, and the final motion verification result. Each evaluated endpoint frame includes:

- Depth and mesh scores, their thresholds, and their pass/fail flags.
- Texture and color scores, weighted contributions and component weights.
- Presentation integrity, periodic-artifact penalty and integrity components.
- Liveness before the geometry gates, final liveness score and threshold.
- Frame index and capture-relative timestamp.

The report includes a short first/last-frame comparison table and the complete allowlisted scalar records. Depth and mesh remain model-inferred cues, not measurements from a physical depth sensor.

An early failure preserves measurements already completed. A later frame that was never evaluated is explicitly `evaluated: false`, displayed as **not evaluated**, without invented zero scores. If the service cannot supply diagnostics, the report displays **unknown**. The instrumentation performs no additional model checks after a failure or on intermediate frames. A server blink count of zero may reflect an early passive or identity failure before the recorded blinks were processed.

## Scope and compatibility

Both backend and face service must have `CHECKIN_DIAGNOSTICS_ENABLED=true` and the same exact session UUID allowlist in `CHECKIN_DIAGNOSTIC_SESSION_IDS`. Defaults are disabled with an empty allowlist. Existing image replay configuration variables, log prefix, finite-scalar sanitizer, context isolation, report markers and monitor are reused.

Only an authenticated owner's motion challenge establishes the backend diagnostic scope. The backend requests internal sequence details through `X-SAIV-Diagnostic-Session-ID`; the face service independently checks that UUID against its own enabled allowlist. A supplied header alone cannot enable diagnostics. This internal header selects measurements, not authentication or a verification bypass; no client should use it as proof of identity.

`POST /liveness/sequence` returns an additional `diagnostics` object only for opted-in internal requests. The backend sanitizes that object again before logging. The normal student verification response is unchanged, and the existing `motion_challenges.result` retains only its four existing scalar verification outcomes. No schema migration is required. Images, video, base64 payloads, landmarks, embeddings, reference hashes, credentials, arbitrary exception text and unfiltered Docker logs are not written to diagnostic reports or persistence. Diagnostic observers and log-sink failures cannot override the existing verification verdict.

Events carry a server-generated diagnostic ID per request, session UUID and challenge UUID. The challenge UUID correlates issuance, sequence verification, and subsequent attendance submission. Retries receive separate challenges; the report preserves their individual observations.

## Preparing a physical trial

1. Deploy the updated backend and face service with diagnostics initially disabled. Source edits alone do not update the existing running containers:

   ```sh
   CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
     docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
     up -d --build --no-deps face-recognition backend
   ```

2. Through the normal dashboard/API, create two fresh matched sessions for an already enrolled participant: `real_face_control` and `phone_video`. Verify `require_motion_check=true`, `require_liveness_check=true`, and `require_face_match=true` in both. Keep course, actual venue, geofence, time window, risk policy and capture device matched. Use an approved device and its normal signed proof; an unsigned or untrusted device can flag attendance independently of biometric acceptance. Preserve face enrollment, consents, thresholds, recognition algorithms and existing attendance/audit records.

3. Copy [`video-replay-run.example.json`](../../new-tests/video-replay-run.example.json) to a uniquely named run configuration in `new-tests/`. Replace all placeholders with the two real session UUIDs and a UTC timestamp before the first challenge. The configuration contains only the collection start time and presentation labels/session UUIDs; do not add credentials or video data.

4. Enable the same two-session scope in both services:

   ```sh
   export CHECKIN_DIAGNOSTICS_ENABLED=true
   export CHECKIN_DIAGNOSTIC_SESSION_IDS='CONTROL_SESSION_UUID,VIDEO_SESSION_UUID'
   docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
     up -d --no-deps face-recognition backend
   ```

   Replace the UUID placeholders before running. Verify backend and face-service health, and independently confirm their enabled flags and exact allowlists. Record the effective recognition thresholds; repository defaults are 0.85 liveness, 0.80 depth, 0.80 mesh and 0.70 identity, subject to deployment overrides. Do not reduce thresholds for the trial.

5. Create a unique report in this directory containing participant condition notes. Start the reused collector before issuing either challenge:

   ```sh
   python3 new-tests/monitor_phone_replay.py --mode video \
     --config new-tests/video-replay-run.json \
     --report new-documentations/video-replay/video-replay-test-0.md \
     --minutes 45
   ```

   Use the actual unique config/report paths. `--mode video` requires an explicit report path. Wait for `MONITOR_READY` and a successful backend log connection before captures. The current collector targets the local Compose backend container `saiv-backend`.

6. Complete the real-face control through **Start challenge**, two blinks, **Verify this sequence**, and normal check-in submission. For the video trial, replay the participant's prerecorded two-blink clip on a second phone into the same physical capture camera. Start from eyes open, use normal-speed playback, and keep the participant's actual face outside the capture view. Capture is bounded to eight seconds. Let the participant perform the submissions and confirm which presentation was used; session labels do not establish physical ground truth.

Record display phone, capture device/browser, clip duration/frame rate/resolution, brightness, lighting, distance, visible borders/reflections, playback speed, and UI observations. Keep the recording locally on the display phone rather than in Git, reports or log exports.

## Outcomes, retries and cleanup

The video monitor completes each latest observed challenge when either:

- The server records `motion_verified` with `passed=false`: performed sequence rejection, even though the UI never submits attendance.
- Motion verification passes and the corresponding attendance commits: report the actual saved status, including flagged/rejected outcomes.
- The owned motion request fails, expires, or receives unavailable/invalid service results: **inconclusive** for replay detection, not a biometric rejection.

A passed motion sequence without an attendance commit is biometric acceptance with an unconfirmed attendance outcome. A calculated decision is not proof of commitment. A replay with passed motion and independently verified approved attendance is an observed end-to-end acceptance. A device/geofence block does not establish replay detection. A new challenge supersedes the older challenge for automatic completion, while earlier records remain in the report. Once both sessions have terminal outcomes the collector exits; use a fresh run/session pair for further repetitions.

Challenge issuance without verification remains pending. Browser tracking failures/cancellation, uploads rejected before route execution (such as 413/422), authentication failures, and nonexistent/foreign challenges have no scoped server sequence observation. Record the participant-visible outcome separately; do not infer successful replay detection from the lack of records. Cancel/retry and issue a fresh challenge as appropriate.

On normal completion, timeout, Ctrl-C, SIGTERM, stream failure, or report/startup exceptions inside collection, the collector attempts to recreate **backend and face-recognition** with diagnostics disabled and empty allowlists. Existing image mode retains backend-only cleanup and its default behavior. A failed shutdown is reported explicitly. Invalid arguments/configuration stop before collection; disable diagnostics manually if they were already enabled. A hard kill, host failure or unavailable Docker daemon can prevent cleanup.

Manual cleanup is:

```sh
CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
  docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend
unset CHECKIN_DIAGNOSTICS_ENABLED CHECKIN_DIAGNOSTIC_SESSION_IDS
```

After cleanup, independently verify disabled flags, empty allowlists, both service health checks, and saved attendance ownership/status through authenticated reads. Preserve attendance/audit records and participant notes. The collector replaces only its delimited observation section, using the same markers as image replay reports.

## Endpoints and specification gaps

No endpoint is added. Reused endpoints are backend `POST /api/v1/motion/challenges`, `POST /api/v1/motion/challenges/{id}/verify`, `POST /api/v1/checkins/`, existing session/attendance readback, and internal `POST /liveness/sequence`.

The optional motion extension in `docs/API-SPECIFICATION.md` points to the existing motion contract. This instrumentation adds an opt-in internal diagnostic projection without changing normal response fields, request bodies, database schema, failure policy or recognition thresholds. The older 0.60 liveness example differs from the previously approved 0.85/0.80/0.80 policy documented in [threshold implementation](../image-replay/threshold-implementation.md). The fixed two-blink challenge does not establish recording freshness. Browser-only failures remain participant-reported. No changes to `docs/` are proposed.

## Validation

Checks used existing dependency images with source mounted read-only. Backend unit tests use a temporary SQLite database and mocked face transport. Native face/model tests run separately because both services use the `app` package. Public HTTP checks and the real-service smoke used a separate Compose project, `saiv-video-diagnostics-20261030`, with a temporary PostgreSQL database, separate Redis and no published ports. No check targets the user's existing database or produces attendance in the existing application.

| Check | Result |
| --- | --- |
| New sequence diagnostics cases | **16 passed** |
| New backend diagnostics cases | **12 passed** |
| New video monitor cases | **11 passed** |
| Full selected face/motion/policy/native suites, including the 16 new cases | **98 passed** |
| Focused backend/video-monitor/existing image-monitor suites | **26 passed** |
| Backend diagnostics/image-monitor/motion regression combination | **66 passed, 8 existing failures**; before editing it was **43 passed, the same 8 failures** |
| Unchanged `tests/public` on disposable services | **26 passed, 3 failed, 73 setup errors, 1 skipped** |
| Untouched-HEAD backend comparison for `tests/public` | Identical outcome for **all 103 test IDs**, including failures/errors/skip |
| Existing frontend session-policy/restoration component checks | **10 passed, 14 failed** on unchanged test/component sources; all exercised files verified byte-identical to HEAD |
| Real backend + native face-service smoke | Correlated challenge, first/last component scores and verification result; static sequence rejected for `insufficient_blinks`; normal student response unchanged; only the four existing scalar outcomes persisted; **no attendance written** |
| Compose override validation, changed/new Python syntax, example JSON and whitespace | Passed; Compose reports its existing obsolete `version` warning |
| Preservation | All **16** files in `docs/` and historical image replay documentation match their pre-run SHA-256 hashes |

The eight existing backend failures comprise four image-diagnostic expectations that predate the current unsigned-device flagging/risk behavior, and four motion-suite read-query expectations (two expected queries versus three executed). No production device policy, query path, existing assertion or fixture was changed to make these tests pass.

The public suite's fixture passwords do not meet the current registration password policy, causing HTTP 422 failures, dependent setup errors and failed login checks. A read-only HEAD backend in a separate temporary database reproduces all 103 outcomes exactly. The face-recognition public cases all pass. Public tests and password policy remain unchanged. The existing concurrent-check-in skip remains unchanged. Initial attempts to run the optional frontend checks needed the image's Node/TypeScript paths; their final 14 failures occur in untouched frontend tests/components, whose older consent/device-flow mocks do not match the current flow. No frontend or dashboard code was changed by this task.

All four disposable service containers and their dedicated network were removed after verification. Existing application containers were not rebuilt or restarted; the new instrumentation is **not yet deployed or enabled there**. The raw sample-image preparation for the smoke was piped between test processes in memory; only fixed-schema scalar observations were saved. Local QA artifacts are `/tmp/saiv-video-diagnostics-results/backend-monitor.xml`, `public.xml`, `public-baseline.xml` and `smoke-report.md`. The smoke uses a static bundled sample, not a participant-reported phone-video presentation, and establishes wiring rather than replay resistance.

No physical video replay has been performed by this implementation task.

## Files changed

| Files | Purpose |
| --- | --- |
| [`module2-backend/app/checkin_diagnostics.py`](../../module2-backend/app/checkin_diagnostics.py) | Reuse the scalar allowlist and request context for motion events and challenge correlation |
| [`module2-backend/app/face_service.py`](../../module2-backend/app/face_service.py) | Request scoped internal measurements on the existing service call |
| [`module2-backend/app/motion.py`](../../module2-backend/app/motion.py) | Instrument issuance/verification, including failures before attendance |
| [`module3-face-recognition/app/motion.py`](../../module3-face-recognition/app/motion.py) | Observe existing checks and stopping stages without extra inference |
| [`module3-face-recognition/app/motion_diagnostics.py`](../../module3-face-recognition/app/motion_diagnostics.py) | Opt-in gate and source-side finite scalar projection |
| [`module3-face-recognition/app/main.py`](../../module3-face-recognition/app/main.py) | Return internal diagnostic details only for opted-in requests |
| [`new-tests/monitor_phone_replay.py`](../../new-tests/monitor_phone_replay.py) | Add video mode, per-challenge reports, terminal-outcome handling and cleanup |
| [`new-tests/docker-compose.phone-replay.yml`](../../new-tests/docker-compose.phone-replay.yml) | Apply the existing opt-in variables to both services |
| [`new-tests/video-replay-run.example.json`](../../new-tests/video-replay-run.example.json) | Credential-free run configuration template |
| [`new-tests/test_video_replay_sequence_diagnostics.py`](../../new-tests/test_video_replay_sequence_diagnostics.py) | Source projection, scope, early failures and decision parity |
| [`new-tests/test_video_replay_backend_diagnostics.py`](../../new-tests/test_video_replay_backend_diagnostics.py) | Correlation, privacy, persistence/API compatibility and outage handling |
| [`new-tests/test_video_replay_monitor.py`](../../new-tests/test_video_replay_monitor.py) | Completion, retries, interpretation, report preservation and cleanup |
| This document | Setup, operation, limits and validation evidence |
