# Phone replay false acceptance: investigation and mitigation plan

Prepared on 24 October 2026, Singapore time. This is a plan only. No application code, session policy, threshold, running service, attendance record, or file under `docs/` was changed.

## Recommendation

Use the existing required-motion policy as interim protection against static-photo presentations. For the single-photo flow, evaluate and integrate a dedicated RGB presentation attack detection (PAD) model in Module 3, with calibration against actual camera captures. Keep identity matching and attendance risk separate from presentation authenticity.

Do not select a new cutoff from the one successful attack. The existing fixed two-blink challenge is useful containment, but is not protection against every prepared video or camera-injection attack. Stronger randomized challenges are a separate, approval-dependent extension.

## Evidence and root cause

The [completed trial](test-logs/phone-replay-test.md#phone-screen-result-and-comparison) records one participant-reported static photograph displayed on a phone being accepted. The operator did not see the captures; device, lighting, brightness, distance, and display conditions remain unknown. This establishes an observed failure, not an attack acceptance rate.

| Signal | Live control | Phone presentation | Implication |
| --- | ---: | ---: | --- |
| Liveness | 0.978987 | 0.822759 | Both exceed 0.6 |
| Face match | 0.881481 | 0.896296 | Recognizing the enrolled photograph does not prove presence |
| Texture | 1.0 | 0.99816 | Existing texture heuristics barely distinguish this attack |
| Color | 1.0 | 1.0 | Plausible skin colors survive display recapture |
| Periodic-artifact penalty | 0.0 | 0.00723 | This presentation does not resemble the strong artificial grids in existing tests |
| Module 3 risk | 0.224883 | 0.260236 | Neither reaches the attendance threshold |
| Final risk | 0.4254 | 0.4254 | Equal venue risk dominates both decisions |
| Committed status | approved | approved | These are saved attendance outcomes |

Relevant implementation findings:

- [`liveness.py`](../module3-face-recognition/app/liveness.py), `_mesh_snapshot()`, scores inferred landmark z-coordinates as depth. These are not measurements from a depth sensor. MediaPipe documents predictions from a cropped image without additional depth input and relative z-coordinates: [official Face Mesh documentation](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_mesh.md#face-landmark-model). The trial demonstrates that a phone photograph can receive plausible inferred geometry.
- `assess_liveness()` combines depth/mesh/texture/color at 30/25/25/20 percent, then applies presentation/challenge factors. The phone's factor was 0.995662. Using the logged rounded values, even setting its depth contribution to zero leaves approximately **0.634742**, still above 0.6. Recalibrating only nose depth is insufficient for this observed combination.
- `_standard_gray()` downsizes crops and `_fft_naturalness()` resizes again to 128×128. Investigate whether this suppresses useful display-frequency evidence; this is a hypothesis to test, not an established cause of this trial.
- [`main.py`](../module2-backend/app/main.py), `_combine_checkin_assessment()`, already rejects a performed liveness failure regardless of risk. Correcting Module 3's verdict will therefore reach the existing rejection path. Changing the face-match threshold or the venue/biometric `max()` rule does not directly address presentation detection.
- The trial had successful biometric responses. Enabling strict security alone would not change these valid passing results. Separately, the non-strict photo path permits unavailable checks; a new PAD model must not create an unnoticed outage bypass.
- [`SessionsPanel.tsx`](../module4-observability/src/components/dashboard/SessionsPanel.tsx) already defaults new dashboard sessions to motion by sending `require_motion_check: !allow_single_photo`. API defaults and existing session policies still permit photo mode.
- [`test_face_module3.py`](../new-tests/test_face_module3.py) tests synthetic screen grids/print patterns and also expects an ordinary sample JPEG to pass liveness. These are useful pipeline checks, but do not validate physical replay resistance. [`test_motion_native.py`](../new-tests/test_motion_native.py) covers repeated static image frames, not a physical display capture.

The current source SHA-256 of `liveness.py` matches the version recorded in the report: `9486ef646708e8d86ce41581a538091854e11e08c418759142704e0f6f1e655e`.

## Implementation sequence

### 1. Establish a replay evaluation matrix

Before modifying scoring, repeat fresh matched control/attack trials using the existing session-scoped instrumentation. Collect device/browser, display type, brightness, camera distance, lighting, photo provenance, and visible borders/reflections as text. Preserve the original report and records. The original attack image is unavailable, so its scalar diagnostics cannot substitute for an image-level regression.

Cover live controls, stationary and moved static-photo displays, high-resolution displays with weak visible artifacts, multiple brightness/distance combinations, and printed photographs. Evaluate prepared video replay separately so static-photo success is not presented as general replay resistance. Include varied users, skin tones, glasses, cameras, and realistic low-light conditions in live controls.

Use the exact production capture transformations: photo mode currently caps the longest side at 720px and encodes JPEG at quality 0.82; sequence mode uses at most 480px and quality 0.7. Split calibration and evaluation by person and capture/display device where possible. Do not tune and evaluate on repeated copies of the same capture.

Process participant captures in memory and retain only sanitized scalar results and trial conditions. Do not add raw captures, videos, landmarks, templates, credentials, or unfiltered logs to the repository or reports. Public benchmark material must have suitable usage rights and must not become a reason to retain student captures.

Deliverable: a new evaluation report under `new-documentations/test-logs/`, including baseline false acceptances, live rejections, unavailable checks, and unknown conditions.

### 2. Apply the existing static-photo containment option

For sessions requiring stronger protection now, use the already supported `require_motion_check: true` policy and keep the dashboard's existing motion default. Any operational policy changes should be deliberate and limited to selected sessions; this inspection changes none.

Reuse the current challenge issuance, sequence verification, enrolled-face checks, expiry, one-time consumption, and atomic attendance transaction. Verify that live users can complete the challenge and that a physical static-photo display cannot obtain a verification ID, including when the phone is moved or tilted. Missing evidence and Module 3 outages must continue to fail on required-motion sessions.

Do not silently turn photo sessions into motion sessions or remove the existing instructor choice. The fixed `blink_twice` action can be satisfied by a suitable prerecorded video; label its protection accurately.

Deliverable: measured static-photo containment using the existing contracts, without a schema migration or recognition-threshold change.

### 3. Add dedicated passive PAD behind the existing image endpoint

Evaluate a small shortlist of CPU-compatible RGB PAD models on the matrix before selecting an implementation. Selection must consider replay accuracy on unseen devices, live-user rejection, inference latency, exact preprocessing, checkpoint provenance, license, and deployable runtime dependencies. An off-the-shelf benchmark result is insufficient to choose a production cutoff.

Proposed implementation locations:

- New `module3-face-recognition/app/pad.py`: bounded, request-local PAD inference with validated finite output and explicit model-unavailable errors.
- `module3-face-recognition/app/assets/` and its README: package the selected checkpoint with its provenance, license, version, and SHA-256; avoid runtime downloads or unverified substitute models.
- `module3-face-recognition/app/config.py`, `requirements.txt`, and `Dockerfile`: validated settings, pinned runtime dependency, reproducible asset packaging, and startup/readiness validation.
- `module3-face-recognition/app/liveness.py`: combine PAD evidence with the current presentation-integrity stage. Keep the documented four-component breakdown available; do not let optimistic inferred depth, sharpness, color, or an identity match compensate for a confident spoof verdict.
- `module3-face-recognition/app/main.py`: keep `/liveness/check` request/response fields stable and return only aggregate diagnostics. Preserve `liveness_passed = (liveness_score >= configured threshold)`; a PAD veto must also produce a score below that threshold. Calibrate the mapping rather than treating an arbitrary model score as a probability.

Test face crop/context and image-scale requirements for the selected model. Compare any higher-resolution texture analysis against the current preprocessing, but retain FFT/LBP/color as supporting evidence. Absence of visible moire must not count as proof of a live face.

Explicitly define how ambiguous/poor-quality results map to the existing contract. They must not produce a fabricated pass. Do not turn a detected spoof into a service-unavailable response: the legacy non-strict backend may approve that fallback. A new retry/step-up response requires a separate contract decision; the current false-liveness result produces a rejected attendance record with the existing appeal path.

The same `assess_liveness()` function is called for the first and last motion frames. Evaluate the new PAD on those lower-resolution sequence images as well, including latency and live-user rejection. A passive improvement must not unexpectedly break motion verification.

Deliverable: a calibrated passive detector that retains the image API, default 0.6 liveness threshold, existing identity templates, and database schema.

### 4. Verify backend enforcement and extend scalar diagnostics

Preserve the existing hard rejection of a performed liveness failure. Add an integration regression with a high identity score, good location, low aggregate risk, and failed PAD/liveness: the saved attendance must be `rejected`, never `approved` or merely `flagged`.

In `module2-backend/app/face_service.py`, validate the detector response shape and finite, in-range scores. Malformed responses, missing/corrupt assets, and transport failures must remain distinguishable from a valid spoof rejection. Check both strict and legacy compatibility behavior.

Extend `module2-backend/app/checkin_diagnostics.py` with an explicit allowlist of PAD scalar outcomes/scores and a bounded detector version identifier. Reuse the existing photo monitor and commitment correlation. It does not currently collect detailed `/liveness/sequence` inference stages, so motion comparisons need explicit sanitized sequence observations rather than assuming photo diagnostics cover them.

Use fixed-cardinality Module 3 metrics for pass/fail/unavailable and latency, consumed by the existing observability stack. Never attach user/session IDs, images, templates, or arbitrary model output as metric labels. Module 4 needs no attendance-decision changes for the passive fix.

Deliverable: an explainable chain from detector verdict to saved attendance, with outages reported honestly.

### 5. Validate and release in stages

Add focused tests under `new-tests/`, for example:

- `test_passive_pad.py`: preprocessing contract, finite outputs, score boundaries, spoof veto despite optimistic legacy components, uncertain evidence, missing/corrupt model, and response privacy.
- `test_phone_replay_decisions.py`: failed liveness plus matching identity/low risk commits rejected attendance; valid live controls still approve; strict and legacy outages remain explicit; an unsuccessful commit is not reported as committed.
- Extend existing native sequence tests for the PAD-enabled first/last-frame path and real display trials. Keep the synthetic-pattern tests as heuristic checks and separate hash consistency assertions from claims of physical liveness.
- Extend diagnostic/monitor tests for the added scalar fields, scoping, filtering, and result classification.

Run Module 2 and Module 3 Python suites in separate processes because both packages are named `app`. Relevant existing checks include `test_face_module3.py`, `test_motion_sequence.py`, `test_motion_landmarker.py`, `test_motion_native.py`, `test_motion_backend.py`, `test_checkin_diagnostics.py`, and `test_monitor_phone_replay.py`. Run the session-policy frontend tests, affected frontend/dashboard builds, and the unchanged public suite against disposable infrastructure. Investigate pre-existing failures separately; the motion documentation already records four backend query-count failures from an earlier run.

Release gates:

1. Live control succeeds and the physical static-phone regression is rejected by the model and saved decision, across the agreed device matrix.
2. Report attack acceptance (APCER), live-user rejection (BPCER), failure-to-process rate, sample sizes, and uncertainty on held-out trials. Agree the acceptable operating point before freezing the model/calibration. NIST's [passive PAD evaluation](https://www.nist.gov/publications/face-analysis-technology-evaluation-fate-part-10-performance-passive-software-based) provides a relevant evaluation framework; a small demonstration is not a statistical accuracy claim.
3. No identity-template change, schema migration, raw-image retention, or response-contract regression.
4. Passive processing fits the existing internal timeout and relevant performance tests; sequence processing remains within its separate documented limits.
5. Asset/inference outages do not bypass the intended protection in the selected rollout policy.

Evaluate candidate models offline or in an isolated test deployment first. Enable a pilot only after these gates pass. If a model causes unacceptable live rejection or operational failure, revert the model deployment while keeping selected sessions on the existing required-motion policy; do not restore photo acceptance and describe it as verified replay protection.

## Specification boundaries and decisions

The baseline plan reuses the documented image and optional-motion endpoints, the existing result columns, and the four-component diagnostics. It does not require changing `docs/`.

Before implementation, check the exact selected PAD fusion against `docs/API-SPECIFICATION.md`: the weights are presented as recommended, while the score/pass relationship is explicit. Adding PAD to the existing integrity stage is the proposed compatible approach. Replacing the weighting, changing its meaning, or adding a separate pass rule that contradicts the returned score would require explicit approval under AGENTS.md rule 6.

The following are separate approval-dependent changes, not implicit parts of this plan:

- **Globally rejecting unavailable photo biometrics:** `docs/INTEGRATION-GUIDE.md` explicitly describes proceeding after Module 3 timeouts/errors, and existing tests preserve that behavior. Decide whether to keep legacy compatibility, use existing strict mode with its wider effects, or approve a narrowly scoped required-biometric failure policy. Do not claim the new PAD protects a path that approves when PAD is unavailable.
- **Mandatory motion for every existing photo session or automatic step-up:** the optional extension preserves image contracts when `require_motion_check` is false. Changing that behavior needs approval.
- **Randomized challenge actions/timing:** the referenced motion contract currently specifies `action: "blink_twice"`. A stronger challenge would need server-selected expected actions, server-side sequence verification, and the existing account/session/enrollment/expiry/consumption binding; approve any contract or schema changes before implementing. A random ID alone does not bind image content to a fresh action, and a web challenge does not establish a trusted camera origin.

Unspecified today: a selected PAD model and supported hardware, an agreed attack/live error budget, representative evaluation conditions, and the desired photo-outage/retry policy. The API's expectation of flat inferred z-coordinates for screens is contradicted by this trial and should not be treated as a reliable physical assumption.

## Checks performed during this inspection

- Reviewed the report, relevant flows across all four modules, API/integration/database/security specifications, existing motion documentation, diagnostics, and related tests.
- Recomputed both logged liveness scores and final risks from the sanitized JSON; verified both recorded commitment statuses. Arithmetic is consistent.
- Verified current `liveness.py` checksum matches the report's tested version.
- Parsed all 32 Python source files in the backend and face-service `app` directories with Python's AST parser; all parsed successfully. This is a syntax check, not runtime validation.
- Executed the three existing monitor test functions using Python's standard-library unittest runner, including report preservation in a temporary directory: **3 passed**. Pytest was not available.
- Full application/model/frontend suites were not run: the local Python lacks application/test dependencies, Node is unavailable, and Docker reports no running containers. Previously reported **102 passed, 1 skipped** is historical report evidence, not a result from this inspection.
- The plan's six local links resolve and its whitespace checks pass. Repository `git diff --check` reports pre-existing trailing whitespace in the user's modified replay report at line 463; that file was left unchanged.
- Added only this plan. Preserved the pre-existing user modification to `test-logs/phone-replay-test.md`; no files under `docs/` were modified.

## Endpoints reused by the plan

- Module 2: `POST /api/v1/sessions/`, `PATCH /api/v1/sessions/{id}`, `POST /api/v1/motion/challenges`, `POST /api/v1/motion/challenges/{id}/verify`, `POST /api/v1/checkins/`, and authenticated check-in reads for commitment verification.
- Module 3: `POST /liveness/check`, `POST /liveness/sequence`, `POST /face/verify`, `POST /risk/assess`, `GET /health`, and `GET /metrics`.
- No new endpoint is proposed for the baseline passive fix. No endpoints were called to change application data during this inspection.
