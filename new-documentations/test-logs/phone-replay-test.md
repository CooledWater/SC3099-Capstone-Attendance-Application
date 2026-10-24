# Phone display replay test

Prepared on 24 October 2026, Singapore time. **Both tests completed: the real-face control and participant-reported phone-screen presentation were approved. The phone presentation passed passive liveness. Diagnostics are disabled.**

## Purpose and method

Compare a live-face control with a static face photograph displayed on a second phone, captured through the normal single-photo student check-in flow. Both sessions use the existing recognition, passive-liveness and risk algorithms, without threshold changes. Diagnostic logging does not change API responses, database schema, service failure policy, or decision logic. No test attendance was submitted by the operator.

Account: `wcstudent1@example.com`, actively enrolled in SC4000, with an existing face enrollment and stored camera/location consent. The participant performs both captures and confirms which presentation was used. Session labels alone cannot establish the physical presentation.

## Matched session configuration

| Setting | Value |
| --- | --- |
| Venue | LT1A |
| Venue coordinates | 1.3472192106767371, 103.68029662241148 |
| Geofence radius | 100 m |
| Motion requirement | false: single photo, no two-blink challenge |
| Passive liveness required | true |
| Enrolled-face match required | true |
| Attendance risk threshold | 0.5 |
| Module 3 passive-liveness threshold | 0.6, read from running service |
| Module 3 face-match threshold | 0.7, read from running service |
| Window (SGT, 24 October 2026) | 11:43:54–13:43:24 |
| Strict security mode | false, unchanged from the existing local configuration |

| Assigned presentation | Session name | Session ID |
| --- | --- | --- |
| Real-face control | Phone replay CONTROL real face (24 Oct 11:43 SGT) | `5a257139-7c6b-4c04-9a3d-e58267c33d74` |
| Phone-screen presentation | Phone replay TEST phone display (24 Oct 11:43 SGT) | `7b7c2ec3-a22f-43dc-9220-6b256e997c4e` |

Separate sessions preserve the one-check-in-per-student rule. Browser GPS is participant-supplied and is not independently attested; instrumentation substitutes no image, location, biometric template, or consent setting.

## Participant observations

The participant confirmed in chat that the real-face control was submitted, followed by the phone replay test. Both saved check-ins were independently read through the authenticated API and confirmed to belong to `wcstudent1@example.com` in their assigned sessions. Physical presentations are participant-reported; the operator did not view either capture.

Check-in device/browser, display phone, image source, approximate screen brightness and camera distance, lighting, screen borders/reflections, and participant-visible UI outcome have not yet been provided. These remain unknown; no capture images are available to the operator. Do not attach images, video, HAR exports, credentials, or biometric templates.

## Verified control result

| Measurement | Real-face control |
| --- | --- |
| Checked in (SGT, 24 October 2026) | 11:48:43 |
| Check-in ID | `1463a713-4958-4642-b64a-5bb01d862746` |
| Diagnostic ID | `eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1` |
| Attendance committed/status | yes / approved |
| Passive liveness | pass: 0.978987, threshold 0.6 |
| Face match | pass: 0.881481387837146, threshold 0.7 |
| Module 3 risk | 0.224883 |
| Venue risk | 0.4254 |
| Final risk | `max(0.4254, 0.224883) = 0.4254`, below threshold 0.5 |
| Distance / GPS accuracy | 85.08 m / 35 m |

Control liveness contributions: depth 0.298232 + mesh 0.230755 + texture 0.25 + color 0.2 = 0.978987. Presentation and challenge integrity factors were both 1.0. The periodic-artifact penalty was 0.0. Module 3 risk contributions were liveness 0.005253, face match 0.02963, device 0.1, network 0.075 and geolocation 0.015, summing to 0.224883. Device/network contributions do not independently prove an attack; the attendance photo path does not submit device/network attestation signals to Module 3.

The real-face control passed. Venue distance dominated its final risk; the comparison below separates that contribution from passive liveness and identity matching.

## Phone-screen result and comparison

The participant-reported phone presentation was **accepted**: passive liveness passed, the enrolled identity matched, and attendance committed as approved. The screen-replay anti-spoofing target in `docs/API-SPECIFICATION.md` (Anti-Spoofing Targets under `/liveness/check`) was not met in this observed trial. Both biometric services returned valid results, so this acceptance was **not** caused by the existing unavailable-service fallback.

| Measurement | Real-face control | Phone-screen presentation |
| --- | --- | --- |
| Checked in (SGT, 24 October 2026) | 11:48:43 | 11:51:56 |
| Check-in ID | `1463a713-4958-4642-b64a-5bb01d862746` | `37f9f776-bc92-439b-b416-b97fb9eba38c` |
| Diagnostic ID | `eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1` | `3d4c8a17-40b8-42cb-b492-edb044aef956` |
| Attendance committed/status | yes / approved | yes / approved |
| Liveness (threshold 0.6) | 0.978987 / pass | 0.822759 / pass |
| Face match (threshold 0.7) | 0.881481387837146 / pass | 0.896296214357503 / pass |
| Depth component score | 0.99411 | 0.62945 |
| Mesh plausibility score | 0.92302 | 0.75188 |
| Texture component score | 1.0 | 0.99816 |
| Color component score | 1.0 | 1.0 |
| Weighted component score | 0.978987 | 0.826344 |
| Presentation integrity factor | 1.0 | 0.995662 |
| Challenge integrity factor (passive) | 1.0 | 1.0 |
| Periodic-artifact penalty | 0.0 | 0.00723 |
| Inferred depth detected / quality | true / good | true / good |
| Module 3 risk | 0.224883 | 0.260236 |
| Venue risk | 0.4254 | 0.4254 |
| Final risk (threshold 0.5) | 0.4254 | 0.4254 |
| Distance / reported GPS accuracy | 85.08 m / 35 m | 85.08 m / 35 m |

Phone liveness calculation, using the returned rounded diagnostics:

```text
Weighted components = 0.188836 depth + 0.187969 mesh + 0.249539 texture + 0.2 color
                    = 0.826344
Final liveness      ≈ 0.826344 × 0.995662 presentation × 1.0 challenge
                    = 0.822759 (returned score), above 0.6

Module 3 risk       = 0.044310 liveness + 0.025926 face match
                    + 0.100000 device + 0.075000 network + 0.015000 geolocation
                    = 0.260236
Attendance risk     = max(0.4254 venue, 0.260236 Module 3)
                    = 0.4254, below 0.5
```

Depth and mesh scores decreased for the phone presentation, but the inferred-depth check still reported depth as detected/good. Texture and color remained near their maximum scores, while the screen-periodicity penalty was small. The combined liveness score therefore remained above the pass threshold. Face matching recognized the enrolled identity; that match does not establish a live presentation. The equal final attendance scores reflect equal venue risk dominating both decisions, despite the different biometric scores.

This is one observed false acceptance of a participant-reported static phone-screen presentation. It establishes a failure for this trial, not a measured attack success rate across devices or people. Device/browser, displayed-photo provenance, brightness, distance, lighting, and screen/reflection conditions remain unknown. No recognition threshold or algorithm was modified in response to these observations.

## Completion and cleanup verification

The collector observed six correlated diagnostic stages for each session, including successful attendance commitment. It exited successfully after the second commit and recreated the backend with diagnostics disabled. An independent post-cleanup check confirmed `CHECKIN_DIAGNOSTICS_ENABLED=false`, an empty diagnostic session allowlist, backend health HTTP 200, and both saved approved records belonging to the intended account. Test attendance and audit records were preserved.

## Diagnostics and interpretation

The backend logs only explicitly allowlisted scalar fields, restricted to the two session IDs. Each attempt has a server-generated diagnostic ID. Captured stages are attempt start, Module 3 liveness/face-match/risk responses, backend decision, and successful attendance commitment. HTTP/server failures are distinct and include no arbitrary exception text. Full Docker logs are never saved to this report.

Passive liveness uses weighted depth/mesh/texture/color components (30/25/25/20 percent), followed by presentation/challenge integrity factors. Module 3 risk contributions and the backend's venue risk are captured separately. Final attendance risk is `max(venue risk, Module 3 risk)` when Module 3 risk is available. Geofence hard rejection and a performed liveness failure independently force rejection. A calculated decision is not proof that attendance committed.

The existing non-strict photo path can record attendance when Module 3 is unavailable. Such a capture is **inconclusive for replay detection**, even if attendance is approved. Distinguish a liveness pass from identity matching and from the final attendance result. A passing phone-screen capture is evidence for that specific presentation only; a rejected capture does not prove general replay resistance.

## Implementation validation

- Instrumentation privacy, session scoping, concurrent correlation, service outage, logging failure, API compatibility and failed-commit tests: **11 passed**.
- Monitor filtering, classification and report preservation tests: **3 passed**.
- Unchanged public suite against a disposable SQLite backend and the running Module 3 service: **102 passed, 1 skipped**.
- No files under `docs/` or existing public tests were modified.
- Rebuilt local backend health returned HTTP 200; both sessions were visible as active with photo mode and required liveness/face matching. Both had no student attendance before monitoring began.
- Running Module 3 `liveness.py` SHA-256: `9486ef646708e8d86ce41581a538091854e11e08c418759142704e0f6f1e655e`.
- Deployed backend `checkin_diagnostics.py` SHA-256: `b880cf1775e650dc8304424d229a0d05651da1e67d4c30db153fca028248bd7a`.

## Monitor operation and cleanup

Run configuration: `new-tests/phone-replay-run.json`. The dedicated Compose override is `new-tests/docker-compose.phone-replay.yml`; diagnostics are off by default and require an explicit session allowlist. The monitor updates only the delimited observation section, preserving participant notes above it. After both sessions commit, manual interruption, or its 45-minute timeout, it recreates only the backend with diagnostics disabled. Cleanup status appears in the monitor state below; failures require operator action.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both sessions committed; participant subsequently confirmed both submissions in chat; diagnostics disabled and independently verified**.

Updated: 2026-10-24T11:51:58+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-24T03:48:42.140057+00:00",
    "diagnostic_id": "eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1",
    "session_id": "5a257139-7c6b-4c04-9a3d-e58267c33d74",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-24T03:48:43.216510+00:00",
    "diagnostic_id": "eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1",
    "session_id": "5a257139-7c6b-4c04-9a3d-e58267c33d74",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.978987,
      "liveness_threshold": 0.6,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.92783,
        "depth_score": 0.99411,
        "mesh_plausibility_score": 0.92302,
        "texture_analysis_score": 1.0,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.978987,
        "presentation_integrity_score": 1.0,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.6,
        "face_mesh_complete": true,
        "depth_detected": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0008043,
        "relative_nose_depth": 0.05232,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.298232,
          "mesh": 0.230755,
          "texture": 0.25,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 1.0,
          "texture_diversity": 1.0,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 477.301,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 1.0,
          "fft_high_frequency_ratio": 0.20847,
          "fft_peak_concentration": 0.0628,
          "fft_peak_to_mean": 27.963,
          "periodic_artifact_penalty": 0.0,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.351,
          "lbp_peak_fraction": 0.07978
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.9198,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-24T03:48:43.338171+00:00",
    "diagnostic_id": "eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1",
    "session_id": "5a257139-7c6b-4c04-9a3d-e58267c33d74",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.8814813878371459,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-24T03:48:43.343237+00:00",
    "diagnostic_id": "eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1",
    "session_id": "5a257139-7c6b-4c04-9a3d-e58267c33d74",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.224883,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.005253,
        "face_match": 0.02963,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-24T03:48:43.343337+00:00",
    "diagnostic_id": "eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1",
    "session_id": "5a257139-7c6b-4c04-9a3d-e58267c33d74",
    "stage": "decision",
    "values": {
      "checkin_id": "1463a713-4958-4642-b64a-5bb01d862746",
      "status": "approved",
      "risk_score": 0.4254,
      "venue_risk_score": 0.4254,
      "module3_risk_score": 0.224883,
      "effective_threshold": 0.5,
      "distance_meters": 85.08,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.978987,
      "face_match_passed": true,
      "face_match_score": 0.8814813878371459,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-24T03:48:44.167367+00:00",
    "diagnostic_id": "eb6c300f-ec1e-4eb0-bb6f-5f2bcace16d1",
    "session_id": "5a257139-7c6b-4c04-9a3d-e58267c33d74",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "1463a713-4958-4642-b64a-5bb01d862746",
      "status": "approved",
      "risk_score": 0.4254
    }
  }
]
```

### phone_screen / 3d4c8a17-40b8-42cb-b492-edb044aef956

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-24T03:51:56.129974+00:00",
    "diagnostic_id": "3d4c8a17-40b8-42cb-b492-edb044aef956",
    "session_id": "7b7c2ec3-a22f-43dc-9220-6b256e997c4e",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-24T03:51:57.141679+00:00",
    "diagnostic_id": "3d4c8a17-40b8-42cb-b492-edb044aef956",
    "session_id": "7b7c2ec3-a22f-43dc-9220-6b256e997c4e",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.822759,
      "liveness_threshold": 0.6,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.9035,
        "depth_score": 0.62945,
        "mesh_plausibility_score": 0.75188,
        "texture_analysis_score": 0.99816,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.826344,
        "presentation_integrity_score": 0.995662,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.6,
        "face_mesh_complete": true,
        "depth_detected": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0003596,
        "relative_nose_depth": 0.03423,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.188836,
          "mesh": 0.187969,
          "texture": 0.249539,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.995662,
          "texture_diversity": 0.998987,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 411.583,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.99386,
          "fft_high_frequency_ratio": 0.11899,
          "fft_peak_concentration": 0.079,
          "fft_peak_to_mean": 40.74,
          "periodic_artifact_penalty": 0.00723,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.202,
          "lbp_peak_fraction": 0.05971
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.97656,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-24T03:51:57.249659+00:00",
    "diagnostic_id": "3d4c8a17-40b8-42cb-b492-edb044aef956",
    "session_id": "7b7c2ec3-a22f-43dc-9220-6b256e997c4e",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.8962962143575026,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-24T03:51:57.252632+00:00",
    "diagnostic_id": "3d4c8a17-40b8-42cb-b492-edb044aef956",
    "session_id": "7b7c2ec3-a22f-43dc-9220-6b256e997c4e",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.260236,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.04431,
        "face_match": 0.025926,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-24T03:51:57.252752+00:00",
    "diagnostic_id": "3d4c8a17-40b8-42cb-b492-edb044aef956",
    "session_id": "7b7c2ec3-a22f-43dc-9220-6b256e997c4e",
    "stage": "decision",
    "values": {
      "checkin_id": "37f9f776-bc92-439b-b416-b97fb9eba38c",
      "status": "approved",
      "risk_score": 0.4254,
      "venue_risk_score": 0.4254,
      "module3_risk_score": 0.260236,
      "effective_threshold": 0.5,
      "distance_meters": 85.08,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.822759,
      "face_match_passed": true,
      "face_match_score": 0.8962962143575026,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-24T03:51:58.284419+00:00",
    "diagnostic_id": "3d4c8a17-40b8-42cb-b492-edb044aef956",
    "session_id": "7b7c2ec3-a22f-43dc-9220-6b256e997c4e",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "37f9f776-bc92-439b-b416-b97fb9eba38c",
      "status": "approved",
      "risk_score": 0.4254
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->


## Prompt to start another test session
Run another phone-image replay test using the existing diagnostic instrumentation.

Use wcstudent1@example.com and LT1A coordinates:
(1.3472192106767371, 103.68029662241148), with a 100 m radius.

1. Review AGENTS.md and the existing instrumentation, monitor, and previous test report. Keep ./docs read-only.
2. Create two fresh, matching sessions in a course where the student is actively enrolled:
   - Real-face control.
   - Phone displaying a static photo of the enrolled face.
   Both must allow single-photo check-in, require passive liveness and face matching, and remain open for two hours.
3. Enable diagnostics only for these new session IDs. Rebuild/recreate the backend if necessary and verify the deployed instrumentation.
4. Start monitoring before asking me to submit anything. I will perform both captures manually; do not submit attendance or alter my enrollment, face template, consent, location, thresholds, or recognition algorithms.
5. Use a new run configuration and save the sanitized report to:
   ./new-documentations/test-logs/phone-image-replay-<YYYY-MM-DD-HHMM-SGT>.md
   Preserve all previous reports.
6. Tell me the session names and confirm monitoring is ready. Ask for device/browser, lighting, screen brightness, camera distance, and visible borders/reflections. Mark missing conditions as unknown.
7. After each submission, correlate diagnostics with the saved attendance record. Compare liveness components, presentation penalties, identity scores, Module 3 risk contributions, venue risk, final risk, and attendance status.
8. Distinguish unavailable checks from genuine passes and calculated decisions from committed attendance. Limit conclusions to the observed trial.
9. After both submissions—or if I stop the test—disable diagnostics, clear the allowlist, verify backend health, and finish the report. Preserve test attendance and audit records.

Never save raw images, video, base64 payloads, landmarks, biometric templates, credentials, or unfiltered Docker logs.

You may prepare the sessions, enable instrumentation, and monitor without further approval. Wait for my manual captures before reporting test outcomes.

Finish with files changed, endpoints reused, specification gaps, and checks/results.

## Files relevant to the diagnostics
| File | Purpose |
|---|---|
| [checkin_diagnostics.py](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/module2-backend/app/checkin_diagnostics.py) | Core logger: enable flag, session allowlist, attempt IDs, scalar-field filtering, and request context. |
| [face_service.py](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/module2-backend/app/face_service.py) | Captures sanitized liveness, face-match, and risk responses from Module 3. |
| [main.py](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/module2-backend/app/main.py) | Records the attendance decision and successful database commitment. |
| [docker-compose.phone-replay.yml](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/new-tests/docker-compose.phone-replay.yml) | Compose override for enabling diagnostics on selected sessions. |
| [monitor_phone_replay.py](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/new-tests/monitor_phone_replay.py) | Filters Docker logs, updates the report, and disables diagnostics afterward. |
| [phone-replay-run.json](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/new-tests/phone-replay-run.json) | Previous run’s session IDs, labels, settings, and monitoring start time. |
| [test_checkin_diagnostics.py](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/new-tests/test_checkin_diagnostics.py) | Tests privacy filtering, scoping, correlation, and failure handling. |
| [test_monitor_phone_replay.py](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/new-tests/test_monitor_phone_replay.py) | Tests log filtering, result classification, and report preservation. |
| [phone-replay-test.md](/Users/cheng/Documents/Codes/git/SC3099-Capstone-Attendance-Application/new-documentations/test-logs/phone-replay-test.md) | Completed report containing sanitized diagnostic events and analysis. |
