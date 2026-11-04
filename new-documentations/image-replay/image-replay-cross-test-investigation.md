# Image replay tests 0, 1, 2 and 4: code and score comparison

Investigated on 30 October 2026, Singapore time. This is a retrospective analysis of the existing scalar diagnostics, repository history and current deployed source. No new attendance was submitted.

The participant now confirms the same capture device, display phone and person were used at four different locations. This updates the context of the historical reports without changing their original observations. Identical source photograph, displayed image scale, pose, camera distance, exposure, lighting and reflections across runs have not been established.

## Findings

1. **Tests 0 and 1 did not use test 4's liveness decision policy.** Their final threshold was 0.60, with no independent 0.80 depth/mesh gates. Tests 2 and 4 used threshold 0.85 and both 0.80 gates. The underlying component and presentation-penalty calculations were preserved across that policy change.
2. **Tests 2 and 4 used the same recorded liveness policy and scoring source.** Their different outcomes are explained at the calculation level by different measured geometry and periodicity signals. Test 4's replay actually scored above its genuine control on depth, mesh, texture and presentation integrity.
3. **Identity matching is separate from liveness.** The dlib descriptor, SimHash/Hamming score implementation and recorded 0.70 identity threshold are unchanged. Identity scores never showed a large control/replay separation; test 2's identity scores were identical.
4. **The entire attendance calculation was not identical across runs.** A later backend device policy subtracts the service's placeholder device risk of 0.10 for the trusted, verified device in test 4. This explains its lower saved risk, but does not affect liveness or explain the change in liveness separation.
5. **The exact physical cause of test 4's different input signals cannot be recovered.** No historical capture images were retained. The evidence establishes what the scorer measured and how it decided, but does not isolate lighting, framing, exposure, source-photo presentation or other capture conditions as the cause.

Sources: [test 0](image-replay-test-0.md), [test 1](image-replay-test-1.md), [test 2](image-replay-test-2.md), [test 4](image-replay-test-4.md), and [the approved threshold implementation](threshold-implementation.md).

## Compare the same metric

All four pairs used the single-photo `passive` path, with motion checking disabled, liveness and identity checking required, and attendance risk cutoff 0.50. Every recorded liveness, identity and risk call returned a usable HTTP 200 result. Service-unavailable fallbacks do not explain these observations.

The signed gap below is **control minus replay**. A negative value means the replay scored higher. Scores are heuristic outputs, not calibrated probabilities.

| Test | Liveness threshold | Depth/mesh minimums | Control liveness | Replay before geometry gates | Replay returned liveness | Returned gap | Replay attendance |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| 0 | 0.60 | No independent gates | 0.978987 | 0.822759 | 0.822759 | +0.156228 | approved |
| 1 | 0.60 | No independent gates | 0.907025 | 0.841207 | 0.841207 | +0.065818 | approved |
| 2 | 0.85 | 0.80 / 0.80 | 0.909611 | 0.665702 | 0.000000 | +0.909611 | rejected |
| 4 | 0.85 | 0.80 / 0.80 | 0.911227 | 0.937271 | 0.937271 | -0.026044 | approved |

Test 2's comparable gap **before geometry gates** is 0.243909, not 0.909611. The additional 0.665702 of returned-score separation comes from replacing the failed replay score with zero. Test 4 passes both gates, so no such replacement occurs. Tests 0 and 1 have no geometry-gate operation; their existing scores are the comparable pre-gate values.

| Test | Identity control → replay, cutoff 0.70 | Final attendance risk control → replay, cutoff 0.50 |
| --- | --- | --- |
| 0 | 0.881481 → 0.896296 | 0.4254 → 0.4254 |
| 1 | 0.881481 → 0.859259 | 0.2429 → 0.2649 |
| 2 | 0.918518 → 0.918518 | 0.2330 → 0.4604 |
| 4 | 0.918518 → 0.903704 | 0.1326 → 0.1298 |

Thus the premise of a large gap applies primarily to **passive liveness**, not to identity scores or consistently to final risk. In test 0, venue risk dominates both final scores. Test 2 is rejected by the independent liveness-failure rule even though final risk remains below 0.50.

## What code changed

The policy change is preserved in commit `2b94a0e8db84380575f28c561ce9c8c532c2dce2` (`fixed photo replay attack`). The commit time is not treated as the deployment time: test 2 explicitly records the already deployed 0.85/0.80/0.80 policy before that commit was made.

Comparing the pre-policy `liveness.py` from `2b94a0e^` with current source gives:

| Source | SHA-256 |
| --- | --- |
| Pre-policy liveness source; exactly matches deployed hashes recorded in tests 0 and 1 | `9486ef646708e8d86ce41581a538091854e11e08c418759142704e0f6f1e655e` |
| Current liveness source; byte-identical to policy commit `2b94a0e` and current running service | `9f024d986eba8a400d2494366b0686b54d8b5c97a0fc00fa877256111622eb8f` |

An AST comparison finds **25 unchanged functions**; only `assess_liveness` changed. The changes resolve the configured default, add depth/mesh gates, zero the score when either gate fails, and expose the corresponding scalar diagnostics. Depth estimation, mesh plausibility, crop selection, FFT/texture analysis, color analysis, component weights and presentation-integrity formulas are unchanged.

Tests 2 and 4 both record deployed source matching their local baseline. Liveness/configuration source has no changes between `2b94a0e` and the current working tree. Current container hashes independently match local source. Later uncommitted changes to the face-service router add diagnostics to `/liveness/sequence`; they do not change `/liveness/check`, which all four image pairs used.

The dlib embedding, SimHash template comparison, detection, image decoding and risk-scoring source files are byte-identical between the pre-policy revision, policy commit and current working tree. Test 1 additionally preserves explicit embedding/risk hashes consistent with current source. The pinned MediaPipe, OpenCV and face-recognition requirements are unchanged.

This supports the same **source implementation and recorded policy** for tests 2 and 4. It does not prove byte-identical historical runtime environments: full dependency/model-binary digests and complete effective settings were not archived for every run. In particular, dlib is not independently pinned in `requirements.txt`. Current runtime versions are MediaPipe 0.10.18, OpenCV 4.11.0.86, NumPy 1.26.4, face-recognition 1.3.0 and dlib 20.0.1; these are current observations, not reconstructed historical package inventories.

## Why the liveness gap changed

The shared passive calculation is:

```text
W = 0.30 × depth + 0.25 × mesh + 0.25 × texture + 0.20 × color
P = min(1 - 0.60 × periodic_artifact_penalty,
        0.45 + 0.55 × texture,
        0.45 + 0.55 × color)
pre_gate = round(W × P, 6)  # passive challenge factor = 1

Tests 0/1: final = pre_gate; pass if final >= 0.60
Tests 2/4: final = pre_gate if depth >= 0.80 and mesh >= 0.80 else 0
           pass if both gates pass and final >= 0.85
```

| Test | Depth control → replay | Mesh control → replay | Texture control → replay | Periodic-artifact penalty control → replay | Presentation integrity control → replay |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.99411 → 0.62945 | 0.92302 → 0.75188 | 1.00000 → 0.99816 | 0.00000 → 0.00723 | 1.000000 → 0.995662 |
| 1 | 0.86414 → 0.74772 | 0.82673 → 0.77296 | 0.99630 → 0.97718 | 0.01452 → 0.03991 | 0.991288 → 0.976054 |
| 2 | 0.86713 → 0.60928 | 0.80908 → 0.75161 | 0.99883 → 0.92752 | 0.00458 → 0.28422 | 0.997252 → 0.829468 |
| 4 | 0.87359 → 0.92860 | 0.81612 → 0.84232 | 0.99797 → 0.99923 | 0.00796 → 0.00301 | 0.995224 → 0.998194 |

Color is 1.0 throughout except test 1's replay at 0.99997, so it contributes almost no discrimination.

- **Test 0:** Lower replay depth accounts for 0.109396 of the weighted-score gap; mesh accounts for 0.042786. Texture and the artifact penalty contribute little. The 0.60 policy still accepts the replay.
- **Test 1:** Lower replay depth/mesh account for about 0.048365 of the weighted-score gap. Texture and the modest presentation penalty add separation, but the replay remains above 0.60.
- **Test 2:** Replay depth and mesh both fail 0.80. Its periodic-artifact penalty is also much larger: 0.28422 versus 0.00458. Weighted score 0.802565 times presentation integrity 0.829468 gives about 0.665702, already below 0.85; the gates then set it to zero.
- **Test 4:** Replay depth, mesh and texture all exceed the paired control. Its artifact penalty is lower, so its presentation integrity is higher. `0.938967 × 0.998194 ≈ 0.937271`; both gates and the final threshold pass normally. There is no evidence of a skipped check or an alternate scoring formula in this attempt.

The genuine controls in tests 1, 2 and 4 are close: 0.907025, 0.909611 and 0.911227. The replay signals change much more. Inferred replay landmark Z variance rises from 0.0003470 in test 2 to 0.0006188 in test 4; relative nose depth rises from 0.03323 to 0.04533. FFT peak-to-mean falls from 75.458 to 38.681, producing a much smaller periodicity penalty under the same smoothstep formula. These measured inputs account for the direction of the scoring change.

## Why the same person and phones can produce these signals

The passive path uses MediaPipe `solutions.face_mesh.FaceMesh` in static-image mode. Its Z values are **inferred from the RGB face image**, not measured physical depth. The source itself documents that a flat photograph can receive convincing inferred geometry. This path does not use the motion sequence's task model or prove a blink.

The depth formula combines absolute nose Z, Z standard deviation and cheek-to-nose Z difference. These quantities are not divided by face width. Mesh plausibility also includes face spans, interocular distance, mouth width and face height measured in normalized image coordinates. Consequently, the scorer is sensitive to how the face occupies the image; the same person's displayed photograph can receive a higher score with different scale/framing or pose. This is a mechanism visible in the code, not a recovered measurement of test 4's camera distance.

Texture/color operate on a detected-face crop with approximately 6% margins. Larger crops are reduced to at most 256 pixels, and FFT analysis resizes to 128 × 128. The unchanged frontend limits the captured frame to a 720-pixel longest side and JPEG quality 0.82. As an inference from this processing, changes in image scale, focus, exposure and capture conditions can change or suppress display artifacts before scoring. A phone border visible in the overall capture is not guaranteed to survive the face crop. The reports do not preserve crop dimensions or sufficient exposure/framing measurements to assign the observed change to one cause.

Location coordinates are not supplied to `/liveness/check`; its inputs are the image and challenge type. Changing venue metadata therefore has no direct effect on that score. Physical conditions associated with a location may affect the captured image. GPS distance separately affects venue risk.

Because test 4's replay exceeds its control in every positively weighted component, with color equal and presentation integrity higher, simply raising the existing final, depth or mesh minimums cannot reject this replay while retaining its paired genuine control. Changing thresholds alone would not solve the separation failure demonstrated by this pair.

## Identity and final-risk calculations

Identity uses a 128-dimensional dlib descriptor, deterministic 256-bit SimHash and calibrated Hamming similarity. For these above-threshold matches the unchanged mapping is `score = 1 - 0.30 × (Hamming fraction / 0.158203)`, with decision cutoff 0.70. The reported scores correspond to approximately 16/14 differing bits in test 0, 16/19 in test 1, 11/11 in test 2 and 11/13 in test 4 (control/replay). Equal scores can therefore arise from the same Hamming distance without identical images. Matching the enrolled identity does not establish presentation liveness.

For all eight attempts, the recorded Module 3 formula is:

```text
R3 = round(0.25 × (1 - returned_liveness), 6)
   + round(0.25 × (1 - identity_score), 6)
   + 0.100000 device + 0.075000 network + 0.015000 geolocation
```

Commit `2b39268` on 26 October introduces the backend device-binding policy used by test 4. `device_binding.apply_risk` replaces the service's placeholder device contribution with 0 for a trusted, verified, unshared device. Test 4 records exactly this subtraction:

| Test 4 | Service risk | Backend-adjusted service risk | Venue risk | Saved final risk |
| --- | ---: | ---: | ---: | ---: |
| Control | 0.232563 | 0.132563 | 0.0337 | 0.1326 |
| Replay | 0.229756 | 0.129756 | 0.0430 | 0.1298 |

Saved risk is `round(max(venue_risk, adjusted_service_risk), 4)`. The same subtraction applies to both members of test 4, so it does not create their small within-pair difference. It does affect comparisons of absolute saved risk across dates. Test 0's venue risk of 0.4254 masks the difference in its service scores entirely.

Reviewed paths: [liveness scoring](../../module3-face-recognition/app/liveness.py), [configuration](../../module3-face-recognition/app/config.py), [embedding](../../module3-face-recognition/app/embedding.py), [template comparison](../../module3-face-recognition/app/template.py), [risk](../../module3-face-recognition/app/risk.py), [backend integration](../../module2-backend/app/main.py), [device adjustment](../../module2-backend/app/device_binding.py), [camera capture](../../module1-frontend/features/camera/useCamera.ts), and [dashboard score mapping](../../module4-observability/src/lib/attendance.ts). The dashboard maps API scores for display; it does not calculate biometric scores.

## Verification, limits and follow-up

Checks performed during this investigation:

- Existing `new-tests/test_liveness_thresholds.py`: **35 passed**, two dependency deprecation warnings. Ran in a disposable network-disabled container with the repository mounted read-only; no live database or attendance endpoints were used.
- Reconstructed **all eight recorded captures under both historical and current liveness implementations**, stubbing only model/component extraction with the recorded scalars. Historical/pre-gate scores agree within 0.000003 because reports round component measurements. All recorded liveness decisions agree. Under the old 0.60 policy all four replays pass; under current policy replays 0/1/2 fail and replay 4 passes. All four controls pass both policies.
- Recalculated all eight Module 3 risks and their complete weighted contributions using the real current risk function: exact agreement. Backend-adjusted risk and saved maximum-risk formulas also agree for all eight captures.
- Compared Git history, historical deployed hashes, current local hashes, current deployed hashes and the pre-/post-policy function ASTs. Current service settings independently read as liveness/depth/mesh **0.85/0.80/0.80**, identity **0.70**, Hamming fraction **0.158203**, SimHash seed **3099**.
- Verified the single-photo route and identity helper are unchanged since the policy commit. A preservation manifest confirms **331 existing source, documentation, test and report files remain byte-identical**. Repository and new-report whitespace checks pass.

Scalar reconstruction validates the calculation, not MediaPipe's historical output from unavailable pixels. Historical source/policy evidence is stronger than historical binary-environment evidence. This investigation does not estimate replay acceptance rates from one pair per location.

A useful follow-up is repeated paired captures under one fixed deployed build, with the same source photograph and displayed image scale, recording lighting, brightness, framing, distance and capture order. Preserve pre-gate values separately from returned scores, and record effective configuration plus dependency/model digests. This would distinguish repeatable condition effects from capture-to-capture variation. No additional trial or change to recognition policy is performed here.

Specification gaps: `docs/API-SPECIFICATION.md` and `docs/SECURITY-REQUIREMENTS.md` still describe a 0.60 liveness cutoff; the existing threshold-implementation record documents approval for 0.85 and 0.80 gates. The screen-replay rejection target was not met in tests 0, 1 or 4. These tests also lack full capture-condition and runtime-binary provenance needed to isolate location effects. `docs/` remains read-only.

Files changed: only this new investigation report. Existing source, test scripts, historical reports, attendance, enrollment, consent, device trust and running service configuration are preserved.

Endpoints: no endpoint implemented or invoked for attendance. Existing paths traced are backend `POST /api/v1/checkins/` and internal `POST /liveness/check`, `POST /face/verify`, `POST /risk/assess`. Current deployed verification reads only source hashes, safe settings and package versions through the local container runtime.
