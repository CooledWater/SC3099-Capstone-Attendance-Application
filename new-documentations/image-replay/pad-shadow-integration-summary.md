# MiniFASNet shadow integration

Implemented on 1 November 2026. As requested, PAD only observes captures:
**attendance decisions and existing security policies are unchanged**.

Module 3 now runs the MiniFASNet V2 + V1SE ensemble using existing OpenCV CPU
support. The bundled graphs are hash-checked, warmed at startup and reused behind
a lock. Preprocessing preserves the original context crops, BGR channel order,
0–255 input scale and live-class index. Request inputs and network activations are
overwritten with neutral inputs before model reuse; no participant captures are
saved. No runtime model downloads or new runtime dependencies are needed.

The photo-replay report now shows the ensemble and individual model scores,
exploratory cutoff, pass/fail, processing time, model version, legacy liveness and
whether PAD would have vetoed a legacy pass. Skipped/unavailable checks have
explicit states and null measurements. Both diagnostic allowlists preserve these
bounded scalars. Existing motion sequences receive the same observation on their
first and last passive checks. Metrics expose aggregate PAD outcomes and latency.

Start a trial using [the photo-replay test guide](photo-replay-pad-test-guide.md).
It includes build/start commands, an interactive helper for two fresh test
sessions, diagnostic setup, report locations, interpretation and cleanup.
Running services were not rebuilt, restarted or reconfigured during implementation.

## Files changed

- `module3-face-recognition/app/pad.py`, `app/assets/pad/`: adapter, two graphs,
  manifest, provenance and license notices.
- Module 3 `app/config.py`, `app/liveness.py`, `app/main.py`, `app/metrics.py`,
  `app/motion_diagnostics.py`: settings, shared shadow observation, startup and metrics.
- `module2-backend/app/checkin_diagnostics.py`: PAD diagnostic projection only.
- `docker-compose.yml`: default `PAD_MODE=shadow`, `PAD_THRESHOLD=0.50` for Compose.
  Direct Python service startup defaults to `off`; supported modes are only `off`/`shadow`.
- `new-tests/monitor_phone_replay.py`, `prepare_photo_replay.py`: PAD report and
  self-service photo-session setup.
- `new-tests/test_pad_module3.py`, `test_pad_backend_diagnostics.py`,
  `test_pad_replay_monitor.py`, `test_prepare_photo_replay.py`,
  `check_pad_reference_parity.py`, `pad-reference-vectors.json`: checks and
  synthetic reference outputs. PyTorch/ONNX were temporary verification tools.
- This summary and `photo-replay-pad-test-guide.md`. `docs/` and prior trial records
  were verified unchanged. Modules 1 and 4 required no changes.

## Endpoints reused

No endpoint or database table was added. Processing reuses `POST /liveness/check`,
`POST /liveness/sequence`, `GET /health` and `GET /metrics`; existing
`POST /face/verify` and `POST /risk/assess` keep their roles. The test workflow reuses
backend `POST /api/v1/auth/login`, `GET /api/v1/courses/`,
`POST /api/v1/sessions/` and `POST /api/v1/checkins/`.

## Checks and remaining gaps

- **156 face/PAD/motion/replay checks passed**, including native graphs, real photo
  HTTP shadow/off comparison, corruption/errors, concurrency and diagnostic privacy.
- **8 backend/setup checks passed**; **12 existing video-backend checks passed**
  in a separate process. These use isolated temporary databases and mocked biometric
  transport; no live attendance was created.
- **15 unchanged public HTTP face tests passed** against a disposable service with
  shadow mode enabled. Relevant suites emitted only dependency deprecation warnings.
- **8 original-PyTorch versus bundled ONNX/OpenCV comparisons passed**, including
  original crop parity at image borders; maximum logit difference **0.00000405**.
  See [reference vectors](../../new-tests/pad-reference-vectors.json) and
  [upstream provenance](../../module3-face-recognition/app/assets/pad/NOTICE.md).
- A 60-run synthetic CPU adapter probe measured **6.299 ms median / 6.467 ms p95**,
  including crop/inference/input clearing. This excludes decoding, face detection,
  HTTP, loading, queueing and concurrent load; it is not a production latency result.
- Compose configuration, Python compilation, guide shell syntax/local links,
  whitespace and preservation checks passed.
- **Four existing photo-diagnostics assertions still fail**, identically with the
  original pre-change diagnostic module: they expect approval/old risk values,
  while the current unknown-device policy flags attendance and adjusts risk.
  Ten other tests in that older suite pass. Production device policy and those
  unrelated assertions were not changed.

The **0.50 PAD cutoff remains uncalibrated**; fresh genuine/photo/video trials are
needed before claims about local attack detection or genuine-user tolerance.
Only first/last sequence frames receive PAD, not intermediate frames. Health can
remain healthy with unavailable shadow PAD; use the guide's model smoke check.
Enforcement, outage-policy changes, randomized challenges and enrollment PAD were
not implemented. The earlier approved legacy 0.85/0.80/0.80 policy still differs
from older 0.60 examples in `docs/`; shadow observations introduce no new decision
exception and no documentation changes were required.
