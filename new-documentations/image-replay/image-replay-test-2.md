# Phone image replay test 2 — 25 October 2026

State: **complete. Real-face control saved as approved; participant-reported static phone-photo presentation saved as rejected for performed liveness failure. Diagnostics are disabled, the allowlist is empty, and backend health is verified.**

## Scope and safeguards

Account `wcstudent1@example.com` is active and actively enrolled in SC4000. Existing face enrollment, camera consent and geolocation consent verified by scalar-only database projection; no biometric template retrieved. Participant performs both captures. No operator attendance submission, account/enrollment/consent/location change, threshold change, or recognition algorithm change is authorized or performed. Existing attendance and audit records are preserved. Only fixed-schema scalar diagnostics for these two sessions are retained; no images, video, base64 payloads, landmark arrays, biometric templates, credentials, or unfiltered Docker logs are saved.

## Matched sessions

Venue: **Test Venue2 25 Oct**, participant-supplied coordinates `1.263143, 103.823512`. Both lecture sessions use a 100 m radius, risk threshold 0.5, single-photo check-in (`require_motion_check=false`), passive liveness required and face matching required. Scheduled interval and check-in window both run from **15:04:55 to 17:04:55 SGT**, exactly two hours.

| Presentation | Session name | Session ID |
| --- | --- | --- |
| real_face_control | Phone replay R2 CONTROL real face (25 Oct 15:04 SGT) | `f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70` |
| phone_screen | Phone replay R2 TEST static phone photo (25 Oct 15:04 SGT) | `e7d17ca6-5f16-44d1-9490-4b94505e2010` |

Both creations returned HTTP 201. Authenticated student session readback verified matched policy/venue settings. Both initially had zero attendance records for this student. Existing API authentication helpers issued transient in-memory authorization tokens for API requests; no credentials were saved.

## Conditions

Participant reports **well lit**, **bright display**, **screen distance around 10 cm**, and **phone border visible**. Capture device/browser, display-phone model, numeric brightness, real-face distance, reflections, photo provenance and differences between captures remain **unknown**. Conditions are participant-reported; no image was inspected. Session labels alone do not establish the physical presentation.

## Baseline and checks

Reviewed AGENTS.md, instrumentation, monitor, both prior reports and relevant source paths across all four modules, plus session/check-in/liveness/database/integration contracts. No application source changes are needed. All docs and previous reports/configurations are preserved; pre-run hashes are held in a temporary scalar-only manifest.

Backend and Module 3 health returned HTTP 200. Deployed backend main/diagnostics/face-service and Module 3 config/liveness/main/risk/embedding SHA-256 hashes match local files. Existing recognition modifications predate this run and remain untouched. Running thresholds: liveness **0.85**, depth **0.80**, mesh **0.80**, identity **0.70**, risk **0.50**. These differ from the previous trial, which used liveness 0.60; this is not a controlled before/after algorithm comparison.

Existing instrumentation and monitor tests: **17 passed, 2 deprecation warnings**, in backend Python 3.11 with an isolated temporary SQLite database. Initial host Python run: 11 passed, 6 setup errors due to unsupported union annotations in its older Python; resolved by rerunning in backend Python. No live attendance-producing regression suite was run.

## Verified capture comparison

Participant confirmed real-face attendance in chat. Six diagnostic stages for attempt `85780864-875a-447c-adf1-222eb45856a2` correlate to saved check-in `2756f2b9-4323-4fd4-8681-659ff6d9ef4a`, student `wcstudent1@example.com`, control session `f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70`. Saved at **15:06:51.544745 SGT**. Authenticated my-checkins and check-in detail API readback plus scalar-only database ownership/score projection independently confirm **approved**, risk **0.2330**, performed passive liveness **true / 0.909611**, performed identity match **true / 0.9185184541**. API detail and database scores agree within floating-point serialization precision. Both `checkin_attempted` and `checkin_approved` audit events are present and preserved (IDs `ec9748da-3ab9-4aab-809a-43cc498830f6`, `073d5e87-6826-4e0e-94c2-e47dab3cbac0`). This is committed attendance, corroborated beyond a calculated decision.

| Metric | Real-face control | Phone-photo presentation |
| --- | --- | --- |
| Depth score / gate | 0.86713 / passed at 0.80 | 0.60928 / failed at 0.80 |
| Mesh plausibility / gate | 0.80908 / passed at 0.80 | 0.75161 / failed at 0.80 |
| Texture / color | 0.99883 / 1.00000 | 0.92752 / 1.00000 |
| Weighted component score | 0.912118 | 0.802565 |
| Presentation integrity | 0.997252 | 0.829468 |
| Periodic-artifact penalty | 0.00458 | 0.28422 |
| Passive liveness / threshold | 0.909611 / 0.85, passed | 0.000000 / 0.85, failed (pre-gate 0.665702) |
| Identity score / threshold | 0.9185184541 / 0.70, passed | 0.9185184541 / 0.70, passed |
| Module 3 liveness contribution | 0.022597 | 0.250000 |
| Module 3 identity contribution | 0.020370 | 0.020370 |
| Module 3 device contribution | 0.100000 | 0.100000 |
| Module 3 network contribution | 0.075000 | 0.075000 |
| Module 3 geolocation contribution | 0.015000 | 0.015000 |
| Module 3 total risk | 0.232967 | 0.460370 |
| Venue risk | 0.1628 | 0.1490 |
| Venue distance / radius | 32.56 m / 100 m | 29.81 m / 100 m |
| Location accuracy | 35 m | 35 m |
| Final risk / threshold | 0.2330 / 0.50 | 0.4604 / 0.50 |
| Saved attendance status | approved | rejected |

Liveness, face verification and Module 3 risk each returned usable HTTP 200 responses. The control is not an unavailable-check fallback. Weighted components 0.912118 multiplied by presentation integrity 0.997252 and passive challenge factor 1.0 produce approximately 0.909611; both depth and mesh gates passed. Final risk is `round(max(0.1628, 0.232967), 4) = 0.2330`, below 0.50. Device/network contributions are neutral scores and do not establish successful attestation/network checks. The phone-photo result and observed comparison follow below.

At the time of control correlation, diagnostics remained enabled for exactly the two trial sessions, the existing monitor remained running, and backend health was HTTP 200. A first correlation script assumed `student_id` existed in the my-checkins summary and stopped read-only with KeyError; corrected endpoint-specific projections and independent scalar ownership verification succeeded, with no data mutation.

## Verified phone-photo result and observed conclusion

Participant confirmed the phone-photo capture in chat. Six diagnostic stages for attempt `3fb805a6-da7b-4900-9097-e24a5b2194a0` correlate to saved check-in `8f6df163-91df-44fa-8ff4-039a5a1346cc`, phone session `e7d17ca6-5f16-44d1-9490-4b94505e2010`, and the intended student. Checked in **15:09:23.243697 SGT**. Authenticated my-checkins and detail readback independently confirmed **rejected**, risk **0.4604**; a scalar-only database projection verified student/session ownership, liveness false/0.0, and identity true/0.9185184541. Saved `checkin_attempted` and `checkin_rejected` audit events were read and preserved (IDs `87864f53-a0b3-4c5f-bbdf-be7a972cabeb`, `092abc76-ee97-4491-8ea9-bcf09a79fd1d`). Both captures therefore have committed records; rejected attendance is still a saved attendance attempt.

All three biometric/risk service calls returned usable HTTP 200 responses. The phone-photo liveness failure is a performed check, not an unavailable-service fallback. Depth decreased from 0.86713 to 0.60928 and mesh from 0.80908 to 0.75161; both phone-photo values are below their 0.80 gates. The weighted component score decreased from 0.912118 to 0.802565. Presentation integrity fell from 0.997252 to 0.829468, while periodic-artifact penalty increased from 0.00458 to 0.28422. Periodicity integrity was 0.829468, texture-diversity integrity 0.960138 and color-diversity integrity 1.0. Texture remained relatively high (0.92752), and color stayed 1.0. The product of weighted components, presentation integrity and passive challenge factor 1.0 gives pre-gate score approximately 0.665702, already below the 0.85 overall threshold. The deployed geometry gates additionally set the final liveness score to 0.0 because depth and mesh both failed.

The diagnostic fields `depth_detected=true`, `depth_quality=good` and complete face mesh do not override the numeric depth/mesh gate failures and do not establish physical depth. The identity score was identical to the real-face control at 0.9185184541: recognizing the enrolled face did not prove a live presentation. Module 3 liveness risk contribution increased from 0.022597 to 0.250000; all other weighted contributions remained the same. Module 3 total rose from 0.232967 to 0.460370. Phone-photo venue risk was 0.1490 (29.81 m from venue, within the 100 m radius), so final risk was `round(max(0.1490, 0.460370), 4) = 0.4604`, below 0.50. The independently enforced liveness failure, recorded as decision reason `liveness_failed`, caused rejection despite this below-threshold risk score.

**Observed conclusion:** the participant-reported static phone-photo presentation was rejected while the participant-reported real-face control was approved in this trial. This satisfies the screen-replay rejection target for this observation only. It does not establish general replay resistance, a detection rate, or that a visible phone border was specifically analyzed. Inferred depth/mesh failures and presentation penalties are measured signals; the physical presentation and conditions are participant-reported. Missing device/browser, reflections and other conditions remain unknown. The prior report used different deployed recognition settings, venue and conditions; the trials do not isolate the cause of the changed outcome.

## Interpretation and specification gaps

Unavailable/unperformed checks are unknown, never genuine passes. A calculated decision is separate from an attendance commit and must be correlated with the independently saved attendance record. Compare liveness components, presentation penalties, identity scores, Module 3 weighted contributions, venue risk, final risk and saved status after each submission. Inferred mesh/depth cues do not independently establish physical depth. Neutral device/network risk contributions do not prove device attestation or network verification passed. Conclusions apply only to the observed trial and participant-reported presentations.

Existing gaps: deployed API uses `name` while session-create documentation example says `session_name`; documentation liveness example/logic uses 0.60 while current deployed threshold is 0.85 with depth/mesh gates. Non-strict single-photo service outages can produce saved attendance without performed biometric checks; such a result would be inconclusive for replay detection. No code or docs changes are proposed to resolve these gaps during this test.

## Endpoints reused

`POST /api/v1/sessions/`, `GET /api/v1/enrollments/my-enrollments`, `GET /api/v1/sessions/{id}`, `GET /api/v1/checkins/my-checkins`, `GET /api/v1/checkins/{id}`, `GET /api/v1/sessions/active`, backend and Module 3 `GET /health`. Participant-only submission uses `POST /api/v1/checkins/` and normal internal `POST /liveness/check`, `/face/verify`, `/risk/assess`. No endpoint implemented.

## Monitoring and cleanup

Existing monitor emitted `MONITOR_READY` before requesting any captures (initial health probe hit startup connection refusal; subsequent backend and Module 3 health probes both returned HTTP 200). Exact two-session allowlist and deployed backend hashes independently verified after recreation; strict mode remains false. The existing monitor uses this run's unique config/report and a 125-minute safety timeout. It automatically disables diagnostics and clears the allowlist after both sessions commit, timeout, or operator interruption. Post-recreation backend and Module 3 health verified HTTP 200. Independent saved-record correlation for both captures and final cleanup/allowlist/health verification are complete. Test attendance/audit records are preserved.

## Final cleanup and preservation checks

The existing monitor exited successfully after both `attendance_committed` events and recreated only the backend with diagnostics disabled. Both presentation types are confirmed by the participant. Independent post-cleanup runtime checks verified `CHECKIN_DIAGNOSTICS_ENABLED=false`, an empty `CHECKIN_DIAGNOSTIC_SESSION_IDS`, and unchanged `STRICT_SECURITY_MODE=false`. Backend and Module 3 health both returned HTTP 200. The monitor is no longer running. Test sessions retain their two-hour schedules; no attendance or audit record was removed or edited.

After cleanup, both saved attendance records and their attempted/status audit entries were independently read again. Active account, active SC4000 enrollment, face-enrolled flag, and camera/geolocation consent remain unchanged. No face template was retrieved or altered. All eight deployed backend/Module 3 source hashes still match the verified pre-run/local sources, and recognition thresholds remain 0.85 liveness, 0.80 depth/mesh, 0.70 identity and 0.50 risk. All files in the preservation manifest (docs, previous reports and previous replay configurations/scripts) match their pre-run hashes.

Checks/results: 17 isolated diagnostic/monitor tests passed; two session creations HTTP 201; authenticated policy/empty-attendance preflight passed; both sessions independently confirmed active before inviting captures; six diagnostic stages per capture correlated with saved attendance and audit records; exact allowlist, disabled diagnostics, empty final allowlist, source/threshold preservation, student flags/enrollment and both health checks passed. Existing API summary lacks `student_id`; ownership was verified via authenticated access and explicit safe database projection. No recognition or API feature was implemented or changed during this run.

## Files changed

Added `new-tests/phone-image-replay-run-20261025T070255Z.json` and this report only. No existing source or report changes made by this run.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both presentations confirmed by participant; both saved attendance and audit records independently verified; diagnostics disabled and empty allowlist independently verified**.

Updated: 2026-10-25T15:09:25+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / 85780864-875a-447c-adf1-222eb45856a2

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-25T07:06:50.672312+00:00",
    "diagnostic_id": "85780864-875a-447c-adf1-222eb45856a2",
    "session_id": "f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-25T07:06:52.628284+00:00",
    "diagnostic_id": "85780864-875a-447c-adf1-222eb45856a2",
    "session_id": "f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.909611,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.94965,
        "depth_score": 0.86713,
        "mesh_plausibility_score": 0.80908,
        "texture_analysis_score": 0.99883,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.912118,
        "presentation_integrity_score": 0.997252,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.909611,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": true,
        "mesh_passed": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0005384,
        "relative_nose_depth": 0.04199,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.26014,
          "mesh": 0.202269,
          "texture": 0.249708,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.997252,
          "texture_diversity": 0.999358,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 1104.392,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.99611,
          "fft_high_frequency_ratio": 0.20686,
          "fft_peak_concentration": 0.08716,
          "fft_peak_to_mean": 39.552,
          "periodic_artifact_penalty": 0.00458,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.466,
          "lbp_peak_fraction": 0.09879
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.95935,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T07:06:52.743484+00:00",
    "diagnostic_id": "85780864-875a-447c-adf1-222eb45856a2",
    "session_id": "f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.9185184541380378,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T07:06:52.745281+00:00",
    "diagnostic_id": "85780864-875a-447c-adf1-222eb45856a2",
    "session_id": "f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.232967,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.022597,
        "face_match": 0.02037,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T07:06:52.745440+00:00",
    "diagnostic_id": "85780864-875a-447c-adf1-222eb45856a2",
    "session_id": "f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70",
    "stage": "decision",
    "values": {
      "checkin_id": "2756f2b9-4323-4fd4-8681-659ff6d9ef4a",
      "status": "approved",
      "risk_score": 0.233,
      "venue_risk_score": 0.1628,
      "module3_risk_score": 0.232967,
      "effective_threshold": 0.5,
      "distance_meters": 32.56,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.909611,
      "face_match_passed": true,
      "face_match_score": 0.9185184541380378,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-25T07:06:53.610710+00:00",
    "diagnostic_id": "85780864-875a-447c-adf1-222eb45856a2",
    "session_id": "f1c8a0fa-bff6-41de-bfc5-5b1f1f204a70",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "2756f2b9-4323-4fd4-8681-659ff6d9ef4a",
      "status": "approved",
      "risk_score": 0.233
    }
  }
]
```

### phone_screen / 3fb805a6-da7b-4900-9097-e24a5b2194a0

Passive liveness rejected this capture.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-25T07:09:21.781378+00:00",
    "diagnostic_id": "3fb805a6-da7b-4900-9097-e24a5b2194a0",
    "session_id": "e7d17ca6-5f16-44d1-9490-4b94505e2010",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-25T07:09:23.417986+00:00",
    "diagnostic_id": "3fb805a6-da7b-4900-9097-e24a5b2194a0",
    "session_id": "e7d17ca6-5f16-44d1-9490-4b94505e2010",
    "stage": "liveness",
    "values": {
      "liveness_passed": false,
      "liveness_score": 0.0,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.82434,
        "depth_score": 0.60928,
        "mesh_plausibility_score": 0.75161,
        "texture_analysis_score": 0.92752,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.802565,
        "presentation_integrity_score": 0.829468,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.665702,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": false,
        "mesh_passed": false,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.000347,
        "relative_nose_depth": 0.03323,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.182783,
          "mesh": 0.187901,
          "texture": 0.231881,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.829468,
          "texture_diversity": 0.960138,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 359.162,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.75841,
          "fft_high_frequency_ratio": 0.19066,
          "fft_peak_concentration": 0.15368,
          "fft_peak_to_mean": 75.458,
          "periodic_artifact_penalty": 0.28422,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 6.246,
          "lbp_peak_fraction": 0.08507
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 1.0,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T07:09:23.533709+00:00",
    "diagnostic_id": "3fb805a6-da7b-4900-9097-e24a5b2194a0",
    "session_id": "e7d17ca6-5f16-44d1-9490-4b94505e2010",
    "stage": "face_match",
    "values": {
      "match_passed": true,
      "match_score": 0.9185184541380378,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T07:09:23.536440+00:00",
    "diagnostic_id": "3fb805a6-da7b-4900-9097-e24a5b2194a0",
    "session_id": "e7d17ca6-5f16-44d1-9490-4b94505e2010",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.46037,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "MEDIUM",
      "signal_breakdown": {
        "liveness": 0.25,
        "face_match": 0.02037,
        "device": 0.1,
        "network": 0.075,
        "geolocation": 0.015
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-25T07:09:23.536614+00:00",
    "diagnostic_id": "3fb805a6-da7b-4900-9097-e24a5b2194a0",
    "session_id": "e7d17ca6-5f16-44d1-9490-4b94505e2010",
    "stage": "decision",
    "values": {
      "checkin_id": "8f6df163-91df-44fa-8ff4-039a5a1346cc",
      "status": "rejected",
      "risk_score": 0.4604,
      "venue_risk_score": 0.149,
      "module3_risk_score": 0.46037,
      "effective_threshold": 0.5,
      "distance_meters": 29.81,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": false,
      "liveness_score": 0.0,
      "face_match_passed": true,
      "face_match_score": 0.9185184541380378,
      "reason": "liveness_failed"
    }
  },
  {
    "timestamp": "2026-10-25T07:09:24.327992+00:00",
    "diagnostic_id": "3fb805a6-da7b-4900-9097-e24a5b2194a0",
    "session_id": "e7d17ca6-5f16-44d1-9490-4b94505e2010",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "8f6df163-91df-44fa-8ff4-039a5a1346cc",
      "status": "rejected",
      "risk_score": 0.4604
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
