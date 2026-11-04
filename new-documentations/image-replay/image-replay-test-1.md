# Phone image replay test — 25 October 2026

State: **complete. Both the real-face control and participant-reported static phone-photo presentation committed as approved. The replay was falsely accepted in this observed trial. Diagnostics are disabled, the allowlist is empty, and backend health is verified.**

## Purpose and safeguards

Compare a manually submitted real-face control with a manually submitted static photograph of the enrolled face displayed on a phone, using `wcstudent1@example.com` in SC4000. Physical presentation is participant-reported; session labels cannot prove what the camera saw. Conclusions will be limited to this trial.

The participant selected **Test Venue 25 Oct** and supplied `1°16′54.1″N 103°50′44.3″E`, converted to latitude `1.2816944444444445`, longitude `103.84563888888889`. These coordinates configure only the two new sessions. The operator does not submit attendance or change enrollment, face enrollment/template, consent, participant location, recognition algorithms, or thresholds. Existing attendance and audit records are preserved.

Only allowlisted diagnostic scalars are collected. No raw images, video, image payloads, landmark arrays, biometric templates, credentials, or unfiltered Docker logs are saved. Authentication material used for authorized setup/readback stays in process memory.

## Matched session configuration

Both new lecture sessions were created through the existing API with identical two-hour scheduled and check-in intervals, venue coordinates, 100 m geofence radius, attendance risk threshold 0.5, single-photo mode (`require_motion_check=false`), passive liveness required, and face matching required. Both POSTs returned HTTP 201.

| Assigned presentation | Session name | Session ID |
| --- | --- | --- |
| Real-face control | Phone image replay CONTROL real face (25 Oct 12:11 SGT) | `76e90dc9-ac12-466d-8f38-252c561565ec` |
| Static photo displayed on phone | Phone image replay TEST static phone photo (25 Oct 12:11 SGT) | `3293c930-1938-4b88-ac4e-2730eb23b24c` |

Window on 25 October 2026: **12:11:35.870925–14:11:35.870925 SGT**, exactly two hours. Fresh run configuration: `new-tests/phone-image-replay-run-20261025T040935Z.json`. The previous run configuration is untouched.

Running service baseline: passive-liveness threshold 0.6, face-match threshold 0.7, Module 3 risk threshold 0.5. Existing `STRICT_SECURITY_MODE=false` is unchanged. Diagnostics were initially disabled with an empty session allowlist.

## Participant conditions

| Condition | Value |
| --- | --- |
| Capture device and browser | unknown |
| Display phone | unknown |
| Lighting | participant-reported dim lighting; differences between captures unknown |
| Display brightness | unknown |
| Camera-to-face / camera-to-screen distance | unknown |
| Visible screen borders and reflections | participant reports visible phone border; reflections unknown |
| Displayed-photo provenance | unknown |
| Real-face presentation confirmed by participant | yes, participant reported “Real face attendance taken.” |
| Static phone-photo presentation confirmed by participant | yes, participant reported “phone photo attendance taken.” |

## Results and correlation

The participant confirmed the real-face capture. All six diagnostic stages were collected for diagnostic ID `3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4`. Authenticated `my-checkins` and check-in-detail reads independently matched committed check-in `ad818480-60ca-4600-929e-90554c6923af` to the intended student and control session. The saved record is **approved**, checked in at **12:13:29.584943 SGT**. Preserved audit records include successful `checkin_attempted` and `checkin_approved` events for that same check-in ID. This is a committed attendance outcome, not merely a calculated decision.

| Measurement | Real-face control | Static phone-photo presentation |
| --- | --- | --- |
| Attendance saved / status | yes / approved | yes / approved |
| Passive liveness (threshold 0.6) | 0.907025 / pass | 0.841207 / pass |
| Identity match (threshold 0.7) | 0.881481387837146 / pass | 0.859259148056611 / pass |
| Depth component | 0.86414 | 0.74772 |
| Mesh plausibility component | 0.82673 | 0.77296 |
| Texture component | 0.9963 | 0.97718 |
| Color component | 1.0 | 0.99997 |
| Weighted liveness component score | 0.914996 | 0.861845 |
| Presentation integrity factor | 0.991288 | 0.976054 |
| Passive challenge integrity factor | 1.0 | 1.0 |
| Periodic-artifact penalty | 0.01452 | 0.03991 |
| Module 3 risk | 0.242874 | 0.264883 |
| Venue risk | 0.0209 | 0.0331 |
| Saved final risk (threshold 0.5) | 0.2429 | 0.2649 |
| Venue distance / reported GPS accuracy | 4.18 m / 35 m | 6.62 m / 35 m |

Control liveness weighted contributions: depth 0.259241 + mesh 0.206681 + texture 0.249074 + color 0.2 = 0.914996. Applying presentation factor 0.991288 and passive challenge factor 1.0 yields approximately 0.907025, above 0.6. Inferred depth was reported detected/good; this is an image-derived estimate, not a physical depth measurement. The passive factor does not establish that an active challenge was performed.

Control Module 3 risk contributions: liveness 0.023244 + face match 0.029630 + device 0.100000 + network 0.075000 + geolocation 0.015000 = 0.242874. The existing photo path supplies no device/network attestation signals to Module 3; their neutral contributions are not successful checks. All three biometric/risk service calls returned HTTP 200 and usable results. Final risk is `round(max(0.0209 venue, 0.242874 Module 3), 4) = 0.2429`, below 0.5.

The participant confirmed the phone-photo capture. All six diagnostic stages were collected for diagnostic ID `03b2b364-609a-4273-bdcb-1be601385893`. Authenticated `my-checkins` and check-in-detail reads independently matched committed check-in `2181e3bb-1f13-4dd4-b05b-811db07e8796` to the same intended student and the phone-photo session. The saved record is **approved**, checked in at **12:15:18.818550 SGT**. Successful `checkin_attempted` and `checkin_approved` audit records are preserved for that ID. Both saved records were checked again after diagnostic shutdown.

Phone-photo weighted liveness contributions were depth 0.224317, mesh 0.193240, texture 0.244294, and color 0.199993. Their displayed rounded sum is 0.861844, within 0.000001 of the returned weighted score 0.861845. Applying presentation factor 0.976054 and passive challenge factor 1.0 gives approximately 0.841207, above 0.6. Periodicity integrity was 0.976054, texture-diversity integrity 0.987447, and color-diversity integrity 0.999982. The periodic-artifact penalty increased from 0.01452 to 0.03991, but was insufficient to bring liveness below threshold. Inferred depth still reported detected/good; this does not establish physical depth.

| Module 3 weighted risk contribution | Real-face control | Phone-photo presentation |
| --- | --- | --- |
| Liveness | 0.023244 | 0.039698 |
| Face match | 0.029630 | 0.035185 |
| Device | 0.100000 | 0.100000 |
| Network | 0.075000 | 0.075000 |
| Geolocation | 0.015000 | 0.015000 |
| Total | 0.242874 | 0.264883 |

Phone-photo final risk is `round(max(0.0331 venue, 0.264883 Module 3), 4) = 0.2649`, below 0.5. Module 3 risk dominated both captures despite slightly different reported venue distances. Neither geofence hard rejection nor a performed liveness failure triggered rejection. Identity matching recognized the enrolled person but cannot distinguish a live face from a photograph of that person.

**Observed conclusion:** the screen-replay rejection target in `docs/API-SPECIFICATION.md` was not met in this trial. The participant-reported phone presentation passed passive liveness and identity matching, and attendance committed as approved. This was not an unavailable-service fallback: both attempts received HTTP 200 usable liveness, face-match, and Module 3 risk responses. Depth, mesh, and texture scores were lower for the phone presentation, but texture/color remained high and the presentation penalty was modest.

This is one observed false acceptance, not an attack success rate or a general claim about other people, phones, browsers, lighting, or display conditions. Dim lighting and a visible phone border were participant-reported; the operator did not inspect either image. Capture device/browser, display phone, brightness, distance, reflections, photo provenance, and differences in conditions remain unknown. A visible border reported by the participant does not establish that the recognition pipeline analyzed the border. Recognition thresholds and algorithms remain unchanged.

A `decision` event proves only that a decision was calculated. An `attendance_committed` event must be corroborated by a saved attendance record. Unavailable or unperformed checks are unknown, never genuine passes. Device/network neutral contributions do not prove attestation or network checks passed. Final risk uses the maximum of venue risk and available Module 3 risk, rounded by the backend; performed liveness failure and geofence hard rejection independently reject attendance.

## Validation and specification gaps

- Reviewed `AGENTS.md`, the existing diagnostics/monitor, the previous report, and relevant paths across all four modules. `docs/` remains read-only.
- Verified the intended account is active, actively enrolled in SC4000, face-enrolled, and already has camera/geolocation consent; no account settings were changed.
- Existing diagnostics and monitor regression tests: **14 passed** (59 deprecation warnings), using an isolated temporary SQLite database. Tests cover session scoping, scalar filtering, concurrency, outages, logging failures, calculated versus committed attendance, and report preservation.
- Backend and Module 3 health: **HTTP 200** before setup. Deployed backend diagnostic/call-path and Module 3 liveness/risk/embedding source hashes matched local files; no rebuild is needed for source deployment.
- Recreated only the backend with diagnostics enabled. Independently verified that its runtime allowlist contains exactly the two new session IDs and its deployed diagnostic hash remains unchanged. Backend health returned HTTP 200 after recreation. Authenticated session readback confirmed matched settings and zero existing check-ins for the intended student in both sessions.
- Existing monitor reported `MONITOR_READY` at 12:10:49 SGT, before the scheduled opening and before requesting participant submissions. It uses the new run configuration and this report, with a 125-minute safety timeout and automatic diagnostic cleanup. No attendance was submitted by the operator.
- Public active-session readback at 12:11:53 SGT independently confirmed both new sessions active. The monitor remained running without observed diagnostic submissions at that check.
- Existing limitation: non-strict single-photo check-in may save attendance when required biometric services are unavailable. Any such observation is inconclusive for replay detection. A matching enrolled identity does not prove liveness.
- Existing API example inconsistency: session creation shows `session_name`, while the deployed schema and existing clients/tests use `name`. Setup reuses the deployed `name` contract; no API code or documentation is changed.
- The screen-replay rejection target in `docs/API-SPECIFICATION.md` is the observed trial's comparison criterion, not an assumed guarantee.

## Deployment evidence

| File | Verified deployed SHA-256 |
| --- | --- |
| Backend `app/main.py` | `1bc9a170a1f0397144c29d584194cbd90cdc5e320fd50bae5ac3db2674eb2c5b` |
| Backend `app/checkin_diagnostics.py` | `b880cf1775e650dc8304424d229a0d05651da1e67d4c30db153fca028248bd7a` |
| Backend `app/face_service.py` | `5ee963de4cf7839e804103224158bf2a84991be83a323062fbcf5980925387d9` |
| Module 3 `app/liveness.py` | `9486ef646708e8d86ce41581a538091854e11e08c418759142704e0f6f1e655e` |
| Module 3 `app/risk.py` | `17f4af3b626c683b10c8960e32820c7cca84d4f176279f71dd08a2c983007842` |
| Module 3 `app/embedding.py` | `885d127ef09ad37a6e7b43aba9198e4ad177f04ba174ab419b0ddeef3559dff4` |

Before-run preservation hashes: all 11 files under `docs/` combined manifest SHA-256 `f85be89b66a632bb9d4c9d88409fc2b5d24bea35d6b054e40a4ffb470aa68454`; previous `phone-replay-test.md` SHA-256 `3ab68ff657bc375fad0c1c0682355d33c35df05ad51c86c10eb819ea57c900cd`. That previous report already had working-tree edits before this run and is preserved as found.

## Endpoints reused

`POST /api/v1/sessions/`; `GET /api/v1/enrollments/my-enrollments`; `GET /api/v1/sessions/{session_id}`; `GET /api/v1/sessions/active`; `GET /api/v1/checkins/my-checkins`; `GET /api/v1/checkins/{checkin_id}`; backend and Module 3 `GET /health`. Participant submissions use the existing `POST /api/v1/checkins/`, which invokes Module 3 `POST /liveness/check`, `POST /face/verify`, and `POST /risk/assess`. No endpoint is implemented.

## Cleanup

The monitor exited successfully after both commits and recreated only the backend with diagnostics disabled. Independent post-cleanup checks verified `CHECKIN_DIAGNOSTICS_ENABLED=false`, an empty `CHECKIN_DIAGNOSTIC_SESSION_IDS`, unchanged `STRICT_SECURITY_MODE=false`, backend health HTTP 200, and Module 3 health HTTP 200. The monitor is no longer running.

Both approved attendance records and their attempted/approved audit entries were independently read after shutdown and preserved. Active enrollment, active account, face-enrolled flag, and existing camera/geolocation consent remain unchanged. No face template was retrieved or changed. Running backend instrumentation/call-path hashes and Module 3 liveness/risk/embedding hashes still match the recorded baseline; Module 3 thresholds remain 0.6 liveness, 0.7 face match, and 0.5 risk.

All 11 files under `docs/` and the previous `phone-replay-test.md` match their before-run hashes. The previous run configuration and all previous reports were preserved. Test sessions retain their original two-hour schedules; no attendance or audit record was deleted or edited.

## Files changed and final checks

Added only `new-documentations/test-logs/phone-image-replay-.md` and `new-tests/phone-image-replay-run-20261025T040935Z.json`. No application code, recognition algorithms, thresholds, documentation under `docs/`, or existing reports were modified by this run. Existing working-tree changes from before the run remain untouched.

Checks: 14 isolated instrumentation/monitor tests passed; two session creations returned HTTP 201; authenticated settings/empty-attendance preflight and active-session visibility passed; six diagnostic stages per capture correlated to saved attendance and audit records; post-cleanup disabled diagnostics/empty allowlist and both service health checks passed; deployed source/threshold and documentation/previous-report preservation checks passed. No new feature was implemented, and no live public suite that would create unrelated attendance or alter enrollment was run.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both presentations confirmed by participant; both saved attendance and audit records independently verified; diagnostics disabled and empty allowlist independently verified**.

Updated: 2026-10-25T12:15:20+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / 3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-25T04:13:28.744628+00:00",
    "diagnostic_id": "3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4",
    "session_id": "76e90dc9-ac12-466d-8f38-252c561565ec",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-25T04:13:30.594933+00:00",
    "diagnostic_id": "3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4",
    "session_id": "76e90dc9-ac12-466d-8f38-252c561565ec",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.907025,
      "liveness_threshold": 0.6,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.92554,
        "depth_score": 0.86414,
        "mesh_plausibility_score": 0.82673,
        "texture_analysis_score": 0.9963,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.914996,
        "presentation_integrity_score": 0.991288,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.6,
        "face_mesh_complete": true,
        "depth_detected": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0005463,
        "relative_nose_depth": 0.04162,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.259241,
          "mesh": 0.206681,
          "texture": 0.249074,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.991288,
          "texture_diversity": 0.997963,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 185.436,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.98765,
          "fft_high_frequency_ratio": 0.20838,
          "fft_peak_concentration": 0.10614,
          "fft_peak_to_mean": 43.199,
          "periodic_artifact_penalty": 0.01452,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 5.833,
          "lbp_peak_fraction": 0.16615
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.95471,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T04:13:30.708441+00:00",
    "diagnostic_id": "3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4",
    "session_id": "76e90dc9-ac12-466d-8f38-252c561565ec",
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
    "timestamp": "2026-10-25T04:13:30.714501+00:00",
    "diagnostic_id": "3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4",
    "session_id": "76e90dc9-ac12-466d-8f38-252c561565ec",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.242874,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.023244,
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
    "timestamp": "2026-10-25T04:13:30.714574+00:00",
    "diagnostic_id": "3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4",
    "session_id": "76e90dc9-ac12-466d-8f38-252c561565ec",
    "stage": "decision",
    "values": {
      "checkin_id": "ad818480-60ca-4600-929e-90554c6923af",
      "status": "approved",
      "risk_score": 0.2429,
      "venue_risk_score": 0.0209,
      "module3_risk_score": 0.242874,
      "effective_threshold": 0.5,
      "distance_meters": 4.18,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.907025,
      "face_match_passed": true,
      "face_match_score": 0.8814813878371459,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-25T04:13:31.737031+00:00",
    "diagnostic_id": "3c54c7d7-8aac-4d6c-9b11-d4faaf8020e4",
    "session_id": "76e90dc9-ac12-466d-8f38-252c561565ec",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "ad818480-60ca-4600-929e-90554c6923af",
      "status": "approved",
      "risk_score": 0.2429
    }
  }
]
```

### phone_screen / 03b2b364-609a-4273-bdcb-1be601385893

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-25T04:15:17.485294+00:00",
    "diagnostic_id": "03b2b364-609a-4273-bdcb-1be601385893",
    "session_id": "3293c930-1938-4b88-ac4e-2730eb23b24c",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-25T04:15:18.950102+00:00",
    "diagnostic_id": "03b2b364-609a-4273-bdcb-1be601385893",
    "session_id": "3293c930-1938-4b88-ac4e-2730eb23b24c",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.841207,
      "liveness_threshold": 0.6,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.92963,
        "depth_score": 0.74772,
        "mesh_plausibility_score": 0.77296,
        "texture_analysis_score": 0.97718,
        "color_distribution_score": 0.99997,
        "weighted_component_score": 0.861845,
        "presentation_integrity_score": 0.976054,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.6,
        "face_mesh_complete": true,
        "depth_detected": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0004473,
        "relative_nose_depth": 0.03804,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.224317,
          "mesh": 0.19324,
          "texture": 0.244294,
          "color": 0.199993
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.976054,
          "texture_diversity": 0.987447,
          "color_diversity": 0.999982
        },
        "texture_signals": {
          "laplacian_variance": 121.292,
          "sharpness_score": 0.98394,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.94952,
          "fft_high_frequency_ratio": 0.08348,
          "fft_peak_concentration": 0.09418,
          "fft_peak_to_mean": 48.831,
          "periodic_artifact_penalty": 0.03991,
          "lbp_naturalness_score": 0.9982,
          "lbp_entropy": 5.687,
          "lbp_peak_fraction": 0.10024
        },
        "color_signals": {
          "chroma_variance_score": 0.99991,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.99994,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T04:15:19.065539+00:00",
    "diagnostic_id": "03b2b364-609a-4273-bdcb-1be601385893",
    "session_id": "3293c930-1938-4b88-ac4e-2730eb23b24c",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.8592591480566107,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T04:15:19.070060+00:00",
    "diagnostic_id": "03b2b364-609a-4273-bdcb-1be601385893",
    "session_id": "3293c930-1938-4b88-ac4e-2730eb23b24c",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.264883,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.039698,
        "face_match": 0.035185,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T04:15:19.070126+00:00",
    "diagnostic_id": "03b2b364-609a-4273-bdcb-1be601385893",
    "session_id": "3293c930-1938-4b88-ac4e-2730eb23b24c",
    "stage": "decision",
    "values": {
      "checkin_id": "2181e3bb-1f13-4dd4-b05b-811db07e8796",
      "status": "approved",
      "risk_score": 0.2649,
      "venue_risk_score": 0.0331,
      "module3_risk_score": 0.264883,
      "effective_threshold": 0.5,
      "distance_meters": 6.62,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.841207,
      "face_match_passed": true,
      "face_match_score": 0.8592591480566107,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-25T04:15:20.043517+00:00",
    "diagnostic_id": "03b2b364-609a-4273-bdcb-1be601385893",
    "session_id": "3293c930-1938-4b88-ac4e-2730eb23b24c",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "2181e3bb-1f13-4dd4-b05b-811db07e8796",
      "status": "approved",
      "risk_score": 0.2649
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
