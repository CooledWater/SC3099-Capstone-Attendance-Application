# Liveness and PAD adjustment

Implemented 2 November 2026 at the user's request. This supersedes the separate geometry gates in `threshold-implementation.md` and the shadow-only behavior in `pad-shadow-integration-summary.md`.

## Decision

- Overall liveness threshold stays **0.85**.
- Depth and mesh retain their **30% / 25%** component weights. Their independent 0.80 cutoffs, runtime settings, and emitted gate flags were removed. Texture/color weights and the existing integrity factors are unchanged.
- PAD defaults to **`enforce`**, with a **0.75** cutoff in both direct Python startup and Docker Compose. An explicit server-side `off` or `shadow` override remains available; requests cannot choose the mode or cutoff.
- A measured PAD failure returns `liveness_passed=false` and final `liveness_score=0.0`. The pre-PAD score and model results remain in diagnostics. The existing backend liveness-failure rule rejects photo check-ins; the sequence verifier stops on a failed passive frame and issues no successful motion proof.

```text
weighted = 0.30*depth + 0.25*mesh + 0.25*texture + 0.20*color
pre_pad = round(weighted * presentation_integrity * challenge_integrity, 6)
pad_live = (V2_live + V1SE_live) / 2

in enforce mode:
    liveness_score = pre_pad if pad_live >= 0.75 else 0.0
    liveness_passed = (pre_pad >= 0.85) AND (pad_live >= 0.75)
```

Missing faces, multiple faces, and missing landmarks still fail. A zero liveness-cutoff override cannot bypass PAD rejection. PAD model/inference errors return a service-unavailable response rather than a fabricated live/spoof verdict. Existing backend strict/non-strict service-outage handling is unchanged.

## Original API conformity

**Removing geometry gates conforms to the original weighted-component design** in `docs/API-SPECIFICATION.md` (liveness section): it specifies depth 30%, mesh 25%, texture 25%, color 20%, without separate depth/mesh minimums. It does not restore the original overall cutoff: the original API/security examples use 0.60, while the user explicitly retains the previously approved **0.85**.

PAD enforcement is the additional decision rule authorized in this request; the original spec does not describe it. Response top-level fields and the backend's documented “liveness failed → rejected” rule are reused. No database/schema or endpoint changes were needed. `docs/` remains untouched.

## Files and integration

- Module 3: `app/config.py`, `liveness.py`, `main.py`, `motion.py`, `motion_diagnostics.py` remove geometry gates, enable the PAD veto, and preserve scalar diagnostics.
- Module 2: `app/checkin_diagnostics.py` accepts the `enforce` diagnostic mode; existing rejection logic is reused.
- `docker-compose.yml` defaults to `PAD_MODE=enforce` and `PAD_THRESHOLD=0.75`.
- Replay helper/monitor and the [photo test guide](photo-replay-pad-test-guide.md) now describe enforcement and still interpret historical shadow/gated logs. Existing trial logs were preserved.
- Added `new-tests/test_pad_enforcement.py`. Updated `test_liveness_thresholds.py`, `test_pad_module3.py`, `test_checkin_diagnostics.py`, `test_pad_backend_diagnostics.py`, `test_video_replay_sequence_diagnostics.py`, `test_pad_replay_monitor.py`, and `test_prepare_photo_replay.py` in `new-tests/`.
- Modules 1 and 4 were reviewed; their existing response/status handling needs no change.

Endpoints reused: Module 3 `POST /liveness/check` and `POST /liveness/sequence`; Module 2 `POST /api/v1/checkins/` and `POST /api/v1/motion/challenges/{challenge_id}/verify`. Existing identity and risk endpoints remain unchanged.

## Verification

- **157 passed**: native face/PAD/motion suites, including original-model reference vectors, photo/sequence enforcement, 0.75 boundaries, service errors, and replay of all ten recorded capture scalars.
- **15 passed**: `tests/public/test_face_recognition.py` against disposable audit services.
- **33 passed**: backend PAD/check-in/motion diagnostics, including saved PAD rejection despite low risk.
- **28 passed**: report, monitor, and setup helper suites.
- Recorded-scalar outcome under the implemented calculation: **5/5 genuine passes; 0/5 screen-photo passes**. This replays scoring, not the original images; fresh physical trials remain necessary.
- `git diff --check` passed. Native/API checks used a separate Docker Compose project, temporary PostgreSQL storage, and no published ports. Local backend checks used temporary SQLite databases.
- Verified the isolated runtime defaults: `enforce / 0.75`, overall cutoff `0.85`, and no geometry-cutoff settings. Removed the disposable audit containers and network after testing.

## Activation and limits

Rebuild/recreate the normal backend and face-recognition services to activate the source changes. Explicitly use `PAD_MODE=enforce PAD_THRESHOLD=0.75` if earlier shell/deployment overrides selected shadow mode or 0.50; removed depth/mesh environment settings have no effect. The [updated guide](photo-replay-pad-test-guide.md) contains the commands. The user's normal running services were not restarted by this adjustment.

Sequence PAD still evaluates the first/last passive frames, and device/location/identity requirements still apply. Use newly issued motion challenges after deployment; a previously verified, unexpired motion proof retains its stored result.
