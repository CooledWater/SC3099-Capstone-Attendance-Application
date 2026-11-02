# Anti-spoofing investigation and recommendation

Investigated on 1 November 2026, Singapore time. This is an investigation and proposal; no application code, thresholds, session policies, attendance, or files under `docs/` were changed.

Further adjustment of the existing thresholds is not a viable standalone fix. It can reject particular captures, but the recorded genuine and photo scores overlap and sometimes have the opposite ordering. Use the existing motion requirement as immediate protection against ordinary static photos, then evaluate dedicated presentation attack detection (PAD) together with randomized, server-verified actions. The existing fixed two-blink challenge has already accepted a phone-video replay.

## Evidence from the completed trials

These are participant-confirmed presentations recorded in the existing reports. Captures were not retained or independently inspected, and most capture conditions are unknown. Scores are heuristic outputs, not probabilities.

| Trial | Genuine liveness | Photo liveness returned | Observed photo outcome | Interpretation |
| --- | ---: | ---: | --- | --- |
| [0](image-replay-test-0.md) | 0.978987 | 0.822759 | approved | Both passed the historical 0.60 cutoff |
| [1](image-replay-test-1.md) | 0.907025 | 0.841207 | approved | Both passed the historical 0.60 cutoff |
| [2](image-replay-test-2.md) | 0.909611 | 0.000000 | rejected | Photo failed the current geometry gates; pre-gate score 0.665702 |
| [3](image-replay-test-3.md) | 0.000000 | not submitted | no comparison | Genuine capture hit the multiple-face guard before component analysis |
| [4](image-replay-test-4.md) | 0.911227 | 0.937271 | approved | Photo outscored its genuine control |
| [5](image-replay-test-5.md) | 0.975383 | 0.962048 | flagged | Photo passed biometrics; geofence alone caused the flag |
| [6](image-replay-test-6.md) | 0.976928 | 0.000000 | rejected | Other-person photo had no usable face; no identity or PAD discrimination was measured |

Trials 2–6 record the 0.85 liveness cutoff and independent 0.80 depth/mesh minimums. Current container configuration independently confirms 0.85/0.80/0.80 and identity 0.70. Its liveness source hash matches the local source and the current policy recorded in the earlier investigation: `9f024d986eba8a400d2494366b0686b54d8b5c97a0fc00fa877256111622eb8f`.

Test 6 cannot establish different-person discrimination: no face was extracted, and its zero component and identity values are early-return defaults. Test 3 similarly cannot supply measured genuine components. Neither is evidence that the current components reliably recognize a photo.

The [completed video trial](../video-replay/video-replay-test-0.md) also matters: the participant-reported phone video passed two blinks, passive liveness 0.905077, and identity 0.866667. Attendance was flagged for `device_unknown`, as was the genuine control. That is biometric replay acceptance, without an end-to-end approved-attendance replay.

## Threshold viability

The passive scorer in [liveness.py](../../module3-face-recognition/app/liveness.py) calculates:

```text
W = 0.30 * depth + 0.25 * mesh + 0.25 * texture + 0.20 * color
P = min(1 - 0.60 * periodic_artifact_penalty,
        0.45 + 0.55 * texture,
        0.45 + 0.55 * color)
S = round(W * P, 6)  # passive challenge factor is 1
pass = depth >= depth_cutoff and mesh >= mesh_cutoff and S >= final_cutoff
```

Test 4 alone disproves full separation by these three minimums:

| Signal | Genuine | Photo |
| --- | ---: | ---: |
| Final liveness | 0.911227 | 0.937271 |
| Depth | 0.87359 | 0.92860 |
| Mesh | 0.81612 | 0.84232 |

Any combination of these minimums that retains this genuine capture also retains this photo. Its texture and presentation integrity are higher too, while color is equal; simply changing positive component weights cannot reverse that ordering.

I reconstructed 11 captures using the real current scoring function, substituting the recorded component scalars for image/model extraction. These are the six component-measured genuine controls in trials 0/1/2/4/5/6 and five same-person photos in trials 0/1/2/4/5. The reconstructed pre-gate scores agree within 0.000003, allowing for rounded report values.

With the current 0.80 geometry gates held fixed:

| Final liveness cutoff | Genuine controls retained, out of 6 | Photo trials still passing, out of 5 |
| --- | ---: | --- |
| 0.85 | 6 | 4, 5 |
| 0.90 | 6 | 4, 5 |
| 0.94 | 3 | 5 |
| 0.95 | 3 | 5 |
| 0.962049 | 3 | none |
| 0.97 | 3 | none |

Rejecting all five recorded same-person photos by the final cutoff requires a value greater than 0.962048. Retaining all six measured genuine controls requires a value at most 0.907025. Those requirements are incompatible. The three genuine rejections at the stricter cutoffs are an observed-data tradeoff, not a population rejection-rate estimate.

I also enumerated all 17,576 distinct threshold-decision combinations represented by the observed liveness, depth, mesh, and identity values, plus boundaries 0 and 1. This represents every decision interval for four `score >= cutoff` tests on this dataset. Of 375 combinations preserving all six genuine controls, **none rejects all five photos**. Threshold selection cannot manufacture the missing separation.

Identity and attendance risk are unsuitable substitutes:

- A photograph of the enrolled person should resemble that person. In test 2 the identity scores are identical; in test 5 the photo scores higher than the genuine control, 0.903704 versus 0.874074. Raising identity cutoffs attacks genuine-user tolerance without establishing presence.
- Lower attendance risk is considered safer. In test 4 the photo has lower saved risk than the genuine control, 0.1298 versus 0.1326. Lowering the risk cutoff enough to flag that photo also flags its control, and a risk flag does not itself reject a spoof. Geofence/device flags in other trials are separate from PAD performance.

The earlier threshold change did help: current policy rejects the recorded photos from trials 0/1/2. It did not solve trials 4/5. Threshold calibration remains necessary for a better detector; further tuning of these existing signals cannot provide reliable standalone replay prevention.

## Why the current signals fail

MediaPipe estimates a facial surface from an RGB image. It does not measure the physical distance from camera to skin. Google's [Face Mesh documentation](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_mesh.md) describes this inference and relative landmark coordinates. A displayed face can therefore receive plausible inferred nose depth and a complete mesh. The current depth formula also uses image-scale-dependent geometry; a plausible mesh is useful for tracking, but is not proof of liveness.

Texture and color are handcrafted heuristics here. Test 5 gives both presentations texture 1.0, color 1.0, presentation integrity 1.0, and periodic-artifact penalty 0.0. A screen need not produce detectable moire in the processed face crop. Raising the same score cutoff does not add another observable signal.

The native static-sequence test repeats identical JPEG frames and correctly finds no blink. The periodic-artifact tests use constructed patterns. Passing these tests verifies their particular inputs and decision logic; it does not establish resistance to varied physical display recaptures or prepared videos.

## Recommended implementation direction

1. **Use existing required motion for sessions needing static-photo protection now.** Set `require_motion_check=true` with liveness required and use the existing enrollment/identity binding. The current dashboard's enabled “Require liveness check” control sends both requirements; the API's motion default remains false and existing photo sessions retain their policies. A static image cannot supply genuine eye opening/closing cycles, so the temporal requirement is useful containment. Physical static-photo trials are still needed. The fixed action is already bypassed by the recorded video, so it is not sufficient for the broader replay threat.

2. **Upgrade to unpredictable actions verified on the server.** Issue a short sequence such as center → blink → turn left/right → center, with randomized order and prompt timing. Require a blink as well as movement: moving or tilting a photograph can imitate a pose change. Check expected actions, order, timing, face continuity and enrolled identity from the submitted sequence. Reuse account/session/reference binding, expiry, one submission per challenge and atomic one-time proof consumption. Persist expected actions as bounded challenge metadata. A random challenge ID alone does not prove the recording is fresh; the observed response must satisfy the newly selected prompt. This raises the difficulty of prepared replay, but does not guarantee resistance to adaptive video selection, real-time synthesis or camera injection.

3. **Evaluate a dedicated RGB PAD model in Module 3.** Use a model trained to distinguish genuine camera captures from print/display presentations. [MiniFASNet / Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/README_EN.md) is a concrete open-source baseline for an isolated evaluation, not a selected production detector. Its maintainers explicitly note camera/scene dependence. Match the selected model's crop scales, color ordering, normalization and score semantics; pin model assets and verify any conversion against original inference. Do not assume inserting a network automatically fixes the recorded cases. NIST's [PAD evaluation findings](https://www.nist.gov/news-events/news/2023/09/whats-wrong-picture-nist-face-analysis-program-helps-find-answers) show substantial variation by algorithm and attack type.

4. **Make PAD failure independent of favorable attendance risk.** A valid spoof verdict should cause failed liveness and use the existing backend rejection rule. An uncertain result, missing model, malformed output or timeout should request retry/manual attendance rather than automatically approve. Today the non-strict photo path can proceed when Module 3 is unavailable. Existing strict mode blocks missing required results but has wider effects; enabling it globally is not a narrowly scoped PAD change. Keep all frames request-scoped and store only bounded scores, verdicts and detector versions. The existing raw-image storage prohibition remains applicable.

For this capstone, prioritize required motion immediately, followed by the combined randomized-action and RGB-PAD prototype. If stronger assurance is required against adaptive synthesis or injected camera input, evaluate supervised check-in or a controlled capture device with actual depth/IR sensing and a protected capture path. Merely adding browser-side face checks or device signatures does not establish authenticity of the supplied camera pixels. These stronger options carry additional hardware/deployment work and need their own validation.

## Validation before claiming a fix

Use repeated genuine, printed-photo, phone/tablet static-photo and recorded-video trials, including the conditions that produced trials 4/5 and the successful two-blink video. Include moved/tilted photos, varied image scale, display brightness, lighting, distances, camera models and genuine users with glasses or reduced blink/pose mobility. Include injected/reordered/reused frames if camera injection is in scope, plus unavailable-model/service cases. Provide a manual attendance path for users who cannot complete the challenge.

Choose the model and operating point on development trials, then freeze them and evaluate separate people/devices/capture conditions. Report attack acceptance and genuine rejection separately, with failure-to-process rates, denominators and uncertainty. Distinguish PAD pass/fail, identity, device/geofence decisions and committed attendance. Agree acceptable error and latency budgets before deployment. Do not interpret these few captures from one participant as accuracy estimates. No new raw-media retention is proposed; any dataset collection or retention would need separate consent and reconciliation with `docs/`.

## Specification boundaries and integration

The existing [threshold implementation record](threshold-implementation.md) documents approval for 0.85 and 0.80 geometry minimums, while `docs/API-SPECIFICATION.md` and `docs/SECURITY-REQUIREMENTS.md` still describe 0.60. Their assumption that a screen yields flat inferred landmarks is not supported by these observations.

The motion contract currently fixes `action: "blink_twice"`. Randomized expected actions require an explicit contract/metadata extension. The integration guide explicitly permits proceeding after face-service failure; changing that behavior requires approval under AGENTS.md rule 6. PAD fusion must also reconcile the explicit liveness score/pass relationship and documented component calculation. No conflicting implementation has been made, and `docs/` remains read-only.

Relevant paths reviewed across all four modules: camera capture and `FaceVerification.tsx`; backend `face_service.py`, motion proof lifecycle and check-in decision; Module 3 configuration, liveness and motion analysis; dashboard session policy and attendance score display. No identity-template or database migration is needed merely to evaluate PAD; randomized expected-action metadata must be designed against the database rules before implementation.

## Checks and files

- **82 tests passed**, two dependency deprecation warnings: `test_liveness_thresholds.py`, `test_face_module3.py`, `test_motion_sequence.py`, `test_motion_landmarker.py`, and `test_motion_native.py`. Ran with the repository mounted read-only in a disposable, network-disabled container, using the existing face-service dependency image and current local source.
- **11 scalar reconstructions passed**, plus the complete four-threshold decision enumeration above. These substitute recorded component outputs; they do not reprocess unavailable historical pixels.
- Read current container threshold configuration and liveness source hash; verified agreement with local source. No running service was restarted or reconfigured.
- Preservation checks confirm all 362 pre-existing tracked/untracked files are unchanged. All 10 local report links resolve, and repository/new-report whitespace checks pass.
- No attendance API, database writes, new physical trials, public HTTP suite or new model evaluation was performed. There is no feature implementation requiring a full regression run.

Reproduce the focused suite with the face-service dependencies available:

```sh
python -m pytest -q -p no:cacheprovider new-tests/test_liveness_thresholds.py new-tests/test_face_module3.py new-tests/test_motion_sequence.py new-tests/test_motion_landmarker.py new-tests/test_motion_native.py
```

Files changed: only this new report. Existing reports, including the pre-existing untracked trial-6 report and run JSON, are preserved.

Endpoints: none implemented or called for attendance. Existing paths inspected for reuse are backend `POST /api/v1/motion/challenges`, `POST /api/v1/motion/challenges/{id}/verify`, `POST /api/v1/checkins/`, and internal `POST /liveness/check`, `POST /liveness/sequence`, `POST /face/verify`, `POST /risk/assess`.
