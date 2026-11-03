# Random blink and head-turn liveness

Implemented 2026-11-03 following approval of the randomized-motion plan and its API/schema exceptions. This is the current motion-required attendance flow. The original fixed two-blink flow is historical.

## Student flow

For each attempt, Module 2 independently selects the blink target (one or two), turn direction (the student's left or right), and first action (blink or head turn), using `secrets.choice`. Both actions are required. There are eight requirement combinations; consecutive attempts may legitimately select the same one.

The browser first asks for a forward-facing, open-eyed baseline, then presents one action at a time with direction arrows, progress, and an eight-second countdown. A turn must finish with the face centred. The browser captures the same unmirrored canvas frames that it analyses. The existing video preview is mirrored by CSS only. Demo capture uses the same temporal rules and is not a server verification.

Capture, retry, interruption, and submission keep frames in component memory only. Cancellation, camera interruption, completion/submission, session changes, and unmount release the attempt. No frames are added to browser storage, application tables, or diagnostic logs.

## API contracts

The routes are reused; no new routes are introduced.

`POST /api/v1/motion/challenges` still accepts only `{ "session_id": "..." }`. Unknown fields are rejected so callers cannot choose an easier challenge. Its `201` response now looks like:

```json
{
  "challenge_id": "<UUID>",
  "action": "random_motion",
  "challenge": {
    "version": 2,
    "blink_target": 2,
    "turn_direction": "left",
    "first_action": "blink"
  },
  "expires_at": "<ISO 8601 UTC>",
  "max_duration_ms": 8000,
  "max_frames": 120
}
```

The second action is the other action type. Requirements are stored atomically with the parent challenge. Issuance holds the existing per-user PostgreSQL row lock, invalidates earlier attempts for the same student/session, and prunes expired metadata. The response is assembled before releasing the lock so a concurrent retry cannot cause a lazy-load failure after deleting an earlier challenge.

`POST /api/v1/motion/challenges/{id}/verify` still accepts only `{ "frames": [{ "image": "<base64>", "timestamp_ms": 0 }] }`. Extra fields, including client-supplied requirements, are rejected. Module 2 reads the issued requirements from its database and forwards them to internal `POST /liveness/sequence` as `challenge`, alongside the frames and enrolled `reference_template_hash`.

The verification response adds three scalar fields:

```json
{
  "passed": true,
  "blink_count": 2,
  "challenge_version": 2,
  "turn_passed": true,
  "completed_steps": 2,
  "liveness_score": 0.95,
  "face_match_score": 0.98,
  "verification_id": "<challenge UUID>"
}
```

Module 2 validates all persisted fields and requires version 2, sufficient complete blinks, a completed turn, and two completed steps before issuing a proof. A failed sequence returns `passed: false` and `verification_id: null`. Missing/malformed/incomplete service success evidence or a service outage returns `503` and fails the challenge. Expired, reused, replaced, or pre-v2 challenges cannot be verified/consumed and require a fresh attempt.

`POST /api/v1/checkins/` continues to consume `motion_verification_id` atomically with attendance insertion. The resulting attendance `liveness_challenge_type` is `random_motion`. Ownership, session, enrolled reference, consent, expiry, eligibility, and one-time-use checks remain in place. Motion-required sessions cannot fall back to photo evidence.

Internal `/liveness/sequence` retains its original response and two-blink behavior when `challenge` is absent for compatibility with existing internal clients/tests. Module 2 always supplies and requires a stored v2 specification, so that compatibility path cannot issue attendance proofs through the public API. `/liveness/check` and its single-image challenge-type enum are unchanged.

## Temporal verification

The pinned Tasks Face Landmarker now emits its optional facial transformation matrices. The Python adapter returns a two-dimensional matrix; the Web adapter exposes the column-major packed pose data. The respective yaw conversions use the same rotation elements. See the upstream [Web adapter](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/web/vision/face_landmarker/face_landmarker.ts) and [Python adapter](https://github.com/google-ai-edge/mediapipe/blob/v0.10.18/mediapipe/tasks/python/vision/face_landmarker.py). No model or package upgrades were made.

| Rule | Version 2 behavior |
| --- | --- |
| Baseline | Open eyes and yaw within 8 degrees of forward for at least 200 ms; average those baseline yaw observations |
| Blink | Complete open–closed–open cycles; EAR closed below 0.19, open at/above 0.23; observed closure 40–700 ms |
| Blink counting | Only during the issued blink step while within 8 degrees of the baseline |
| Turn | At least 20 degrees from baseline in the requested direction for at least 200 ms |
| Return | Within 8 degrees of baseline with eyes open for at least 200 ms |
| Direction/order | A 20-degree opposite turn fails; a turn during the blink step fails |
| Other blinks | Natural blinks outside the blink step do not count toward its target |
| Final frame | Both actions completed, face centred, eyes open |

Python and TypeScript implement the same policy and use shared regression vectors. Missing, malformed, or non-finite pose output cannot produce successful verification. These angles and holds are provisional usability thresholds, not a camera-accuracy certification.

Identity matching still runs every eighth frame, at completed blinks, and in the final frame; it also runs when an action completes. One-face tracking and abrupt-face-jump rejection remain. Passive liveness and the configured PAD policy still run on the first and final frames, and either failure prevents a proof. Existing face-match, passive-liveness, and risk thresholds were not changed.

Capture remains bounded to 15–120 frames, 1–8 seconds, first frame within 250 ms, strictly increasing timestamps with gaps at most 250 ms, 100,000 base64 characters per frame, and 6,000,000 total. The 6,200,000-byte upload limit, 40-second processing budget, 45-second internal timeout, 55-second browser timeout, and expiry of at most three minutes/the attendance window remain.

Opt-in diagnostics add `challenge_version`, `completed_steps`, `turn_passed`, and the fixed reasons `baseline_missing`, `step_order`, `wrong_direction`, `insufficient_turn`, and `neutral_not_restored`. They retain scalar allowlisting and never emit matrices, landmarks, templates, or images.

## Storage and rollout

The additive `motion_challenge_specs` table contains:

| Column | Type and constraint |
| --- | --- |
| `challenge_id` | VARCHAR(36), primary key, cascading FK to `motion_challenges.id` |
| `version` | INTEGER NOT NULL, must equal 2 |
| `blink_target` | INTEGER NOT NULL, 1 or 2 |
| `turn_direction` | VARCHAR(5) NOT NULL, `left` or `right` |
| `first_action` | VARCHAR(9) NOT NULL, `blink` or `head_turn` |

The existing startup `Base.metadata.create_all()` creates it in new and existing databases. Existing table columns do not change. `motion_challenges.result` continues to hold scalar verification outcomes only. Explicit child cleanup also supports SQLite configurations without FK enforcement, including retry/expiry cleanup, session deletion, and scheduled account deletion.

Deploy Module 3, Module 2, and then the frontend/dashboard as a coordinated release. Old pending challenges/proofs have no v2 metadata and must be restarted. Refresh cached PWA clients; the new browser rejects an old challenge response with a reload message. This implementation was verified using test copies and a disposable build container; it has not been deployed to the running applications.

The approved exceptions extend the fixed `blink_twice` contract referenced by `docs/API-SPECIFICATION.md`, add metadata beyond `docs/DATABASE-SCHEMA.md`, and add `random_motion` to attendance challenge-type values. Files inside `docs/` were not modified.

## Verification results

All test databases were disposable. The public suite used a temporary backend and a temporary process serving the changed Module 3 source. The native tests used the pinned MediaPipe/dlib models; backend contract tests mock only the Module 3 transport.

| Check | Result |
| --- | --- |
| Entire `tests/public` suite | 102 passed, 1 skipped |
| Motion/pose/native/liveness/sequence-diagnostic Python regressions | 153 passed |
| New backend cases against PostgreSQL | 28 passed, including issuance/verification/retry concurrency |
| SQLite backend wrapper and existing motion contracts, excluding known baseline query-budget assertions | 30 outer tests passed, 5 deselected; wrapper includes the new cases, with PostgreSQL-only issuance locking skipped on SQLite |
| Session-deletion and diagnostic regressions | 31 passed |
| Scheduled account-deletion/device-rotation regressions | 5 passed |
| Browser policy, capture hook, and session-policy component regressions | 45 passed |
| Frontend TypeScript and production build | Passed; existing `PullToRefresh.tsx` hook-dependency warning |
| Dashboard production build and edited-file ESLint | Passed; existing large-bundle warning |
| `git diff --check`; `git diff -- docs` | Clean; no changes under `docs/` |

The complete backend motion run also encounters five existing failures: `test_checkin_query_budget_with_real_auth`, the three parameterized `test_session_list_constant_query_count` cases, and `test_read_mode_is_scoped_and_write_rollback_still_works`. All five reproduce against a separate unchanged HEAD checkout. Their query-budget expectations and unrelated production behavior were not changed.

The first public-suite attempt omitted `sample_images` from its temporary workspace and failed face enrollment; copying the existing fixtures and rerunning the complete suite produced the result above. A repeated Next build exposed a symlinked-dependency isolation issue; the runtime dependencies were restored from the original image, and the final build used a separate disposable container without shared dependency symlinks. Restored frontend dependency checks passed, frontend/manifest/dashboard HTTP checks returned 200, and no deleted original frontend application entries remained.

Representative commands, run from the repository root in environments with the respective module dependencies:

```bash
python new-tests/run_session_regressions.py tests/public
python -m pytest -q new-tests/test_random_motion_backend.py
python -m pytest -q new-tests/random_motion_backend_cases.py
python -m pytest -q new-tests/test_random_motion_sequence.py new-tests/test_random_motion_native.py new-tests/test_motion_sequence.py new-tests/test_motion_landmarker.py new-tests/test_motion_native.py new-tests/test_liveness_thresholds.py new-tests/test_video_replay_sequence_diagnostics.py
node --test new-tests/random-motion.test.mjs new-tests/motion-capture.test.mjs new-tests/session-checkin-policy.test.mjs
```

For PostgreSQL concurrency, set `MOTION_TEST_DATABASE_URL` to a disposable PostgreSQL database before running `random_motion_backend_cases.py`. Keep Module 2 and Module 3 test processes separate because both use the Python package name `app`.

Real webcam/mobile trials were not performed. Before requiring this flow broadly, check all eight combinations with diverse users, glasses, front-camera mirroring, slower devices, and limited neck movement. In particular, evaluate the eight-second capture window and identity false rejections during modest turns. The existing instructor-selected photo flow remains available.

Random actions make a fixed clip less reusable, but eight combinations and client-controlled frame timestamps do not establish capture freshness or stop a prepared clip library, adaptive replay, or virtual-camera injection. Identity is sampled across the sequence. Retain passive/PAD checks and avoid claiming production-grade spoof prevention.

## Files changed

- Module 1: `features/camera/motionChallenge.ts` (new), `features/camera/useFaceGuidance.ts`, `components/check-in/FaceVerification.tsx`, `components/check-in/StudentDashboard.tsx`, `lib/api/checkins.ts`, `types/api.ts`.
- Module 2: `app/motion.py`, `app/main.py`, `app/data_deletion.py`, `app/checkin_diagnostics.py`.
- Module 3: `app/random_motion.py` (new), `app/motion.py`, `app/motion_diagnostics.py`.
- Module 4: `src/components/dashboard/SessionsPanel.tsx`.
- New tests: `random-motion-vectors.json`, `random-motion.test.mjs`, `motion-capture.test.mjs`, `random_motion_backend_cases.py`, `test_random_motion_backend.py`, `test_random_motion_sequence.py`, `test_random_motion_native.py` under `new-tests/`.
- Updated tests: `new-tests/backend_motion_cases.py`, `new-tests/session-checkin-policy.test.mjs`, `new-tests/test_session_deletion.py`, `new-tests/test_device_rotation_privacy.py`.
- Documentation: this file and the historical-version notice in `new-documentations/MOTION-VERIFICATION.md`.
