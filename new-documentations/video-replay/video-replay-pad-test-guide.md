# Run a video-replay test with motion and PAD diagnostics

Run from the repository root in macOS Terminal (zsh or bash). You need Docker
Compose, Python 3, an instructor/admin login, an actively enrolled test student
with face enrollment and camera/location consent, and a second phone playing
that student's prerecorded two-blink video. No local pip installation is needed.
Use the same approved capture device and venue/geofence for both presentations.

The current policy requires two complete blinks, sampled identity matches at
**0.70**, and passive liveness at **0.85** on the first and last captured frames.
Those two frames also require MiniFASNet PAD at **0.75** in **enforce** mode.
Intermediate frames are not PAD-tested. Depth and mesh are weighted cues without
separate cutoffs. This guide uses the existing [video instrumentation](diagnostic-instrumentation.md)
and follows the [image replay guide](../image-replay/photo-replay-pad-test-guide.md).

## 1. Build and check the services

Have the normal stack running with the root `.env` configured. Then:

```sh
docker compose build face-recognition backend
export PAD_MODE=enforce
export PAD_THRESHOLD=0.75
CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
  docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend

curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8000/health
```

Check actual model loading/inference; health alone does not establish PAD readiness:

```sh
docker compose exec -T face-recognition python - <<'PY'
import math
import numpy as np
from app.config import settings
from app.pad import initialize_pad, evaluate_pad
from app.motion import _create_landmarker
assert (settings.pad_mode, settings.pad_threshold) == ('enforce', 0.75)
assert (settings.liveness_threshold, settings.face_match_threshold) == (0.85, 0.70)
initialize_pad()
result = evaluate_pad(np.zeros((160, 200, 3), np.uint8), (50, 40, 60, 80))
assert math.isfinite(result.live_score)
_, tracker = _create_landmarker()
with tracker:
    pass
print(settings.pad_mode, settings.pad_threshold, result.model_version)
print('PAD inference and motion model loading succeeded')
PY
```

Expect `enforce 0.75 minifasnet-v2-v1se-onnx-v1`. This synthetic smoke check does
not submit attendance or measure replay resistance; the image need not pass PAD.

## 2. Automatically create the session pair

In the same terminal:

```sh
export VIDEO_TRIAL="$(date -u +%Y%m%dT%H%M%SZ)"
export VIDEO_RUN_CONFIG="new-tests/video-pad-${VIDEO_TRIAL}.json"
export VIDEO_RUN_REPORT="new-documentations/video-replay/video-pad-${VIDEO_TRIAL}.md"

python3 new-tests/prepare_video_replay.py --config "$VIDEO_RUN_CONFIG"
```

Enter the instructor/admin email and password, then choose the test course.
The helper creates two new sessions, `real_face_control` and `phone_video`, with
`require_motion_check`, `require_liveness_check`, and `require_face_match` all
**true**, and writes their UUIDs into the monitor config. They start in about one
minute and last 60 minutes, inheriting the course's venue/geofence/risk defaults.
These are real sessions; later submissions create real attendance records.

Continue only after setup succeeds and prints both session IDs. On partial failure,
inspect the preserved config and sessions; do not use that incomplete trial or
overwrite it. Choose a fresh filename for another pair. Wait for activation and
refresh the student's session list. Keep this terminal open for the exported paths.

## 3. Enable scoped diagnostics and start collection

Both services need the same exact two-session allowlist:

```sh
export CHECKIN_DIAGNOSTICS_ENABLED=true
export CHECKIN_DIAGNOSTIC_SESSION_IDS="$(python3 -c \
  'import json,sys; c=json.load(open(sys.argv[1])); assert c["setup_complete"] and len(c["sessions"]) == 2; print(",".join(s["id"] for s in c["sessions"]))' \
  "$VIDEO_RUN_CONFIG")"

docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend

docker compose exec -T backend python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
docker compose exec -T face-recognition python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'

python3 new-tests/monitor_phone_replay.py --mode video \
  --config "$VIDEO_RUN_CONFIG" --report "$VIDEO_RUN_REPORT" --minutes 45
```

Confirm both flags are `true` and both allowlists contain the config's two UUIDs.
Wait for `MONITOR_READY` with no log-stream error before issuing either challenge.
Leave collection running in the foreground. It reads local `saiv-backend` logs and
writes only scoped scalar observations. Do not restart services during collection.

## 4. Perform the two presentations

Open the normal student application at `http://localhost:3000` on the local
computer, or its usual HTTPS URL on a phone. Use the real application, not demo
mode. Confirm both sessions are active and their check-in windows are open.

1. In `real_face_control`, start the camera and share a fresh precise location.
   Keep the student's actual face centred, with eyes initially open. Click
   **Start challenge**, blink naturally twice, and finish with eyes open.
2. Click **Verify this sequence**. If it passes, click **Submit check-in** and
   record the saved outcome. A verified sequence alone does not save attendance.
3. In `phone_video`, play the enrolled student's clip on the second phone into
   the same capture camera. Begin with eyes open at normal playback speed,
   allowing time to click **Start challenge** before the two blinks. Keep the
   student's actual face and all other faces outside the camera view.
4. Click **Verify this sequence**. If accepted, finish with **Submit check-in**.
   A server-rejected sequence needs no attendance submission to record rejection.

Capture lasts 1–8 seconds, with 15–120 frames. A challenge permits one verification
upload and expires within three minutes or at session close. After failure,
expiry, or timeout, start a new challenge; submit promptly after success.

Record actual presentations, retries/UI errors, capture/display devices, browser,
clip duration/frame rate/resolution, playback speed, brightness, lighting, distance,
and visible borders/reflections. Keep the clip on the display phone, outside Git
and diagnostic exports. Add notes outside the report's diagnostic markers.

## 5. Read the report

Open the report printed/selected earlier, or use a second terminal:

```sh
cat new-documentations/video-replay/video-pad-YOUR_TIMESTAMP.md
```

Each challenge has a first/last-frame table, sequence stop reason, and allowlisted
JSON. Video mode normally prints `OBSERVED` events, without the photo mode's
standalone `PAD` console line. In `motion_sequence.values.diagnostics`, inspect:

| Measurement | Fields |
| --- | --- |
| Sequence / identity | `reason`, `frame_count`, `processed_frames`, `duration_ms`, `identity_checks`, `face_match_threshold`; sequence `face_match_score` is the minimum sampled identity score |
| Endpoint liveness | `first_frame` / `last_frame`: `evaluated`, `liveness_score`, `liveness_threshold`, `liveness_passed` |
| Endpoint PAD | Each frame's `details`: `pad_mode`, `pad_status`, `pad_evaluated`, `pad_live_score`, `pad_threshold`, `pad_passed` |
| Model comparison | `pad_v2_live_score`, `pad_v1se_live_score`, `pad_model_version`, `pad_inference_ms`; the ensemble live score is the two-model mean |
| Before / after PAD | `pre_pad_liveness_score`, `pre_pad_liveness_passed`, `pad_would_veto`; an enforced PAD failure returns liveness 0.0 / failed |

Both evaluated endpoint frames must pass PAD and overall liveness. Processing
stops at the first failure, so the last frame can be **not evaluated** and server
blink count can remain zero. Missing/`null`/`unknown` values are not measured zeros.
The legacy **Depth / mesh gates** column normally shows **not used**.

| Outcome | Interpretation |
| --- | --- |
| Server `motion_verified.passed=false`, PAD evaluated and failed | Measured PAD-associated motion rejection |
| Server rejected at another stage | Use the stop reason; do not attribute rejection to PAD without its measured failure |
| Server passed, no `attendance_committed` | Biometric acceptance; saved attendance unconfirmed |
| Server passed, attendance flagged | Biometric acceptance plus an attendance flag; inspect saved risk factors |
| Confirmed video, server passed, saved attendance approved | Observed end-to-end replay acceptance |
| Browser failure, expired request, or unavailable verification | Inconclusive for server replay detection |

Confirm saved ownership/status in the dashboard or authenticated check-in detail.
A device/geofence flag does not demonstrate replay detection. Investigate a failed
genuine control before interpreting the pair. One trial does not establish an
attack-success rate; a fixed two-blink action does not establish recording freshness.

## 6. Stop and clean up

Video mode exits when both sessions' latest challenges reach terminal outcomes:
server rejection, server acceptance followed by attendance commitment, or a scoped
request failure (inconclusive). Timeout or Ctrl-C also ends collection. A browser-only
failure or passed proof without submission can remain pending. Retries get separate
challenge groups; a new challenge supersedes an older one for automatic completion.

The monitor attempts to disable diagnostics in **both services** on exit. Expect
`MONITOR_FINISHED` with `diagnostics disabled`. For manual cleanup, a reported
shutdown failure, or to clear the parent shell's exported diagnostic variables:

```sh
CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
  docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend
unset CHECKIN_DIAGNOSTICS_ENABLED CHECKIN_DIAGNOSTIC_SESSION_IDS

docker compose exec -T backend python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
docker compose exec -T face-recognition python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8000/health
```

Expect `false` and `''` in both services. Cleanup briefly restarts services and
leaves PAD enforcement active. A hard kill, Docker failure, or invalid startup
config can prevent automatic cleanup. Preserve attendance, audit records, config,
and report; create a fresh session pair for repetitions.

## Troubleshooting

- **Photo screen:** verify `require_motion_check=true` and refresh. One-time face
  enrollment is a separate photo step; do not use `prepare_photo_replay.py` here.
- **No events/PAD unknown:** check both service flags/allowlists, config timestamp,
  session UUIDs, `MONITOR_READY`, and `saiv-backend` log access. Rebuild both services
  if deployed code predates PAD diagnostics.
- **No server verdict:** browser cancellation/tracking errors, pre-route 413/422,
  and authentication failures may produce no scoped sequence result. Record the UI
  response rather than treating absent observations as attack detection.
- **PAD unavailable / HTTP 503:** rerun the model check; this is an availability
  result, not measured spoof rejection. Do not lower thresholds for the trial.
- **Already checked in:** use fresh sessions. For an expired/used proof without
  saved attendance, start a new challenge.

Older instrumentation text describes depth/mesh gates; the
[current PAD adjustment](../image-replay/pad-enforcement-adjustment-20261102.md)
records their removal. No API/schema or `docs/` changes are needed for this guide.

## About `prepare_video_replay.py`

[`prepare_video_replay.py`](../../new-tests/prepare_video_replay.py) uses standard-library
HTTP requests to log in, list the first 100 accessible courses, and create the two
motion sessions through existing APIs. Use `--course-id UUID` to skip course
selection, `--api-url http://HOST:8000` for another backend origin, or
`--minutes 30` to change duration (5–240 minutes; default 60).

It validates the returned verification flags, saves each created UUID immediately,
and sets `setup_complete=true` only when both sessions are ready. It refuses to
overwrite configs and retains partial results after failure. Credentials remain
in memory. It does not enroll students, change existing sessions, enable PAD or
diagnostics, or submit attendance; `pad_mode` in the config records the intended
trial mode, while Step 1 configures and checks the actual service.
