# Run a photo-replay test with MiniFASNet diagnostics

Run these commands from the repository root in macOS Terminal (zsh or bash).
You need Docker Compose, Python 3, an instructor/admin login, an enrolled test
student, and a second phone displaying that student's photograph. The setup helper
uses Python's standard library; no local pip installation is needed.

PAD runs in **shadow mode**: it measures the capture, but its result does not change
attendance. The existing liveness, identity, device and location rules still apply.
The default PAD cutoff, **0.50**, is exploratory and has not been calibrated for
these cameras. A low live-class score suggests a presentation attack; it is not a
probability or a guarantee. Enforcement is not implemented.

## 1. Build and start the updated services

Have the normal application stack running, with its usual root `.env` configured.
Rebuild both services because the backend diagnostic allowlist also changed:

```sh
docker compose build face-recognition backend

export PAD_MODE=shadow
export PAD_THRESHOLD=0.50
CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
  docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend

curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8000/health
```

Check that the bundled models actually load and run. This uses synthetic pixels,
not a participant photo, and does not submit attendance:

```sh
docker compose exec -T face-recognition python - <<'PY'
import numpy as np
from app.config import settings
from app.pad import initialize_pad, evaluate_pad
assert settings.pad_mode == 'shadow', settings.pad_mode
initialize_pad()
result = evaluate_pad(np.zeros((160, 200, 3), np.uint8), (50, 40, 60, 80))
print('Mode:', settings.pad_mode)
print('Model:', result.model_version)
print('Synthetic smoke-test live score:', result.live_score)
PY
```

Expect `shadow`, `minifasnet-v2-v1se-onnx-v1`, and a finite score. This only checks
that inference works. `/health` checks service health and can remain healthy when
shadow PAD is unavailable; the smoke check is the model check.

## 2. Create a fresh pair of photo sessions

Use a course where your test student is already actively enrolled. The student
needs face enrollment and camera/location consent. Use an approved, registered
browser device and stand inside the course geofence if you want to avoid unrelated
device/location flags. Use a test course with the intended venue coordinates.

```sh
export PAD_TRIAL="$(date -u +%Y%m%dT%H%M%SZ)"
export PAD_RUN_CONFIG="new-tests/photo-pad-${PAD_TRIAL}.json"
export PAD_RUN_REPORT="new-documentations/image-replay/photo-pad-${PAD_TRIAL}.md"

python3 new-tests/prepare_photo_replay.py --config "$PAD_RUN_CONFIG"
```

Enter the instructor/admin email and password, then choose the course. Credentials
are not saved. The helper lists the first 100 accessible courses; alternatively,
pass `--course-id YOUR_COURSE_UUID`. Use `--api-url` if the backend is elsewhere.

It creates two **new** sessions: `real_face_control` and `phone_screen`. Both require
liveness and identity, explicitly disable motion for this photo experiment, start
in about one minute, and last 60 minutes. Course venue/risk defaults are inherited.
These are real test sessions, and later submissions create real attendance records.
The helper does not change existing sessions or enroll anyone.

The dashboard's usual liveness option also enables motion. Use these helper-created
sessions to reach the single-photo path. Do not disable motion on ordinary classes.
If setup fails partway, its config preserves successful session creations; inspect
those sessions and use a fresh filename for another trial.

## 3. Enable diagnostics only for these two sessions

In the same terminal:

```sh
export CHECKIN_DIAGNOSTICS_ENABLED=true
export CHECKIN_DIAGNOSTIC_SESSION_IDS="$(python3 -c \
  'import json,sys; print(",".join(s["id"] for s in json.load(open(sys.argv[1]))["sessions"]))' \
  "$PAD_RUN_CONFIG")"

docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps backend

python3 new-tests/monitor_phone_replay.py \
  --config "$PAD_RUN_CONFIG" --report "$PAD_RUN_REPORT" --mode image --minutes 45
```

Wait for `MONITOR_READY` before submitting captures. The monitor runs in the
foreground; leave that terminal open. It reads existing scoped backend events
since the config's UTC `monitor_since` timestamp. It does not save raw Docker logs.
Each run should use fresh sessions, a fresh config, and a fresh report.

## 4. Submit the genuine face and the displayed photo

On the capture device, open the normal student application in a camera-enabled
browser, sign in as the enrolled student, and refresh sessions after activation.

1. In `real_face_control`, capture the student's actual face and finish check-in.
2. In `phone_screen`, hold the second phone's displayed photograph in front of the
   capture camera, capture it, and finish check-in. Keep the student's real face
   and other faces out of the camera view.
3. Record the actual presentation, camera/display models, brightness, lighting,
   distance, approximate face size, screen borders/reflections and any UI errors.

Keep the photograph on the display device. Do not add participant images to Git,
reports or diagnostic exports. The session label is an operator assignment; it
does not independently prove what the camera saw.

## 5. Read the diagnostic output

The monitor prints an `OBSERVED` line per scoped event and a short `PAD` line for
each photo liveness response. Its Markdown report updates after each event. Open
it in your editor, or in a second terminal from the repository root:

```sh
# Use the report path printed/selected in the first terminal:
cat new-documentations/image-replay/photo-pad-YOUR_TIMESTAMP.md
```

Each attempt includes readable tables for the original liveness and identity
checks, PAD, and the attendance decision, followed by the complete allowlisted
scalar JSON. These tables update automatically with the same monitor command;
the report formatting runs locally, so it does not require a service rebuild.

The original-check tables show:

| Measurement | What to look for |
| --- | --- |
| Identity score, threshold and passed | The separate `/face/verify` comparison against the enrolled face |
| Returned liveness score, threshold and passed | The existing `/liveness/check` verdict used by attendance |
| Depth / mesh scores, gate thresholds and passed | Both geometry gates must pass, even if the combined score is high |
| Texture / color scores | Original weighted components; these have no separate pass/fail cutoff |
| Component weights and weighted contributions | The recorded contributions to `weighted_component_score` |
| `pre_gate_liveness_score` | Score before depth/mesh gates; a failed gate can turn a high pre-gate score into returned liveness `0.0` |
| Mesh completeness, landmark count, depth quality and depth statistics | Aggregate geometry diagnostics; raw landmarks are excluded |
| Presentation integrity, texture signals and color signals | Existing periodicity, sharpness, diversity and color measurements |
| Calculated status, reason, risk and saved attendance status | Distinguishes the decision from a confirmed database commit |

Identity is not a liveness component. An identity match can pass for a displayed
photograph, and a PAD pass cannot override a failed legacy geometry gate in shadow
mode. Original measurements remain visible when PAD is off, unavailable or not
evaluated. `unknown` in these tables means a value was absent or null in the
diagnostics; it does not mean a measured zero or a failed check. Before a commit
event arrives, saved attendance status remains `unknown`.

The PAD table shows:

| Field | What to look for |
| --- | --- |
| `pad_mode` / `pad_status` / `pad_evaluated` | Expect `shadow` / `evaluated` / `true` for a measured result |
| `pad_model_version` | Identifies the pinned model pair and preprocessing recipe |
| `pad_live_score` | Mean live-class score from both models; compare genuine versus photo |
| `pad_v2_live_score`, `pad_v1se_live_score` | Shows whether the two models disagree |
| `pad_threshold`, `pad_passed` | Comparison against the exploratory cutoff, separate from legacy liveness |
| `pad_inference_ms` | Crop, inference and neutral-input cleanup time; excludes model loading and lock wait |
| `pre_pad_liveness_score`, `pre_pad_liveness_passed` | Existing geometry-gated liveness result |
| `pad_would_veto` | `true` means legacy liveness passed while PAD failed; observation only |
| `decision`, `attendance_committed` stages | Calculated decision versus actual saved status |

`off`, `not_evaluated`, or `unavailable` is not a measured PAD rejection. Missing
scores/verdicts are `null`, not measured zeros. A no-face/multiple-face/mesh failure
can stop before PAD. A measured score of `0.0` with `pad_evaluated=true` is different.

In shadow mode, a phone photo may have `pad_passed=false` and still receive approved
attendance if the existing rules pass. A flagged attendance caused by device or
geofence rules does not establish PAD rejection. Confirm what was physically
presented and check the saved record in the dashboard.

Aggregate counters and latency are also available through the existing metrics
endpoint and Prometheus at `http://localhost:9090`:

```sh
curl -fsS http://localhost:8001/metrics | rg '^pad_'
```

Look for `pad_outcomes_total` (`passed`, `failed`, `unavailable`) and
`pad_duration_seconds` (includes lock wait/loading as well as processing). These
are process-wide, reset on restart and include synthetic smoke tests; they do not
replace the scoped report. The dashboard does not have a new per-attempt PAD panel.

## 6. Stop and clean up diagnostics

The monitor exits after both sessions commit attendance, on timeout, or on Ctrl-C.
Image mode attempts to recreate the backend with diagnostics disabled. It prints
whether shutdown succeeded and preserves your report. This restart can briefly
interrupt requests. A hard kill, Docker failure, or invalid config can prevent cleanup.

For manual cleanup, or after a reported shutdown failure:

```sh
CHECKIN_DIAGNOSTICS_ENABLED=false CHECKIN_DIAGNOSTIC_SESSION_IDS='' \
  docker compose -f docker-compose.yml -f new-tests/docker-compose.phone-replay.yml \
  up -d --no-deps face-recognition backend
unset CHECKIN_DIAGNOSTICS_ENABLED CHECKIN_DIAGNOSTIC_SESSION_IDS

# Confirm both services have disabled diagnostics and empty session allowlists:
docker compose exec -T backend python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
docker compose exec -T face-recognition python -c \
  'import os; print(os.getenv("CHECKIN_DIAGNOSTICS_ENABLED"), repr(os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS")))'
```

Expected flags are `false` and `''`. Preserve test attendance and notes. For more
repetitions, create another session pair. To stop PAD processing as well, run
`PAD_MODE=off docker compose up -d --no-deps face-recognition`; disabling diagnostic
logging alone leaves shadow inference active.

## Troubleshooting and limits

- **No records:** check session UUIDs, diagnostic flags, `MONITOR_READY`, active
  enrollment, open session windows and that final check-in was submitted. A browser
  error before submission is not a server PAD result.
- **PAD unknown:** rebuild/recreate both backend and face service; old backend
  images discard unfamiliar diagnostic fields.
- **PAD unavailable:** rerun the model smoke check. Check asset packaging and hashes;
  the runtime does not download replacement weights. The existing non-strict
  face-service outage policy is unchanged.
- **Blink screen instead of photo capture:** check that the session really has
  `require_motion_check=false` and refresh the browser.
- **One student cannot resubmit:** duplicate check-ins are blocked. Create fresh
  sessions rather than deleting attendance records.

The shared PAD integration also observes the existing first and last passive checks
in motion sequences; intermediate frames are not PAD-tested. This guide is for
photo mode. For video trials, use [the video diagnostic guide](../video-replay/diagnostic-instrumentation.md).
Fresh physical trials are still needed to choose a cutoff and measure attack
acceptance and genuine-user rejection. Historical scalar-only reports cannot be
reprocessed through this model.
