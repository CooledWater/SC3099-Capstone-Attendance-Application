# Phone image replay test 5 — 1 November 2026

State: **complete. Participant-confirmed control approved; static phone-photo replay passed biometric checks and committed as flagged for geofence risk. Diagnostics disabled, allowlists empty, both services healthy.**

## Scope and sessions

Participant account `wcstudent1@example.com` is active, actively enrolled in SC4000, face enrolled, and has camera/geolocation consent. Verified through scalar database projection; no template or credentials retrieved. Venue **LT1A** was selected by the participant. Catalogue coordinates 1.34721921067674, 103.680296622411; radius 100 m; risk threshold 0.50.

Both fresh lecture sessions allow single-photo check-in (`require_motion_check=false`) and require passive liveness and face matching. Identical scheduled/check-in windows are **1 November 2026, 15:05:35–17:05:35 SGT**, exactly two hours. Both creations returned HTTP 201.

| Presentation | Session name | Session ID |
| --- | --- | --- |
| real_face_control | Image replay R5 CONTROL real face (01 Nov 15:05 SGT) | `c4af59d5-b4d7-4f1c-b3bd-e82460d44457` |
| phone_screen | Image replay R5 TEST static phone photo (01 Nov 15:05 SGT) | `7ca3237e-e042-434d-8051-804d727cf8c2` |

The participant alone performs captures and attendance submission. Enrollment, face template, consents, participant location, device trust, thresholds and recognition algorithms remain unchanged. Attendance and audit records will be preserved.

## Capture conditions

Capture device/browser: **unknown**. Lighting: **unknown**. Display brightness: **unknown**. Camera distance: **unknown**. Visible borders/reflections: **unknown**. The participant requested skipping condition details; all five remain unknown. Physical presentation is participant-reported, not inferred from session labels.

## Preflight and monitoring

Reviewed AGENTS.md, existing scalar instrumentation and monitor, previous image report 4 and video instrumentation report, relevant paths across all four modules and the database/API/integration contracts. `docs/` is read-only. A temporary SHA-256 manifest preserves 45 existing documentation/report/source files. Existing working-tree changes predate this run and are preserved.

All nine deployed backend/face-service source hashes match local source. No source edits or rebuild are needed. Initial diagnostics are disabled with empty allowlists in both services. Backend and face-service health endpoints returned HTTP 200. Strict mode false; effective liveness 0.85, depth 0.80, mesh 0.80, identity 0.70, risk 0.50. None changed.

Network-disabled disposable-container monitor tests: **14 passed**. Isolated scalar instrumentation checks: **8 passed, 6 deselected**. The six integration cases were excluded; no tests submit attendance to the existing application. An initial overly broad selection deselected all cases (exit 5); corrected explicit selection passed above.

The existing image-mode monitor collected only allowlisted finite scalar diagnostics, with a 122-minute timeout covering the session opening and two-hour window, and automatic backend diagnostic shutdown. No raw images, video, base64 payloads, landmarks, biometric templates, credentials or unfiltered Docker logs are saved. Backend diagnostics were enabled for exactly these two new session IDs; face-service diagnostics remain disabled because image scalar responses use the existing backend observation path.

Deployment verified: backend diagnostics enabled for exactly the two new UUIDs, four backend source hashes unchanged after recreation, strict mode unchanged. Face-service diagnostics independently verified disabled with empty allowlist. Both health checks returned HTTP 200 after recreation. Authenticated student session readbacks confirmed matching policies, venue and two-hour windows; scalar database counts confirmed zero attendance in both sessions. Collector emitted `MONITOR_READY` before any capture invitation. Subsequent authenticated student reads confirmed both sessions **active** after the opening boundary. Preservation verification passed for all 45 manifest files.

## Correlation and interpretation

No outcome is assumed. After each participant submission, correlate diagnostic attempt/session/check-in IDs to committed attendance and audit records using authenticated readback and scalar database projections. Compare liveness components/gates, presentation penalties, identity scores, Module 3 contributions, backend device adjustment, venue risk, final risk and saved status. Calculated decisions are distinct from commits. Unavailable or unperformed checks remain unknown and cannot be called passes. Early failure default zeros must not be treated as measured components. Model-inferred depth and mesh do not establish physical depth; neutral device/network contributions do not establish successful checks. Conclusions will be limited to this observed trial.

## Verified control and replay comparison

The participant confirmed the real-face submission in chat. All six stages for diagnostic attempt `985d22bb-27eb-4701-ae9c-6da1e95d8b04` correlate with saved check-in `8174f72f-ee80-44a7-a917-b9d87b5a1f05`, the intended control session and student. Saved time **15:06:41.704285 SGT**, status **approved**, final risk **0.4646**. Authenticated student summary/detail HTTP 200 reads and independent scalar database projection agree, subject to floating-point serialization precision. Successful audit records `8a1ae1bf-e091-4a11-932a-a52b8ce72807` (`checkin_attempted`) and `cf8bb00d-ae85-4047-b60a-403e32594855` (`checkin_approved`) are preserved. This is committed attendance, beyond a calculated decision. Saved risk factors are null.

| Measurement | Real-face control | Static phone-photo |
| --- | --- | --- |
| Depth / gate | 0.98823 / passed at 0.80 | 0.96779 / passed at 0.80 |
| Mesh / gate | 0.91566 / passed at 0.80 | 0.88684 / passed at 0.80 |
| Texture / color | 1.0 / 1.0 | 1.0 / 1.0 |
| Weighted component score | 0.975383 | 0.962048 |
| Presentation integrity | 1.0 | 1.0 |
| Periodic-artifact penalty | 0.0 | 0.0 |
| Periodicity / texture-diversity / color-diversity integrity | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 |
| Pre-gate / final passive liveness | 0.975383 / 0.975383; passed at 0.85 | 0.962048 / 0.962048; passed at 0.85 |
| Identity / threshold | 0.8740739746 / 0.70; passed | 0.9037036276 / 0.70; passed |
| Module 3 liveness contribution | 0.006154 | 0.009488 |
| Module 3 identity contribution | 0.031482 | 0.024074 |
| Module 3 placeholder device contribution | 0.100000 | 0.100000 |
| Module 3 network contribution | 0.075000 | 0.075000 |
| Module 3 geolocation contribution | 0.015000 | 0.015000 |
| Module 3 service total | 0.227636 | 0.223562 |
| Backend-adjusted Module 3 risk | 0.127636 | 0.123562 |
| Venue risk / distance / radius | 0.4646 / 92.92 m / 100 m | 0.5104 / 102.09 m / 100 m |
| Reported location accuracy | 35 m | 35 m |
| Final risk / threshold | 0.4646 / 0.50 | 0.5104 / 0.50 |
| Saved attendance | approved | flagged (geo_out_of_bounds) |

Liveness, face-match and risk calls returned usable HTTP 200 responses. These biometric checks were performed; acceptance is not an unavailable-service fallback. Weighted components times presentation integrity and passive factor 1.0 yield liveness 0.975383, above 0.85; both geometry gates and identity passed. Inferred geometry does not establish physical depth.

Existing backend device policy replaced Module 3's placeholder device contribution 0.10 with 0.00, reducing service risk from 0.227636 to 0.127636. Venue risk dominates: `round(max(0.4646, 0.127636), 4) = 0.4646`, below 0.50; reason `below_threshold`. Neutral Module 3 device/network contributions do not prove performed checks. The operator made no location or device-trust changes.

After control correlation and before inviting the replay, the monitor was verified running with the exact two-session backend scope. Both health endpoints returned HTTP 200, the replay session was active until **17:05:35 SGT**, and its saved attendance count was zero. The replay subsequently committed as described below. All five capture conditions remain unknown at participant request.

## Verified static phone-photo replay

The participant confirmed the static-photo submission in chat. All six stages for diagnostic attempt `4af519b8-5b3d-4c5c-9ba8-855c341c244f` correlate with saved check-in `b7763dec-2f44-4a5b-8e03-3c2bf366b36e`, the intended replay session and student. Saved time **15:08:45.950199 SGT**, status **flagged**, final risk **0.5104**. After diagnostic shutdown, authenticated student summary/detail HTTP 200 reads and independent scalar database projections confirm ownership, saved scores and status for both records. Preserved successful replay audit records are `0223737a-5108-430d-b686-05f6a22f09d0` (`checkin_attempted`) and `3b254316-aa2d-413d-9c0e-760ee7e810a1` (`checkin_flagged`). This is committed flagged attendance, beyond a calculated decision.

All three replay service calls returned usable HTTP 200 responses. Depth **0.96779** and mesh **0.88684** passed their **0.80** gates. Texture and color were **1.0**, giving weighted score **0.962048**. Presentation integrity, periodicity, texture-diversity and color-diversity integrity were all **1.0**; periodic-artifact penalty was **0.0**. Passive factor **1.0** left final liveness **0.962048**, above **0.85**. Identity **0.9037036276** passed **0.70**. These were performed checks, not unavailable-service fallbacks. Passive factor 1.0 is not an independent challenge/freshness test; motion was disabled for both single-photo sessions.

Compared with the control, replay depth decreased **0.02044**, mesh decreased **0.02882**, and final liveness decreased **0.013335**, while identity increased **0.0296296530**. Both remained above their respective thresholds. Both presentations received full presentation integrity and zero periodic-artifact penalty. These signals did not identify the reported static replay in this pair. Inferred depth/mesh do not establish physical depth; matching the enrolled face does not establish liveness.

Module 3 liveness contribution rose **0.006154 → 0.009488**, while identity contribution fell **0.031482 → 0.024074**. Device/network/geolocation contributions stayed **0.10 / 0.075 / 0.015**. Service risk decreased **0.227636 → 0.223562**. Existing backend device policy replaced the device placeholder 0.10 with 0.00 in both attempts, yielding replay adjusted risk **0.123562**. Neutral placeholder device/network values are not evidence of performed successful checks.

Venue risk rose **0.4646 → 0.5104**, with reported distance **92.92 → 102.09 m** against the same **100 m** radius; reported accuracy was **35 m** for both. Saved replay risk factors contain exactly `geo_out_of_bounds`, medium severity, weight **0.5104**. The final replay risk was `round(max(0.5104, 0.123562), 4) = 0.5104`, exceeding **0.50**, with diagnostic reason `risk_threshold`. It was outside the nominal radius but below the 200 m hard-reject distance. The recorded distance is derived from reported geolocation, not proof of an actual physical movement; neither participant location nor venue policy was altered by the operator. The differing geofence results limit direct comparison of final attendance status.

**Observed conclusion:** this participant-reported static phone-photo replay passed the existing passive liveness and identity checks and produced **flagged attendance because of geofence risk**. The genuine control produced approved attendance. This trial shows biometric acceptance of the reported replay, but does not show an end-to-end approved replay. The geofence flag is not evidence of replay detection. It does not establish a population false-acceptance rate, behavior across other capture conditions, or the image property causing acceptance. Physical presentation is participant-reported, captures were not inspected or retained, and all five requested conditions remain unknown.

## Endpoints reused

`POST /api/v1/sessions/`, `GET /api/v1/sessions/{id}`, `GET /api/v1/sessions/active`, `GET /api/v1/checkins/my-checkins`, `GET /api/v1/checkins/{id}`, backend/face-service `GET /health`. Participant-only `POST /api/v1/checkins/` reuses internal `/liveness/check`, `/face/verify`, `/risk/assess`. No endpoint implemented.

## Specification gaps

Existing session-create example uses `session_name`; deployed API accepts `name`. Older documentation liveness example is 0.60; deployed policy is 0.85 with 0.80 geometry gates. Non-strict unavailable-service outcomes must remain inconclusive. Existing device policy can adjust Module 3 risk and independently flag attendance; the monitor's generic maximum-risk sentence omits this adjustment, so actual source, saved risk factors and adjusted diagnostic risk govern the comparison. Diagnostic reason `risk_threshold` may also describe device flags below threshold. No source or documentation changes proposed.

## Cleanup and files changed

The collector observed commits for both sessions, exited successfully, and recreated the backend with diagnostics disabled and an empty allowlist. Independent runtime checks confirmed diagnostics disabled and allowlists empty in **both backend and face service**, strict mode still false, and **HTTP 200** from both health endpoints. No monitor cleanup remains pending.

After shutdown, both attendance records and all four successful attempted/outcome audit entries were read back and preserved. Active account/enrollment, face-enrolled and camera/geolocation consent flags remain unchanged; no template was retrieved. All nine deployed source hashes match the unchanged local source. Effective thresholds remain liveness 0.85, depth/mesh 0.80, identity 0.70, risk 0.50. Sessions retain their original two-hour windows.

Final checks: **22 passed, 6 deselected** in isolated scalar/monitor preflight; two session creations HTTP 201; active matching-policy and empty-attendance preflight passed; six diagnostic stages per capture correlated; authenticated summary/detail and scalar attendance/audit projections agree; diagnostic shutdown, empty allowlists, unchanged source/thresholds/eligibility and both health endpoints verified. All **45** original manifest files, including all prior reports and `docs/`, remain byte-identical. No raw media, base64 payloads, landmarks, biometric templates, credentials or unfiltered Docker logs were saved.

Added `new-tests/phone-image-replay-20261101T070355Z.json` and this report. Previous reports, application source and `docs/` remain untouched.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both presentations participant-confirmed; saved attendance and audit records verified; diagnostics disabled and allowlists empty**.

Updated: 2026-11-01T15:08:51+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / 985d22bb-27eb-4701-ae9c-6da1e95d8b04

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and backend-adjusted Module 3 risk; existing device policy replaces its placeholder contribution before combination. A liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-11-01T07:06:40.854714+00:00",
    "diagnostic_id": "985d22bb-27eb-4701-ae9c-6da1e95d8b04",
    "session_id": "c4af59d5-b4d7-4f1c-b3bd-e82460d44457",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-11-01T07:06:45.446086+00:00",
    "diagnostic_id": "985d22bb-27eb-4701-ae9c-6da1e95d8b04",
    "session_id": "c4af59d5-b4d7-4f1c-b3bd-e82460d44457",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.975383,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.8849,
        "depth_score": 0.98823,
        "mesh_plausibility_score": 0.91566,
        "texture_analysis_score": 1.0,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.975383,
        "presentation_integrity_score": 1.0,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.975383,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": true,
        "mesh_passed": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0007718,
        "relative_nose_depth": 0.05078,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.296468,
          "mesh": 0.228916,
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
          "laplacian_variance": 393.661,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 1.0,
          "fft_high_frequency_ratio": 0.25702,
          "fft_peak_concentration": 0.06015,
          "fft_peak_to_mean": 29.402,
          "periodic_artifact_penalty": 0.0,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.221,
          "lbp_peak_fraction": 0.07815
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.98773,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:06:45.555795+00:00",
    "diagnostic_id": "985d22bb-27eb-4701-ae9c-6da1e95d8b04",
    "session_id": "c4af59d5-b4d7-4f1c-b3bd-e82460d44457",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.8740739745769676,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:06:45.560736+00:00",
    "diagnostic_id": "985d22bb-27eb-4701-ae9c-6da1e95d8b04",
    "session_id": "c4af59d5-b4d7-4f1c-b3bd-e82460d44457",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.227636,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.006154,
        "face_match": 0.031482,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:06:45.560934+00:00",
    "diagnostic_id": "985d22bb-27eb-4701-ae9c-6da1e95d8b04",
    "session_id": "c4af59d5-b4d7-4f1c-b3bd-e82460d44457",
    "stage": "decision",
    "values": {
      "checkin_id": "8174f72f-ee80-44a7-a917-b9d87b5a1f05",
      "status": "approved",
      "risk_score": 0.4646,
      "venue_risk_score": 0.4646,
      "module3_risk_score": 0.127636,
      "effective_threshold": 0.5,
      "distance_meters": 92.92,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.975383,
      "face_match_passed": true,
      "face_match_score": 0.8740739745769676,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-11-01T07:06:46.755245+00:00",
    "diagnostic_id": "985d22bb-27eb-4701-ae9c-6da1e95d8b04",
    "session_id": "c4af59d5-b4d7-4f1c-b3bd-e82460d44457",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "8174f72f-ee80-44a7-a917-b9d87b5a1f05",
      "status": "approved",
      "risk_score": 0.4646
    }
  }
]
```

### phone_screen / 4af519b8-5b3d-4c5c-9ba8-855c341c244f

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and backend-adjusted Module 3 risk; existing device policy replaces its placeholder contribution before combination. A liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-11-01T07:08:45.157565+00:00",
    "diagnostic_id": "4af519b8-5b3d-4c5c-9ba8-855c341c244f",
    "session_id": "7ca3237e-e042-434d-8051-804d727cf8c2",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-11-01T07:08:48.804124+00:00",
    "diagnostic_id": "4af519b8-5b3d-4c5c-9ba8-855c341c244f",
    "session_id": "7ca3237e-e042-434d-8051-804d727cf8c2",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.962048,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.80294,
        "depth_score": 0.96779,
        "mesh_plausibility_score": 0.88684,
        "texture_analysis_score": 1.0,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.962048,
        "presentation_integrity_score": 1.0,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.962048,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": true,
        "mesh_passed": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0006952,
        "relative_nose_depth": 0.04811,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.290338,
          "mesh": 0.22171,
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
          "laplacian_variance": 232.021,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 1.0,
          "fft_high_frequency_ratio": 0.21494,
          "fft_peak_concentration": 0.07042,
          "fft_peak_to_mean": 31.646,
          "periodic_artifact_penalty": 0.0,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.019,
          "lbp_peak_fraction": 0.07546
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.96796,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:08:48.918183+00:00",
    "diagnostic_id": "4af519b8-5b3d-4c5c-9ba8-855c341c244f",
    "session_id": "7ca3237e-e042-434d-8051-804d727cf8c2",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.9037036276176811,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:08:48.919789+00:00",
    "diagnostic_id": "4af519b8-5b3d-4c5c-9ba8-855c341c244f",
    "session_id": "7ca3237e-e042-434d-8051-804d727cf8c2",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.223562,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.009488,
        "face_match": 0.024074,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:08:48.919925+00:00",
    "diagnostic_id": "4af519b8-5b3d-4c5c-9ba8-855c341c244f",
    "session_id": "7ca3237e-e042-434d-8051-804d727cf8c2",
    "stage": "decision",
    "values": {
      "checkin_id": "b7763dec-2f44-4a5b-8e03-3c2bf366b36e",
      "status": "flagged",
      "risk_score": 0.5104,
      "venue_risk_score": 0.5104,
      "module3_risk_score": 0.123562,
      "effective_threshold": 0.5,
      "distance_meters": 102.09,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.962048,
      "face_match_passed": true,
      "face_match_score": 0.9037036276176811,
      "reason": "risk_threshold"
    }
  },
  {
    "timestamp": "2026-11-01T07:08:50.059244+00:00",
    "diagnostic_id": "4af519b8-5b3d-4c5c-9ba8-855c341c244f",
    "session_id": "7ca3237e-e042-434d-8051-804d727cf8c2",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "b7763dec-2f44-4a5b-8e03-3c2bf366b36e",
      "status": "flagged",
      "risk_score": 0.5104
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
