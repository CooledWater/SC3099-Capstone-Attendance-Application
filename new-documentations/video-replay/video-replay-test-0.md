# Phone video replay test 0 — 30 October 2026

State: **complete. Both participant-confirmed presentations passed motion/liveness/identity. The phone-video replay was falsely accepted by biometric verification. Both attendance records saved as flagged for `device_unknown`; no approved-attendance replay was demonstrated. Diagnostics are disabled in both services, both allowlists are empty, and health is verified.**

## Scope and safeguards

Participant `wcstudent1@example.com`, actively enrolled in SC4000, uses existing face enrollment and camera/geolocation consent. The participant performs and confirms both physical presentations. The operator does not submit attendance, replay images/video into APIs, alter face enrollment, consent, device trust, location, recognition algorithms, thresholds or existing attendance/audit records. Only session-scoped allowlisted scalar diagnostics are collected; no raw captures, base64 payloads, landmarks, templates, credentials or unfiltered Docker logs are saved.

## Matched sessions

Venue **LT26**, catalogue coordinates **1.3434326, 103.6815837**. Both sessions have a 100 m geofence radius, risk threshold 0.50, motion required, passive liveness required and enrolled-face matching required. Scheduled and check-in windows both run from **2026-10-30T10:01:04.806956+08:00** to **2026-10-30T12:01:04.806956+08:00**, exactly two hours. Both session creations returned HTTP 201; authenticated student readback verified matched policy/venue settings and empty attendance.

| Presentation | Session name | Session ID |
| --- | --- | --- |
| real_face_control | Video replay R0 CONTROL real face (30 Oct 10:01 SGT) | `9d30108b-2513-4d64-8184-c60fc6e27b3b` |
| phone_video | Video replay R0 TEST phone video (30 Oct 10:01 SGT) | `f30d828b-6bb4-446a-8f80-876553dd56f0` |

## Baseline and known conditions

Both rebuilt services initially returned health HTTP 200, diagnostics disabled and empty allowlists. All 11 deployed backend/face-service source hashes match local source. Running thresholds: liveness **0.85**, depth **0.80**, mesh **0.80**, identity **0.70**, risk **0.50**. Existing `STRICT_SECURITY_MODE=false` is unchanged. Participant account/enrollment/face/consent flags are enabled; no template or password was retrieved. Before-run device metadata shows one active, untrusted device. Device approval is not changed for this trial; even successful biometric verification can save attendance as flagged because of device policy. Interpret biometric acceptance and final attendance independently.

Focused diagnostics and monitor preflight: **26 passed**, isolated container with temporary SQLite and no network access. No attendance-producing regression suite targets the running application. Existing documentation, historical reports and diagnostic scripts are covered by a temporary SHA-256 preservation manifest.

Participant reports a **bright screen**, display distance **around 10 cm**, and a **visible phone border** for the replay. Display-phone model, capture device/browser, clip duration/frame rate/resolution, numeric brightness, lighting, reflections, playback speed and differences between the two captures remain **unknown**. Both presentations are participant-confirmed in chat; the operator inspected no capture. Session labels alone do not prove what the camera saw. No video, screenshots of captures, HAR exports, credentials or templates are attached.

## Verified real-face control

The participant confirmed in chat that the real-face control was completed. Challenge `b9ff3931-ee92-406a-adbd-75696f0d3510` passed server motion verification with **two complete blinks**, 31 processed frames over **2,863 ms**, and six sampled identity checks. At control readback its metadata was consumed; later issuance pruned expired challenge metadata through the existing lifecycle, while diagnostic, attendance and audit records remain preserved. All seven diagnostic stages correlate by challenge/session: issuance, verification start, sequence response, verified result, attendance attempt, decision and commit.

| Measurement | First passive frame | Last passive frame |
| --- | --- | --- |
| Frame index / relative timestamp | 0 / 55 ms | 30 / 2,918 ms |
| Depth score / threshold | 0.99583 / 0.80, passed | 0.99578 / 0.80, passed |
| Mesh score / threshold | 0.93090 / 0.80, passed | 0.93148 / 0.80, passed |
| Texture / color | 0.99379 / 1.00000 | 0.99335 / 1.00000 |
| Weighted component score | 0.979922 | 0.979941 |
| Presentation integrity | 0.985378 | 0.984340 |
| Periodic-artifact penalty | 0.02437 | 0.02610 |
| Liveness before gates / final | 0.965594 / 0.965594 | 0.964595 / 0.964595 |
| Liveness threshold / result | 0.85 / passed | 0.85 / passed |

Both endpoint frames passed the existing geometry gates and final cutoff. Sequence liveness is the lower endpoint score, **0.964595**; sampled identity's minimum score is **0.8592591481**, passing the 0.70 threshold. The stop reason is `passed`. These are model scores, not calibrated probabilities or physical depth measurements.

Saved check-in `ad3b7526-f4ba-43bc-89ad-cdb0f8c0c24e` belongs to the intended student and control session, checked in at **10:04:15.132667 SGT**. Authenticated my-checkins and detail API readback plus a scalar-only database projection independently confirm **flagged**, liveness true/0.964595, identity true/0.8592591481 and risk **0.3126**. The summary endpoint does not expose the biometric scores; detail and database values agree. Preserved audit events are `checkin_attempted` (`c0a880b2-d150-4e1b-86b4-5969a7751ed8`) and `checkin_flagged` (`06695b95-1b99-4bb2-92e1-f342dd614ac6`). This is committed attendance, corroborated beyond a calculated decision.

The saved risk factor is **`device_unknown`**, severity medium, weight 0.20. The motion path initially derives risk `max(1-0.964595, 1-0.8592591481) ≈ 0.1407408519`; device policy applies `0.8 × 0.1407408519 + 0.20 ≈ 0.3125926816`. Venue risk is 0.0738 at 14.76 m from LT26 (100 m radius; reported location accuracy 40 m), producing saved risk `round(max(0.0738, 0.3125926816), 4) = 0.3126`, below 0.50. Device policy independently flags the attendance. The genuine control therefore passed the biometric comparison while its final attendance remained flagged. Device trust is unchanged.

The diagnostic `decision.reason` uses the generic value `risk_threshold` for this flagged status even though the numeric risk is below the cutoff. Saved risk factors establish the device cause; the reason enum alone should not be interpreted as a threshold exceedance. This existing diagnostic limitation is recorded without modifying source or decision logic. Both physical presentations are now participant-confirmed in chat.

At control verification time, backend health was HTTP 200 and diagnostics remained enabled for exactly the two trial sessions. The monitor was still running and the phone-video session was independently confirmed active until 12:01:04 SGT, with no motion challenge or saved attendance at that point. Its subsequently completed result follows.

## Verified phone-video replay

The participant confirmed in chat that the video replay was completed. The completed replay challenge is `3805efd4-6037-4082-95f4-cec5867ca905`: **two complete blinks**, 60 processed frames over **5,557 ms**, ten sampled identity checks, and stop reason **`passed`**. All seven diagnostic stages correlate through this challenge and the phone-video session. An earlier challenge, `1e0ca20d-7614-4e25-9c9f-fa53d58f4898`, was issued at 10:09:20 SGT and then superseded by the completed challenge issued at 10:09:36 SGT. Only issuance was observed for the earlier challenge; it has no measured verification outcome and is not counted as a rejection or another completed replay trial.

| Measurement | First replay frame | Last replay frame |
| --- | --- | --- |
| Frame index / relative timestamp | 0 / 21 ms | 59 / 5,578 ms |
| Depth score / threshold | 0.99974 / 0.80, passed | 0.98950 / 0.80, passed |
| Mesh score / threshold | 0.94122 / 0.80, passed | 0.92032 / 0.80, passed |
| Texture / color | 0.99631 / 1.00000 | 0.97162 / 1.00000 |
| Weighted component score | 0.984303 | 0.969837 |
| Presentation integrity | 0.991828 | 0.933226 |
| Periodic-artifact penalty | 0.01362 | 0.11129 |
| Liveness before gates / final | 0.976259 / 0.976259 | 0.905077 / 0.905077 |
| Liveness threshold / result | 0.85 / passed | 0.85 / passed |

The first-frame weighted score multiplied by presentation integrity gives approximately `0.984303 × 0.991828 = 0.976259`; the last frame gives approximately `0.969837 × 0.933226 = 0.905077`. Passive challenge integrity is 1.0 in both endpoint assessments. Both depth/mesh gates passed, so neither score was zeroed. Sequence liveness is the lower endpoint score, **0.905077**, above 0.85. Sampled identity's minimum score is **0.8666665613**, above 0.70. The fixed two-blink condition also passed. The first replay frame scored higher than the control's first frame on depth, mesh and final liveness. These inferred cues did not distinguish the participant-reported screen presentation in this observation.

The completed replay proof is consumed. Saved check-in `e8b4800e-dfed-4dc2-b807-aad7f0b2bc7f`, checked in at **10:09:58.826996 SGT**, belongs to the intended participant and phone-video session. Authenticated my-checkins/detail reads plus scalar-only database projection independently confirm **flagged**, liveness true/0.905077, identity true/0.8666665613, and risk **0.3067**. Preserved audit events are `checkin_attempted` (`012ba73d-0b37-468e-a2e4-ce8b7196aee5`) and `checkin_flagged` (`bd49a142-9a27-41de-921d-77155b5ee46b`). The collector recorded attendance commitment at **10:10:03 SGT**. Saved risk factors contain `device_unknown`, severity medium, weight 0.20, matching the control's device flag.

The motion-derived risk before device policy is `max(1-0.905077, 1-0.8666665613) ≈ 0.1333334387`; the device adjustment gives `0.8 × 0.1333334387 + 0.20 ≈ 0.3066667509`. Venue risk is 0.0738 at 14.75 m from LT26, within the 100 m radius, with reported accuracy 40 m. Saved risk is `round(max(0.0738, 0.3066667509), 4) = 0.3067`, below 0.50. Device policy independently flags attendance. Its slightly lower risk than the control reflects the identity-derived term dominating both motion risk calculations, despite lower replay liveness. The diagnostic `module3_risk_score` field here contains the motion-derived risk after backend device adjustment; the motion flow does not call `/risk/assess` for this calculation.

## Comparison and observed conclusion

| Measurement | Real-face control | Phone-video replay |
| --- | --- | --- |
| Completed server verification | passed | passed |
| Complete blink count | 2 | 2 |
| Captured frames / span | 31 / 2.863 s | 60 / 5.557 s |
| First / last depth scores | 0.99583 / 0.99578 | 0.99974 / 0.98950 |
| First / last mesh scores | 0.93090 / 0.93148 | 0.94122 / 0.92032 |
| Sequence liveness / threshold | 0.964595 / 0.85 | 0.905077 / 0.85 |
| Minimum sampled identity / threshold | 0.8592591481 / 0.70 | 0.8666665613 / 0.70 |
| Saved risk / threshold | 0.3126 / 0.50 | 0.3067 / 0.50 |
| Saved attendance / risk factor | flagged / device_unknown | flagged / device_unknown |

**Observed conclusion:** the participant-reported phone-video replay was accepted by motion, passive-liveness and identity verification in this trial. This is an observed biometric replay false acceptance. The screen-replay rejection target was not met for this observation. Attendance committed as flagged for device policy, so approved-attendance replay success was not demonstrated. The device flag does not establish successful replay detection.

The replay's last-frame periodic-artifact penalty increased to 0.11129 from the control's 0.02610, reducing its presentation integrity and liveness, while depth and mesh stayed above their gates. The returned values explain the accepted decision under the current policy; they do not establish recording freshness or physical depth. A bright screen, around 10 cm distance and visible border are participant-reported. The logs do not establish whether the border was analyzed. This is one completed phone-video observation from one enrolled participant; it does not establish a population attack-success rate or general replay resistance. The earlier issuance-only challenge has an unknown outcome. No thresholds or algorithms were adjusted after seeing these results.

## Completion and cleanup

After both attendance commitments, the existing collector exited successfully at **10:10:05 SGT** and recreated only backend and face-recognition with diagnostics disabled and empty allowlists. The monitor is no longer running. Independent runtime checks confirmed both health endpoints HTTP **200**, `CHECKIN_DIAGNOSTICS_ENABLED=false` in both services, empty `CHECKIN_DIAGNOSTIC_SESSION_IDS` in both services, unchanged `STRICT_SECURITY_MODE=false`, and unchanged recognition thresholds **0.85 / 0.80 / 0.80 / 0.70 / 0.50**.

All 11 deployed backend/face-service source hashes still match the pre-run/local sources. All 19 protected documentation/script hashes match their pre-run values. Active participant/enrollment, face-enrollment/reference-presence flags, camera/location consents and the single active untrusted device count are unchanged. No biometric template was retrieved. Both saved attendance records and their audit events were independently read after cleanup and preserved. Both sessions retain their original two-hour schedule; no attendance or audit record was edited or deleted.

Checks/results: 26 isolated diagnostic/monitor tests passed before activation; both session creations returned HTTP 201; policy, venue, empty-attendance, active-session and exact-scope preflight checks passed; seven correlated diagnostic stages per completed presentation plus one earlier issuance-only event were preserved; authenticated API, scalar database and audit readbacks agree; disabled diagnostics, empty allowlists, health, source/settings preservation and protected-file checks passed. The 15 sanitized event records remain unchanged. No further attendance-producing regression suite or mitigation implementation was run against the live application.

## Operation and interpretation

Configuration: `new-tests/phone-video-replay-run-20261030T020004Z.json`. Collector: existing `new-tests/monitor_phone_replay.py --mode video`, with a 125-minute safety timeout. Before captures, diagnostics were enabled for exactly the two session IDs in both services and the collector emitted `MONITOR_READY`. Independent preflight checks verified both health endpoints HTTP 200, exact matching allowlists, all 11 deployed source hashes, both sessions active/visible to the authenticated participant, required motion/liveness/identity and empty attendance. The collector preserved the narrative and updated only its delimited observation section. It has now finished; independent cleanup/health/readback verification is complete. Diagnostics are disabled and both allowlists are empty.

Both presentations are complete and verified above. The instructed replay method was to pause the phone clip on its initial eyes-open frame, centre the displayed face, start the challenge and immediately play at normal speed, keeping the real face outside the camera view. Capture is bounded to eight seconds. The participant confirmed completion of the phone-video trial; unreported setup details remain unknown.

First/last-frame measurements appear only when those checks ran. Early failure can leave the last frame not evaluated, and a zero server blink count can reflect early rejection before the recorded blinks were processed. Verification success is distinct from saved attendance. Unavailable/invalid service responses or expiry are inconclusive, not biometric rejection. A device/geofence block is separate from replay detection.

## Endpoints and specification gaps

Reused setup/readback endpoints: `POST /api/v1/sessions/`, `GET /api/v1/sessions/{id}`, `GET /api/v1/checkins/my-checkins`, `GET /api/v1/sessions/active` and both services' `GET /health`. Participant-only submission uses `POST /api/v1/motion/challenges`, `POST /api/v1/motion/challenges/{id}/verify`, `POST /api/v1/checkins/` and internal `POST /liveness/sequence`. No endpoint or recognition feature is implemented in this run.

Existing gaps: session creation uses `name` while the older documentation example says `session_name`; the older 0.60 liveness example differs from the previously approved 0.85/0.80/0.80 policy. A fixed two-blink challenge does not establish recording freshness, and this completed screen presentation passed biometric verification. The diagnostic decision reason uses `risk_threshold` for below-threshold device-flagged attendance; saved risk factors identify the actual device cause. Browser-only failures are participant-reported and may produce no scoped verification event. No code/docs change is proposed to resolve these gaps during this trial.

## Files changed

Added this report and `new-tests/phone-video-replay-run-20261030T020004Z.json` only. Existing source, docs and reports are preserved. Test sessions and their normal audit records are created through the existing API.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both presentations confirmed by participant; both saved attendance and audit records independently verified; diagnostics disabled and empty allowlists independently verified in both services**.

Updated: 2026-10-30T10:10:05+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / b9ff3931-ee92-406a-adbd-75696f0d3510

Server accepted the motion sequence; saved attendance status: flagged. Participant confirmed the real-face presentation in chat.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates |
| --- | --- | --- | --- | --- | --- |
| first_frame | yes | 0.99583 | 0.9309 | 0.965594 | True / True |
| last_frame | yes | 0.99578 | 0.93148 | 0.964595 | True / True |

Sequence stop reason: passed.

```json
[
  {
    "timestamp": "2026-10-30T02:03:54.138006+00:00",
    "diagnostic_id": "8f684d60-9c3c-4fa6-81fc-0c3dba94df92",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  },
  {
    "timestamp": "2026-10-30T02:04:01.512995+00:00",
    "diagnostic_id": "8ad90835-bf74-4748-a340-aca54fc8663f",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  },
  {
    "timestamp": "2026-10-30T02:04:05.246732+00:00",
    "diagnostic_id": "8ad90835-bf74-4748-a340-aca54fc8663f",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.964595,
      "face_match_score": 0.8592591480566107,
      "diagnostics": {
        "frame_count": 31,
        "processed_frames": 31,
        "duration_ms": 2863,
        "last_frame_index": 30,
        "last_timestamp_ms": 2918,
        "identity_checks": 6,
        "face_match_threshold": 0.7,
        "liveness_threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "ear_closed_threshold": 0.19,
        "ear_open_threshold": 0.23,
        "min_closure_ms": 40,
        "max_closure_ms": 700,
        "first_frame": {
          "evaluated": true,
          "frame_index": 0,
          "timestamp_ms": 55,
          "liveness_passed": true,
          "liveness_score": 0.965594,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.91465,
            "depth_score": 0.99583,
            "mesh_plausibility_score": 0.9309,
            "texture_analysis_score": 0.99379,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.979922,
            "presentation_integrity_score": 0.985378,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "depth_threshold": 0.8,
            "mesh_threshold": 0.8,
            "pre_gate_liveness_score": 0.965594,
            "face_mesh_complete": true,
            "depth_detected": true,
            "depth_passed": true,
            "mesh_passed": true,
            "weighted_contributions": {
              "depth": 0.29875,
              "mesh": 0.232725,
              "texture": 0.248447,
              "color": 0.2
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.985378,
              "texture_diversity": 0.996582,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.02437
            }
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 30,
          "timestamp_ms": 2918,
          "liveness_passed": true,
          "liveness_score": 0.964595,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.924,
            "depth_score": 0.99578,
            "mesh_plausibility_score": 0.93148,
            "texture_analysis_score": 0.99335,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.979941,
            "presentation_integrity_score": 0.98434,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "depth_threshold": 0.8,
            "mesh_threshold": 0.8,
            "pre_gate_liveness_score": 0.964595,
            "face_mesh_complete": true,
            "depth_detected": true,
            "depth_passed": true,
            "mesh_passed": true,
            "weighted_contributions": {
              "depth": 0.298735,
              "mesh": 0.232869,
              "texture": 0.248336,
              "color": 0.2
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.98434,
              "texture_diversity": 0.99634,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.0261
            }
          }
        },
        "reason": "passed"
      },
      "outcome": "received",
      "http_status": 200
    },
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  },
  {
    "timestamp": "2026-10-30T02:04:05.917418+00:00",
    "diagnostic_id": "8ad90835-bf74-4748-a340-aca54fc8663f",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.964595,
      "face_match_score": 0.8592591480566107
    },
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  },
  {
    "timestamp": "2026-10-30T02:04:14.212952+00:00",
    "diagnostic_id": "5e0e91d7-34a8-4955-9556-fcd621eb4df9",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  },
  {
    "timestamp": "2026-10-30T02:04:18.716213+00:00",
    "diagnostic_id": "5e0e91d7-34a8-4955-9556-fcd621eb4df9",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "decision",
    "values": {
      "checkin_id": "ad3b7526-f4ba-43bc-89ad-cdb0f8c0c24e",
      "status": "flagged",
      "risk_score": 0.3126,
      "venue_risk_score": 0.0738,
      "module3_risk_score": 0.3125926815547114,
      "effective_threshold": 0.5,
      "distance_meters": 14.76,
      "radius_meters": 100.0,
      "accuracy_meters": 40.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.964595,
      "face_match_passed": true,
      "face_match_score": 0.8592591480566107,
      "reason": "risk_threshold"
    },
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  },
  {
    "timestamp": "2026-10-30T02:04:19.855640+00:00",
    "diagnostic_id": "5e0e91d7-34a8-4955-9556-fcd621eb4df9",
    "session_id": "9d30108b-2513-4d64-8184-c60fc6e27b3b",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "ad3b7526-f4ba-43bc-89ad-cdb0f8c0c24e",
      "status": "flagged",
      "risk_score": 0.3126
    },
    "challenge_id": "b9ff3931-ee92-406a-adbd-75696f0d3510"
  }
]
```

### phone_video / 1e0ca20d-7614-4e25-9c9f-fa53d58f4898

No completed server motion verification recorded; browser-only capture is not a server result.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates |
| --- | --- | --- | --- | --- | --- |
| first_frame | unknown | — | — | — | — |
| last_frame | unknown | — | — | — | — |

Sequence stop reason: unknown.

```json
[
  {
    "timestamp": "2026-10-30T02:09:20.349437+00:00",
    "diagnostic_id": "3235bc1f-f5e5-4a5e-a9db-437d5bee49c1",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "1e0ca20d-7614-4e25-9c9f-fa53d58f4898"
  }
]
```

### phone_video / 3805efd4-6037-4082-95f4-cec5867ca905

Server accepted the motion sequence; saved attendance status: flagged. Participant confirmed the phone-video presentation in chat.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates |
| --- | --- | --- | --- | --- | --- |
| first_frame | yes | 0.99974 | 0.94122 | 0.976259 | True / True |
| last_frame | yes | 0.9895 | 0.92032 | 0.905077 | True / True |

Sequence stop reason: passed.

```json
[
  {
    "timestamp": "2026-10-30T02:09:36.237508+00:00",
    "diagnostic_id": "475bdb2f-dc6e-4e4b-a155-36fc1ae6b775",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  },
  {
    "timestamp": "2026-10-30T02:09:45.964980+00:00",
    "diagnostic_id": "7671cbee-44a3-4fde-bf8c-9fda46e26e55",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  },
  {
    "timestamp": "2026-10-30T02:09:49.528780+00:00",
    "diagnostic_id": "7671cbee-44a3-4fde-bf8c-9fda46e26e55",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.905077,
      "face_match_score": 0.8666665613167892,
      "diagnostics": {
        "frame_count": 60,
        "processed_frames": 60,
        "duration_ms": 5557,
        "last_frame_index": 59,
        "last_timestamp_ms": 5578,
        "identity_checks": 10,
        "face_match_threshold": 0.7,
        "liveness_threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "ear_closed_threshold": 0.19,
        "ear_open_threshold": 0.23,
        "min_closure_ms": 40,
        "max_closure_ms": 700,
        "first_frame": {
          "evaluated": true,
          "frame_index": 0,
          "timestamp_ms": 21,
          "liveness_passed": true,
          "liveness_score": 0.976259,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.94677,
            "depth_score": 0.99974,
            "mesh_plausibility_score": 0.94122,
            "texture_analysis_score": 0.99631,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.984303,
            "presentation_integrity_score": 0.991828,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "depth_threshold": 0.8,
            "mesh_threshold": 0.8,
            "pre_gate_liveness_score": 0.976259,
            "face_mesh_complete": true,
            "depth_detected": true,
            "depth_passed": true,
            "mesh_passed": true,
            "weighted_contributions": {
              "depth": 0.299921,
              "mesh": 0.235305,
              "texture": 0.249076,
              "color": 0.2
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.991828,
              "texture_diversity": 0.997968,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.01362
            }
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 59,
          "timestamp_ms": 5578,
          "liveness_passed": true,
          "liveness_score": 0.905077,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.92313,
            "depth_score": 0.9895,
            "mesh_plausibility_score": 0.92032,
            "texture_analysis_score": 0.97162,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.969837,
            "presentation_integrity_score": 0.933226,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "depth_threshold": 0.8,
            "mesh_threshold": 0.8,
            "pre_gate_liveness_score": 0.905077,
            "face_mesh_complete": true,
            "depth_detected": true,
            "depth_passed": true,
            "mesh_passed": true,
            "weighted_contributions": {
              "depth": 0.296851,
              "mesh": 0.23008,
              "texture": 0.242905,
              "color": 0.2
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.933226,
              "texture_diversity": 0.984391,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.11129
            }
          }
        },
        "reason": "passed"
      },
      "outcome": "received",
      "http_status": 200
    },
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  },
  {
    "timestamp": "2026-10-30T02:09:50.055934+00:00",
    "diagnostic_id": "7671cbee-44a3-4fde-bf8c-9fda46e26e55",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.905077,
      "face_match_score": 0.8666665613167892
    },
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  },
  {
    "timestamp": "2026-10-30T02:09:58.040631+00:00",
    "diagnostic_id": "c6783914-6217-4fce-90b0-72b54feb37a1",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  },
  {
    "timestamp": "2026-10-30T02:10:01.959457+00:00",
    "diagnostic_id": "c6783914-6217-4fce-90b0-72b54feb37a1",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "decision",
    "values": {
      "checkin_id": "e8b4800e-dfed-4dc2-b807-aad7f0b2bc7f",
      "status": "flagged",
      "risk_score": 0.3067,
      "venue_risk_score": 0.0738,
      "module3_risk_score": 0.30666675094656864,
      "effective_threshold": 0.5,
      "distance_meters": 14.75,
      "radius_meters": 100.0,
      "accuracy_meters": 40.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.905077,
      "face_match_passed": true,
      "face_match_score": 0.8666665613167892,
      "reason": "risk_threshold"
    },
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  },
  {
    "timestamp": "2026-10-30T02:10:03.002061+00:00",
    "diagnostic_id": "c6783914-6217-4fce-90b0-72b54feb37a1",
    "session_id": "f30d828b-6bb4-446a-8f80-876553dd56f0",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "e8b4800e-dfed-4dc2-b807-aad7f0b2bc7f",
      "status": "flagged",
      "risk_score": 0.3067
    },
    "challenge_id": "3805efd4-6037-4082-95f4-cec5867ca905"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
