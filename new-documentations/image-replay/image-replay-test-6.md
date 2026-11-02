# Different-person static-photo test 6 — 1 November 2026

State: **complete; genuine control approved; participant-reported other-person photo rejected with no face detected; saved records verified; diagnostics disabled and allowlists empty**.

The participant uses their existing account and unchanged enrolled face in both sessions. Control: their real face. Test: a static photograph of another person displayed on a second phone. Both assigned physical presentations were participant-confirmed in chat; captures were not inspected. The existing monitor label phone_screen means static_photo_other_person in this run.

## Sessions and policy

Course SC4000; participant wcstudent1@example.com; venue LT1A (1.34721921067674, 103.680296622411), radius 100 m. Both scheduled/check-in windows: **2026-11-01T15:53:45+08:00 to 2026-11-01T17:53:45+08:00** (two hours). Passive liveness and face matching required; motion disabled; attendance risk threshold 0.50.

- Image replay R6 CONTROL real face (01 Nov 15:53 SGT): `eda7c7b3-6625-4379-976a-ce3a02b21ae0`.
- Image replay R6 TEST other person photo (01 Nov 15:53 SGT): `eb162496-4802-425b-9f53-2ad5f65e2eab`.

Both creations HTTP 201; authenticated student detail reads HTTP 200 confirmed matching policies. Initial scalar attendance counts zero. Enrollment, face template, consents, participant location and device trust remain unchanged.

## Preflight and monitoring

Reviewed AGENTS.md, relevant paths across all four modules and database/API/integration contracts. All nine checked deployed source hashes match local source. Both health endpoints HTTP 200. Account, enrollment, face enrollment and camera/geolocation consents active; no template or credentials retrieved. Initial diagnostics off with empty allowlists in both services. Strict mode false, unchanged. Effective thresholds: liveness 0.85, depth/mesh 0.80, identity 0.70, risk 0.50.

Disposable network-disabled containers with repository mounted read-only: monitor suite 14 passed; scalar filtering/scoping/failure selection 7 passed, 7 deselected. No tests submitted live attendance. Temporary SHA-256 baseline protects 322 existing source, test, report and documentation files.

Backend image-mode scalar diagnostics covered exactly these two session IDs. Face-service diagnostics remain disabled; backend observation supplies the image scalar responses. Existing monitor timeout 122 minutes, with automatic backend diagnostic shutdown on completion, interruption or timeout. Runtime verification passed: backend diagnostics enabled for exactly the two new session IDs; face-service diagnostics disabled with empty allowlist; strict mode unchanged; both health endpoints HTTP 200. Authenticated student reads confirm both sessions active with matching policies/windows. Four recreated backend source hashes remain unchanged. Collector emitted MONITOR_READY before inviting captures.

## Interpretation and conditions

Capture device/browser, lighting, display brightness, camera distance and visible borders/reflections unknown. No raw images, video, base64 payloads, landmarks, templates, credentials or unfiltered Docker logs are saved by the monitor.

Correlate attempt/session/check-in IDs with saved attendance and audit records. Report liveness and identity separately from device/geofence risk and attendance status. Required identity mismatch flags unless another condition rejects; performed liveness failure rejects. Service unavailability is inconclusive. Missing or early-failure measurements are not passes. Inferred depth/mesh do not prove physical depth; neutral device/network contributions do not prove performed successful checks. This pair cannot establish a population error rate.

The monitor generic maximum-risk sentence omits existing backend device adjustment: final risk uses venue risk and backend-adjusted Module 3 risk, plus independent device/identity flags. Saved factors and source govern interpretation. Diagnostic reason risk_threshold can also describe identity/device flags below threshold.

## Endpoints reused

POST /api/v1/sessions/; authenticated GET /api/v1/sessions/{id} and /api/v1/sessions/active; GET /api/v1/checkins/my-checkins and /api/v1/checkins/{id}; backend/face-service GET /health. Participant alone submits POST /api/v1/checkins/, reusing internal /liveness/check, /face/verify and /risk/assess. No endpoint implemented.

## Specification gaps

Existing session-create example uses session_name; deployed API accepts name. Documentation liveness example 0.60 differs from deployed 0.85 with 0.80 geometry gates. Documentation does not fully describe existing required-identity flag/device adjustment. No source or documentation changes proposed.

## Verified real-face control

Participant confirmed the real-face submission in chat. All six diagnostic stages correlate to diagnostic attempt `e1851433-1b7e-4fa6-8049-663c464ca85c`, control session `eda7c7b3-6625-4379-976a-ce3a02b21ae0` and saved check-in `7aff19bc-b96e-4816-8bf6-d34ab299806b`.

Saved at **15:55:33 SGT**, status **approved**. Passive liveness **0.976928 / 0.85** passed; identity **0.881481 / 0.70** passed. Both service responses were usable HTTP 200 results, not unavailable-service fallbacks. Depth 0.99203 and mesh 0.91728 passed 0.80; texture/color and presentation integrity 1.0, periodic-artifact penalty 0.0.

Module 3 risk 0.225398 was adjusted to 0.125398 by existing device policy replacing placeholder device contribution 0.10 with 0.00. Venue risk 0.4762 dominates; final saved risk **0.4762**, below 0.50. Distance 95.24 m / 100 m radius, reported location accuracy 35 m. Saved risk factors null. Neutral device/network values do not establish performed successful checks.

Authenticated student summary and detail reads returned HTTP 200 and agreed with independent scalar database projection. Successful checkin_attempted and checkin_approved audit records verified: `1fb9710a-3685-48ab-aeda-29ee63c00a31`, `b8266133-1e8a-46cb-8179-9161eac53c58`. Attendance and audits preserved.

Before inviting the photo, authenticated student read confirmed its session active with matching policies, scalar count zero, both health endpoints HTTP 200, and backend diagnostics enabled for exactly the two new IDs. Collector remained running for the subsequent photo, whose verified result follows. Location is close to the geofence boundary; its contribution will be evaluated separately.

## Verified other-person photo and comparison

Participant confirmed the assigned photo submission in chat. All six scalar stages for attempt `f92e3a9b-2b07-4b43-967f-b422b6ff5fa3` correlate to the intended photo session and saved check-in `4b56df4a-5a72-48f5-b1df-419a13fad849`. Saved at **15:57:58.702142 SGT**, status **rejected**, risk **0.5900**. Post-shutdown authenticated student summary/detail HTTP 200 reads agree with independent scalar database projections. Attempt and rejected-outcome audits are preserved: `4b11edb4-e7f1-4e84-b033-5b3e7b9aef0b` (checkin_attempted, success=true), `d82f5f87-95b6-46dc-9bbe-3c12d0287bd7` (checkin_rejected, success=false). The source intentionally records success=false for a rejected outcome; this is not a failed audit write.

| Observation | Real-face control | Other-person static photo |
| --- | --- | --- |
| Face usable for comparison | yes | no face reported (`face_detected=false`) |
| Passive liveness returned / threshold | 0.976928 / 0.85, pass | 0.0 / 0.85, failed early |
| Identity returned / threshold | 0.8814813878 / 0.70, pass | 0.0 / 0.70, no identity comparison |
| Depth / mesh | 0.99203 / 0.91728, both pass 0.80 | not evaluated; default zeros |
| Texture / color | 1.0 / 1.0 | not evaluated; default zeros |
| Landmarks | 468 | default 0; no mesh analysis |
| Module 3 risk | 0.225398 | 0.690000 |
| Backend-adjusted Module 3 risk | 0.125398 | 0.590000 |
| Venue risk | 0.4762 | 0.4925 |
| Distance / radius / reported accuracy | 95.24 / 100 / 35 m | 98.49 / 100 / 35 m |
| Final saved risk | 0.4762 | 0.5900 |
| Saved attendance | approved | rejected |

All three photo service calls returned usable HTTP 200 responses. This was not an unavailable-service fallback. Face verification explicitly reported face_detected=false. Liveness returned the empty failure-details shape: default detection confidence 0, zero landmarks, incomplete mesh and default component zeros. Source `/liveness/check` returns this shape when no usable face is detected/extracted, before `assess_liveness`; `/face/verify` reports no face before template comparison. These zeros are **not measured physical flatness, measured texture/color deficits, or a measured different-person similarity**. No display-artifact penalty or presentation-integrity measurement is available for this photo. The scalar record cannot establish why face detection/extraction failed; capture conditions and pixels are unavailable.

The returned zero liveness and identity scores each contribute 0.25 to Module 3 risk, with device/network/geolocation placeholders 0.10/0.075/0.015, totaling 0.69. Existing backend device policy replaces 0.10 with 0.00, yielding 0.59. Final risk is max(0.4925 venue, 0.59 adjusted service)=0.59, above 0.50. Independently, the performed liveness response failed and forces rejection; the diagnostic reason is liveness_failed. Saved risk factors are liveness_failed (high, weight 1.0) and face_match_failed (critical, weight 1.0). Both reported positions are within the nominal geofence; no geofence risk factor was saved. Reported location is not independently attested physical location.

**Observed conclusion:** the participant-reported other-person photo was rejected and the genuine control was approved. This trial establishes end-to-end rejection of this capture. Because the service reported no usable face, it does **not** demonstrate successful discrimination between this other person's face and the enrolled person, nor classification of a detected face as a photo. A later, separately authorized trial with a detectably captured face would be needed to evaluate those stages. No retry or additional session is created here. Both physical presentations remain participant-reported; conditions are unknown and no media were retained by this diagnostic workflow.

## Completion and cleanup verification

The existing collector observed both commits, exited successfully, and recreated the backend with diagnostics disabled. Independent runtime checks confirm diagnostics disabled and allowlists empty in both backend and face service, unchanged strict mode false, unchanged liveness/depth/mesh/identity/risk thresholds 0.85/0.80/0.80/0.70/0.50, and HTTP 200 from both health endpoints. No monitor or diagnostic cleanup remains pending.

Both saved attendance records and all four attempted/outcome audit entries were independently read back and preserved. Account eligibility, enrollment, face-enrolled and consent flags remain active; no template was retrieved. Both sessions retain their original two-hour windows and biometric requirements. All nine checked running source hashes match unchanged local source. All 322 baseline files, including docs and prior reports, remain byte-identical.

Checks: 21 isolated preflight tests passed (7 deselected); both creations HTTP 201; four final authenticated summary/detail readbacks HTTP 200; 12 diagnostic stages correlated to two committed records; audit semantics verified against source; risk arithmetic and cleanup verified. An initial final audit assertion assumed success=true on rejected outcomes; corrected to the existing source convention success=false and the complete read-only verification passed. No application code change or new feature was made, so no additional test suite was required.

Files changed for this run: only this new report and `new-tests/phone-other-person-image-replay-20261101T075215Z.json`. Application source, existing tests, previous reports and docs remain untouched. No raw media, base64 payloads, landmarks, templates, credentials or unfiltered Docker logs saved.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both presentations participant-confirmed; saved attendance/audits verified; diagnostics disabled and allowlists empty**.

Updated: 2026-11-01T15:58:03+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / e1851433-1b7e-4fa6-8049-663c464ca85c

Passive liveness passed; enrolled-face match passed.

Final risk uses venue risk and backend-adjusted Module 3 risk, with independent device/identity flags; a failed performed liveness response forces rejection.

```json
[
  {
    "timestamp": "2026-11-01T07:55:33.052356+00:00",
    "diagnostic_id": "e1851433-1b7e-4fa6-8049-663c464ca85c",
    "session_id": "eda7c7b3-6625-4379-976a-ce3a02b21ae0",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-11-01T07:55:37.709318+00:00",
    "diagnostic_id": "e1851433-1b7e-4fa6-8049-663c464ca85c",
    "session_id": "eda7c7b3-6625-4379-976a-ce3a02b21ae0",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.976928,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.88278,
        "depth_score": 0.99203,
        "mesh_plausibility_score": 0.91728,
        "texture_analysis_score": 1.0,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.976928,
        "presentation_integrity_score": 1.0,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.976928,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": true,
        "mesh_passed": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0008004,
        "relative_nose_depth": 0.05125,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.297609,
          "mesh": 0.229319,
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
          "laplacian_variance": 443.366,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 1.0,
          "fft_high_frequency_ratio": 0.25779,
          "fft_peak_concentration": 0.06231,
          "fft_peak_to_mean": 29.803,
          "periodic_artifact_penalty": 0.0,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.34,
          "lbp_peak_fraction": 0.08751
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.97534,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:55:37.812339+00:00",
    "diagnostic_id": "e1851433-1b7e-4fa6-8049-663c464ca85c",
    "session_id": "eda7c7b3-6625-4379-976a-ce3a02b21ae0",
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
    "timestamp": "2026-11-01T07:55:37.813451+00:00",
    "diagnostic_id": "e1851433-1b7e-4fa6-8049-663c464ca85c",
    "session_id": "eda7c7b3-6625-4379-976a-ce3a02b21ae0",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.225398,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.005768,
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
    "timestamp": "2026-11-01T07:55:37.813543+00:00",
    "diagnostic_id": "e1851433-1b7e-4fa6-8049-663c464ca85c",
    "session_id": "eda7c7b3-6625-4379-976a-ce3a02b21ae0",
    "stage": "decision",
    "values": {
      "checkin_id": "7aff19bc-b96e-4816-8bf6-d34ab299806b",
      "status": "approved",
      "risk_score": 0.4762,
      "venue_risk_score": 0.4762,
      "module3_risk_score": 0.12539799999999998,
      "effective_threshold": 0.5,
      "distance_meters": 95.24,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.976928,
      "face_match_passed": true,
      "face_match_score": 0.8814813878371459,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-11-01T07:55:39.056651+00:00",
    "diagnostic_id": "e1851433-1b7e-4fa6-8049-663c464ca85c",
    "session_id": "eda7c7b3-6625-4379-976a-ce3a02b21ae0",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "7aff19bc-b96e-4816-8bf6-d34ab299806b",
      "status": "approved",
      "risk_score": 0.4762
    }
  }
]
```

### phone_screen / f92e3a9b-2b07-4b43-967f-b422b6ff5fa3

The face service reported no usable face: liveness failed early and identity was not compared. Attendance was saved as rejected. Default component zeros do not establish measured spoof cues.

Final risk uses venue risk and backend-adjusted Module 3 risk, with independent device/identity flags; a failed performed liveness response forces rejection.

```json
[
  {
    "timestamp": "2026-11-01T07:57:57.915258+00:00",
    "diagnostic_id": "f92e3a9b-2b07-4b43-967f-b422b6ff5fa3",
    "session_id": "eb162496-4802-425b-9f53-2ad5f65e2eab",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-11-01T07:58:01.745190+00:00",
    "diagnostic_id": "f92e3a9b-2b07-4b43-967f-b422b6ff5fa3",
    "session_id": "eb162496-4802-425b-9f53-2ad5f65e2eab",
    "stage": "liveness",
    "values": {
      "liveness_passed": false,
      "liveness_score": 0.0,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.0,
        "depth_score": 0.0,
        "mesh_plausibility_score": 0.0,
        "texture_analysis_score": 0.0,
        "color_distribution_score": 0.0,
        "challenge_evidence_score": 0.0,
        "challenge_integrity_score": 0.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.0,
        "face_mesh_complete": false,
        "depth_detected": false,
        "depth_passed": false,
        "mesh_passed": false,
        "landmark_count": 0,
        "depth_quality": "poor"
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:58:01.774753+00:00",
    "diagnostic_id": "f92e3a9b-2b07-4b43-967f-b422b6ff5fa3",
    "session_id": "eb162496-4802-425b-9f53-2ad5f65e2eab",
    "stage": "face_match",
    "values": {
      "match_passed": false,
      "match_score": 0.0,
      "match_threshold": 0.7,
      "face_detected": false,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:58:01.776215+00:00",
    "diagnostic_id": "f92e3a9b-2b07-4b43-967f-b422b6ff5fa3",
    "session_id": "eb162496-4802-425b-9f53-2ad5f65e2eab",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.69,
      "risk_threshold": 0.5,
      "pass_threshold": false,
      "risk_level": "HIGH",
      "signal_breakdown": {
        "liveness": 0.25,
        "face_match": 0.25,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-11-01T07:58:01.776324+00:00",
    "diagnostic_id": "f92e3a9b-2b07-4b43-967f-b422b6ff5fa3",
    "session_id": "eb162496-4802-425b-9f53-2ad5f65e2eab",
    "stage": "decision",
    "values": {
      "checkin_id": "4b56df4a-5a72-48f5-b1df-419a13fad849",
      "status": "rejected",
      "risk_score": 0.59,
      "venue_risk_score": 0.4925,
      "module3_risk_score": 0.59,
      "effective_threshold": 0.5,
      "distance_meters": 98.49,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": false,
      "liveness_score": 0.0,
      "face_match_passed": false,
      "face_match_score": 0.0,
      "reason": "liveness_failed"
    }
  },
  {
    "timestamp": "2026-11-01T07:58:02.934731+00:00",
    "diagnostic_id": "f92e3a9b-2b07-4b43-967f-b422b6ff5fa3",
    "session_id": "eb162496-4802-425b-9f53-2ad5f65e2eab",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "4b56df4a-5a72-48f5-b1df-419a13fad849",
      "status": "rejected",
      "risk_score": 0.59
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
