# Image replay threshold implementation

Implemented on 25 October 2026, Singapore time.

The user approved a final liveness threshold of **0.85**, a minimum depth score of **0.80**, and a minimum mesh score of **0.80**, including the deviation from the documented 0.6 liveness cutoff. All files under `docs/` remain unchanged.

## Decision and score calculation

The existing component calculations, 30/25/25/20 weighting, and presentation/challenge integrity factors are preserved. The change adds independent depth and mesh minimums after the existing calculation:

```text
weighted = 0.30 × depth + 0.25 × mesh + 0.25 × texture + 0.20 × color
pre_gate_liveness_score = round(weighted × presentation_integrity × challenge_integrity, 6)

depth_passed = depth >= 0.80
mesh_passed  = mesh >= 0.80

if either component minimum fails:
    liveness_score = 0.0
    liveness_passed = false
else:
    liveness_score = pre_gate_liveness_score
    liveness_passed = liveness_score >= 0.85
```

Equality passes: depth/mesh scores of exactly 0.80 satisfy their respective minimums, and a final score of exactly 0.85 passes when both component checks pass. The minimum checks use the unrounded component values; rounded diagnostic values close to 0.80 may therefore need their corresponding pass flags to interpret correctly.

Setting the failed-check score to zero prevents texture/color scores from compensating for insufficient geometry and keeps the returned final score below the approved cutoff. The score before this minimum check remains available in diagnostics. These are heuristic scores, not calibrated probabilities.

No face or missing landmarks still returns a failed result and score zero. Configuring a final threshold of zero does not override failed component checks or make a missing face pass.

## Shared photo and motion policy

- `POST /liveness/check` uses the configured final threshold and both component minimums.
- `POST /liveness/sequence` applies the same policy to its first and last frames. The sequence now explicitly passes `settings.liveness_threshold` instead of relying on the former hardcoded 0.6 default.
- Direct `assess_liveness()` calls also resolve an omitted threshold from runtime settings.
- Two complete blinks, identity matching, one-face tracking, frame limits, challenge expiry, and one-time evidence consumption retain their existing behavior. Two blinks cannot override a failed passive check.
- Module 2's existing hard-rejection rule handles a received liveness failure. A good identity match and low attendance risk cannot override it. A failed motion sequence does not obtain a verification ID and cannot be consumed for attendance.

The existing non-strict photo behavior when biometric services are unavailable is unchanged. This work strengthens performed checks; it does not remove that separate fallback limitation or make the fixed two-blink action resistant to every prerecorded video.

## Configuration and diagnostics

| Environment variable | New default | Purpose |
| --- | ---: | --- |
| `LIVENESS_THRESHOLD` | 0.85 | Minimum final liveness score |
| `LIVENESS_DEPTH_THRESHOLD` | 0.80 | Minimum depth component |
| `LIVENESS_MESH_THRESHOLD` | 0.80 | Minimum mesh component |

All three settings accept finite values in the existing 0–1 configuration range; malformed/out-of-range values fail configuration loading. Explicit environment overrides take precedence over defaults. Settings are loaded at process startup.

Existing liveness responses retain their top-level shape. The free-form `details` object adds only these aggregate fields:

- `depth_threshold`, `mesh_threshold`
- `depth_passed`, `mesh_passed`
- `pre_gate_liveness_score`

No-face responses include the same fields, with failed flags and a zero pre-check score. Module 2's scalar diagnostic allowlist includes the new fields. Diagnostics remain disabled unless explicitly enabled for selected sessions, and the existing monitor reuses that allowlist. No raw images, landmarks, templates, request bodies, or arbitrary model output are added to logs or storage.

## Previously recorded cases

The reports currently reside in the pre-existing `new-documentations/imge-replay/` directory. They were preserved, including that directory's spelling:

- [Trial 0](../imge-replay/image-replay-test-0.md)
- [Trial 1](../imge-replay/image-replay-test-1.md)

| Recorded case | Historical final score | Depth | Mesh | New policy applied to recorded scalars |
| --- | ---: | ---: | ---: | --- |
| Trial 0 real-face control | 0.978987 | 0.99411 | 0.92302 | Pass |
| Trial 0 phone photograph | 0.822759 | 0.62945 | 0.75188 | Fail; both component minimums fail, final score becomes 0 |
| Trial 1 real-face control | 0.907025 | 0.86414 | 0.82673 | Pass |
| Trial 1 phone photograph | 0.841207 | 0.74772 | 0.77296 | Fail; both component minimums fail, final score becomes 0 |

The automated checks reconstruct scoring from the rounded scalar observations with rounding tolerance. They do not reprocess the original capture images, which are unavailable, and do not change the historical approved attendance records. These four examples from one enrolled account do not establish a general replay rejection or genuine-user rejection rate.

## Files changed

| File | Change |
| --- | --- |
| [`module3-face-recognition/app/config.py`](../../module3-face-recognition/app/config.py) | Approved final default and validated depth/mesh settings |
| [`module3-face-recognition/app/liveness.py`](../../module3-face-recognition/app/liveness.py) | Shared default resolution, hard component checks, final-score gating and aggregate diagnostics |
| [`module3-face-recognition/app/motion.py`](../../module3-face-recognition/app/motion.py) | Explicit shared final threshold for sequence passive checks |
| [`module3-face-recognition/app/main.py`](../../module3-face-recognition/app/main.py) | Consistent failed-component diagnostics in no-face responses |
| [`module2-backend/app/checkin_diagnostics.py`](../../module2-backend/app/checkin_diagnostics.py) | Allowlist the new finite scalar scores/thresholds and boolean flags |
| [`new-tests/test_liveness_thresholds.py`](../../new-tests/test_liveness_thresholds.py) | 35 cases for configuration, boundaries, recorded scalars, photo/sequence decisions, and privacy |
| [`new-tests/test_checkin_diagnostics.py`](../../new-tests/test_checkin_diagnostics.py) | Three cases for saved approval/rejection despite low risk, plus diagnostic filtering |
| [`new-tests/backend_motion_cases.py`](../../new-tests/backend_motion_cases.py) | Failed passive evidence cannot issue/consume proof even with two blinks |
| This document | Implementation, approved specification exception, verification, and limitations |

Module 1 and Module 4 integration paths were reviewed before modifying code. No frontend, dashboard, database-schema, identity-template, enrollment, consent, or attendance-data changes were needed.

## Validation

Tests used existing dependency images with repository source mounted read-only. Native face/model checks and backend checks ran in separate containers because both services use an `app` package. Public HTTP tests targeted a dedicated Compose project, `saiv-replay-threshold-20261025`, using the existing `new-tests/docker-compose.audit.yml`: a temporary PostgreSQL database, separate Redis, isolated backend/face services, and no published ports. They did not target the user's existing database or running application services.

| Check | Result |
| --- | --- |
| Existing native face and motion suites before the change | **47 passed** |
| Updated policy tests plus existing native suites | **82 passed**: 35 new cases plus the original 47 |
| Backend diagnostics, monitor, and motion suites | **47 passed, 4 failed**; all four failures are the existing query-count expectations described below |
| Unchanged `tests/public` HTTP suite on the disposable stack | **102 passed, 1 skipped** |
| Existing frontend session-policy tests | **18 passed** |
| Isolated running face-service settings | Verified final/depth/mesh thresholds **0.85 / 0.80 / 0.80** |
| Isolated backend and face health | HTTP **200** |
| Changed Python syntax | All eight changed/new Python files parsed successfully |
| Documentation/report preservation | All 14 before/after hashes match: 11 files under `docs/` and three existing files under `imge-replay/` |
| Whitespace | `git diff --check` passed |

The backend's four existing failures are:

- `test_session_list_constant_query_count[0]`
- `test_session_list_constant_query_count[1]`
- `test_session_list_constant_query_count[20]`
- `test_read_mode_is_scoped_and_write_rollback_still_works`

They expect two read queries while the current check-in-listing implementation executes three. The same four failures were reproduced before adding the new backend cases (**43 passed, 4 failed**) and were already recorded in the existing [motion documentation](../MOTION-VERIFICATION.md). This work does not alter that query path or relax those assertions. All 39 added test cases passed.

The public suite's single skip is the pre-existing `TestConcurrentUsers.test_concurrent_checkins` skip, whose reason cites SQLite concurrent-write flakiness. That test is marked skipped even in this disposable PostgreSQL run. No new skip or xfail was introduced, and no public test files were modified.

## Deployment and remaining validation

The updated source has been verified in isolated containers. The user's existing running application containers were not rebuilt or restarted, so they continue using their previous packaged code until deployment. Deploy the updated face service for the new decision policy, and the backend for the expanded scalar diagnostic allowlist. No frontend rebuild or database migration is needed.

After validation, the four disposable test containers and their dedicated network were removed successfully. The existing application stack was preserved. The public test XML is available locally at `/tmp/saiv-replay-threshold-results/public.xml`.

For the existing local Compose stack, activation can use:

```sh
docker compose up -d --build face-recognition backend
```

Check for explicit threshold overrides before deployment, verify the service health and effective settings afterward, and use fresh sessions for physical trials. Existing motion proofs issued before deployment can retain their previously stored result until their short expiry; use newly issued challenges when validating the new policy.

Fresh manual camera trials remain necessary for both single-photo and two-blink flows. Include genuine users in dim light and varied framing/distance, static displays with weak artifacts, and prepared video replays. Measure replay acceptance and genuine-user rejection on captures separate from those used to choose these cutoffs. No claim of general replay resistance is made from the scalar tests.

## Endpoints and specification exception

No endpoint was added. Implementation reuses Module 3 `POST /liveness/check` and `POST /liveness/sequence`; backend integration reuses `POST /api/v1/motion/challenges`, `POST /api/v1/motion/challenges/{id}/verify`, and `POST /api/v1/checkins/`.

The approved exception replaces the 0.6 default in `docs/API-SPECIFICATION.md` and `docs/SECURITY-REQUIREMENTS.md` with 0.85 and adds the 0.80 component minimums. This record documents that exception while leaving `docs/` read-only. The original four component weights, supported challenge types, response top-level fields, database schema, risk thresholds, and service-failure policy retain their existing contracts.
