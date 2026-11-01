# Phone image replay test 4 — 30 October 2026

State: **complete. Participant-confirmed real-face control and static phone-photo replay both saved as approved. Replay accepted in this observed trial. Diagnostics disabled, allowlists empty, both service health checks verified.**

## Scope and matched sessions

Account `wcstudent1@example.com` is active, actively enrolled in SC4000, face enrolled, and has camera/geolocation consent. Eligibility was verified by scalar-only projection without retrieving templates or credentials. Participant performs both captures manually. No operator attendance submission or enrollment, template, consent, location, device trust, threshold or recognition algorithm changes are made. Attendance and audit records are preserved.

Venue **LT26**, catalogue coordinates 1.3434326, 103.6815837; radius 100.0 m; risk threshold 0.5. Both lecture sessions permit single-photo capture (`require_motion_check=false`) and require passive liveness and enrolled-face matching. Scheduled and check-in windows are identical, exactly two hours: **2026-10-30T10:28:05+08:00** to **2026-10-30T12:28:05+08:00**.

| Presentation | Name | Session ID |
| --- | --- | --- |
| real_face_control | Image replay R4 CONTROL real face retry (30 Oct 10:28 SGT) | `6f3c696a-633b-4242-bb39-75999bcb9c68` |
| phone_screen | Image replay R4 TEST static phone photo (30 Oct 10:28 SGT) | `299a5df8-afb5-4a92-832c-2f1a43725aac` |

Both creations returned HTTP 201. A read at the opening boundary did not yet satisfy the active-state assertion; subsequent authenticated reads independently confirmed both sessions active with matching single-photo policies and empty attendance before inviting captures. Authenticated student readback verified matched policies/venue and zero existing attendance for each session. Tokens were transient and never saved.

## Conditions

Capture device/browser, lighting, display brightness, camera distance and visible borders/reflections: **unknown**, as requested by the participant. Session labels alone do not prove physical presentation. No captures are inspected or retained.

## Baseline and checks

Reviewed AGENTS.md, relevant source paths across all four modules, existing scalar instrumentation and monitor, historical image reports and latest video report, and session/check-in/integration/database contracts. `docs/` remains read-only. A temporary SHA-256 preservation manifest covers 84 existing source/document/report/config files. Existing working-tree changes predate this run and remain untouched.

Existing monitor and scalar instrumentation tests in a network-disabled disposable container: **22 passed, 6 deselected**, two harmless pytest cache warnings because the repository was mounted read-only. Live attendance-producing integration tests were excluded. Backend and face-service diagnostics started disabled with empty allowlists. Running thresholds: liveness 0.85, depth 0.80, mesh 0.80, identity 0.70, risk 0.50; strict mode false. All nine deployed backend/face-service source hashes match local source; no rebuild was needed. After backend recreation, its four instrumentation hashes still match. Both health endpoints returned HTTP 200. Retry deployment independently verified: backend enabled for exactly the two new session IDs, all four deployed instrumentation hashes unchanged, strict mode false, both service health endpoints HTTP 200, face-service diagnostics disabled with empty allowlist, recognition thresholds unchanged. The new collector emitted MONITOR_READY before inviting the retry. No outcome is assumed.

Only fixed-schema session-scoped scalar diagnostics are retained. No raw images, video, base64 payloads, landmarks, biometric templates, credentials or unfiltered Docker logs are saved.

## Retry context

Participant requested a new genuine control after run 3 was rejected at the multiple-face detection guard. Run 3's attendance and audit records remain preserved, and its stopped/incomplete report is finalized separately. This fresh pair has identical two-hour windows and unchanged LT26, course and recognition policies. Do not pool the failed control's default component zeros with measured retry results. The participant performs both new captures manually; a successful retry is not assumed. All capture conditions remain unknown by participant request.

## Verified real-face retry

Participant confirmed the real-face capture in chat. All six diagnostic stages for attempt `e0d6b60e-ad32-4d65-8f44-acd5d9d29384` correlate to saved check-in `a02f5747-2d3a-4c23-a850-56101340b168`, the intended student and new control session. Saved at **10:30:42.168811 SGT**, attendance is **approved**, risk **0.1326**. Authenticated my-checkins/detail HTTP 200 readbacks and independent scalar database ownership/score projection agree (floating-point serialization precision applies). Preserved audit events `checkin_attempted` (`a5562b3e-8494-4476-8eb2-189f3282999d`) and `checkin_approved` (`86df03b6-6487-488d-ba7b-fceded6c6f8f`) both have success true. This is committed attendance, beyond a calculated decision.

All three liveness/face/risk calls returned usable HTTP 200 responses. This control performed the biometric checks; it is not an unavailable-service fallback. Depth and mesh passed their 0.80 gates. Weighted components times presentation integrity and passive factor 1.0 give approximately `0.915599 × 0.995224 = 0.911227`, exceeding the 0.85 liveness threshold. Identity score **0.9185184541** exceeds 0.70.

| Measurement | Real-face retry | Static phone-photo |
| --- | --- | --- |
| Depth / gate | 0.87359 / passed at 0.80 | 0.92860 / passed at 0.80 |
| Mesh / gate | 0.81612 / passed at 0.80 | 0.84232 / passed at 0.80 |
| Texture / color | 0.99797 / 1.00000 | 0.99923 / 1.00000 |
| Weighted component score | 0.915599 | 0.938967 |
| Presentation integrity | 0.995224 | 0.998194 |
| Periodic-artifact penalty | 0.00796 | 0.00301 |
| Periodicity / texture-diversity / color-diversity integrity | 0.995224 / 0.998884 / 1.00000 | 0.998194 / 0.999578 / 1.00000 |
| Pre-gate / final passive liveness | 0.911227 / 0.911227; passed at 0.85 | 0.937271 / 0.937271; passed at 0.85 |
| Identity score / threshold | 0.9185184541 / 0.70; passed | 0.9037036276 / 0.70; passed |
| Module 3 liveness contribution | 0.022193 | 0.015682 |
| Module 3 identity contribution | 0.020370 | 0.024074 |
| Module 3 placeholder device contribution | 0.100000 | 0.100000 |
| Module 3 network contribution | 0.075000 | 0.075000 |
| Module 3 geolocation contribution | 0.015000 | 0.015000 |
| Module 3 service total | 0.232563 | 0.229756 |
| Backend-adjusted Module 3 risk | 0.132563 | 0.129756 |
| Venue risk / distance / radius | 0.0337 / 6.74 m / 100 m | 0.0430 / 8.60 m / 100 m |
| Reported location accuracy | 40 m | 40 m |
| Final risk / threshold | 0.1326 / 0.50 | 0.1298 / 0.50 |
| Saved attendance | approved | approved |

Existing backend device policy replaced the service placeholder device contribution 0.10 with 0.00, explaining the adjusted risk **0.132563** versus service total **0.232563**. Final risk is `round(max(0.0337, 0.132563), 4) = 0.1326`, with diagnostic reason `below_threshold`. Neutral service device/network contributions alone are not proof of passed checks. No operator device trust or policy changes were made.

The participant-reported genuine retry provides a measured passing control for this pair. The earlier multiple-face rejection remains preserved separately in report 3 and is not erased or treated as measured zero-valued components for this comparison. The completed replay comparison and bounded conclusion follow below.

After this correlation the monitor remained running, the backend was healthy (HTTP 200), and the exact two-session diagnostic allowlist was verified. At that control readback, the static-photo session was active until **12:28:05 SGT** with zero saved attendance. It was subsequently completed below. All capture conditions remain unknown at participant request.

## Verified static phone-photo replay and comparison

The participant confirmed completion of the instructed static-photo replay in chat. All six diagnostic stages for attempt `715fe939-66e5-43f6-983e-5a1d791e517f` correlate to committed check-in `5a381314-889b-44d4-b38b-51a80669ffdd`, the intended student and static-photo session. Saved at **10:33:14.690260 SGT**, attendance is **approved**, risk **0.1298**. Authenticated my-checkins and detail HTTP 200 reads independently agree with the scalar-only database projection of ownership, status and biometric/risk scores. Preserved successful audit events are `checkin_attempted` (`09237f88-2f30-4deb-8d82-b3b54d387bb7`) and `checkin_approved` (`8bd9d2db-fd79-4578-a600-194c50f08587`). Both records were verified again after diagnostic shutdown, with empty saved risk-factor lists. This is an end-to-end approved attendance result, not merely a calculated decision or passed biometric response.

Liveness, identity and risk service calls each returned usable HTTP 200 responses. The replay's inferred depth **0.92860** and mesh **0.84232** both exceeded their **0.80** gates. Texture **0.99923** and color **1.0** contributed to weighted score **0.938967**. Presentation integrity **0.998194** and passive factor **1.0** yield approximately **0.937271**, above the liveness threshold **0.85**. Identity **0.9037036276** exceeded **0.70**. These are performed checks, not service-outage fallbacks. Inferred depth/mesh do not prove a physical live face.

Compared with the genuine control, replay depth increased **0.05501**, mesh increased **0.02620**, and final liveness increased **0.026044**. Presentation integrity increased from **0.995224** to **0.998194**, while periodic-artifact penalty decreased from **0.00796** to **0.00301**. Thus the measured presentation signals did not reject this replay. Identity decreased from **0.9185184541** to **0.9037036276** but still passed; recognizing the enrolled face does not establish presentation liveness.

Module 3's liveness contribution decreased from **0.022193** to **0.015682**, identity contribution increased from **0.020370** to **0.024074**, and placeholder device/network/geolocation contributions stayed **0.10 / 0.075 / 0.015**. Service total decreased from **0.232563** to **0.229756**. Existing backend policy replaced the device placeholder **0.10** with **0.00**, giving adjusted replay risk **0.129756**. Venue risk was **0.0430** at **8.60 m** within the **100 m** radius, with reported accuracy **40 m**. Final risk was `round(max(0.0430, 0.129756), 4) = 0.1298`, below **0.50**; decision reason was `below_threshold`. No unavailable device/network check is claimed as a genuine pass based only on neutral Module 3 scores.

**Observed conclusion:** the participant-confirmed static phone-photo presentation passed the existing passive liveness and identity checks and produced approved attendance, alongside an approved genuine control. This is an observed false acceptance of the reported replay, so this pair did not meet the replay-rejection target. It does not establish a population false-acceptance rate, robustness across conditions, or which image property caused acceptance. Physical presentation is participant-reported; no captures were inspected, and device/browser, lighting, brightness, distance and borders/reflections remain unknown. The earlier face-count rejection is retained in report 3 and is not evidence of static-photo replay detection.

## Interpretation and specification gaps

Unavailable or unperformed checks remain unknown; they are not genuine passes. Calculated decisions must be correlated to saved attendance through authenticated readback and scalar database/audit projections. Compare liveness components and gates, presentation penalties, identity score, Module 3 contributions, venue and final risk, and saved status after each capture. Model-inferred depth/mesh do not establish physical depth. Neutral device/network scores do not establish successful checks. Conclusions are limited to this observed pair.

Existing gaps: the session-create documentation example uses `session_name`, while the deployed API accepts `name`; documentation's older liveness example uses 0.60 while deployed policy is 0.85 with 0.80 geometry gates. Non-strict outages must be treated as unavailable even if attendance saves. Device policy can independently flag attendance and modify Module 3/final risk. The monitor's generic maximum-risk sentence omits that device adjustment; the report's correlation will use the actual source and saved risk factors. Diagnostic `decision.reason=risk_threshold` may label device flags below the cutoff. No code or documentation change is proposed for these existing gaps.

## Endpoints reused

`POST /api/v1/sessions/`, `GET /api/v1/sessions/{id}`, `GET /api/v1/sessions/active`, `GET /api/v1/checkins/my-checkins`, `GET /api/v1/checkins/{id}`, backend/face-service `GET /health`. Participant-only `POST /api/v1/checkins/` calls the existing internal `/liveness/check`, `/face/verify` and `/risk/assess`. No endpoint implemented.

## Monitoring and cleanup

The unique run configuration and existing image-mode collector reported MONITOR_READY before any captures and used the exact two-session backend allowlist. After both attendance commits, the collector exited successfully and recreated the backend with diagnostics disabled and its allowlist empty. Independent runtime verification confirmed **disabled diagnostics and empty allowlists in both backend and face service**, unchanged strict mode false, and backend/face-service health **HTTP 200**. The monitor is no longer running; automatic timeout cleanup is no longer pending.

Both attendance records and all four successful attempted/approved audit entries were independently verified after cleanup and preserved. Active account/enrollment, face-enrolled and camera/geolocation consent flags remain unchanged. No biometric template was read. All nine deployed backend/face-service source hashes remain unchanged; thresholds remain liveness **0.85**, depth/mesh **0.80**, identity **0.70**, risk **0.50**. All 84 original preservation-manifest files remain byte-identical, and the separate historical-report manifest confirms preservation of finalized report 3 and earlier reports. `docs/` remains untouched. Sessions retain their two-hour windows; no attendance, audit or previous report was deleted.

Checks/results: existing isolated scalar/monitor preflight **22 passed, 6 deselected** (two read-only pytest-cache warnings); two creations **HTTP 201**; active matched policy and empty-attendance preflight passed; six stages per capture correlated; both authenticated summary/detail reads and database/audit projections passed; final exact disabled flags, empty allowlists, unchanged source/thresholds/eligibility and both health checks passed. No application-code changes required further integration tests. No raw media, base64 payloads, landmarks, templates, credentials or unfiltered Docker logs were retained.

## Files changed

Added `new-tests/phone-image-replay-20261030T022635Z.json` and this report; finalized run 3 configuration/report as stopped for retry. Existing application source and historical reports 0–2 remain unchanged. No new endpoint is implemented.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **finished; both presentations participant-confirmed; saved attendance and audit records independently verified; diagnostics disabled and allowlists empty**.

Updated: 2026-10-30T10:33:19+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / e0d6b60e-ad32-4d65-8f44-acd5d9d29384

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and backend-adjusted Module 3 risk; existing device policy replaces its placeholder contribution before combination. Liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-30T02:30:41.278965+00:00",
    "diagnostic_id": "e0d6b60e-ad32-4d65-8f44-acd5d9d29384",
    "session_id": "6f3c696a-633b-4242-bb39-75999bcb9c68",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-30T02:30:45.243610+00:00",
    "diagnostic_id": "e0d6b60e-ad32-4d65-8f44-acd5d9d29384",
    "session_id": "6f3c696a-633b-4242-bb39-75999bcb9c68",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.911227,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.91805,
        "depth_score": 0.87359,
        "mesh_plausibility_score": 0.81612,
        "texture_analysis_score": 0.99797,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.915599,
        "presentation_integrity_score": 0.995224,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.911227,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": true,
        "mesh_passed": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0005503,
        "relative_nose_depth": 0.04283,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.262076,
          "mesh": 0.204031,
          "texture": 0.249493,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.995224,
          "texture_diversity": 0.998884,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 276.413,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.99324,
          "fft_high_frequency_ratio": 0.11898,
          "fft_peak_concentration": 0.08748,
          "fft_peak_to_mean": 41.029,
          "periodic_artifact_penalty": 0.00796,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 5.82,
          "lbp_peak_fraction": 0.11517
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.93341,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-30T02:30:45.343298+00:00",
    "diagnostic_id": "e0d6b60e-ad32-4d65-8f44-acd5d9d29384",
    "session_id": "6f3c696a-633b-4242-bb39-75999bcb9c68",
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
    "timestamp": "2026-10-30T02:30:45.345402+00:00",
    "diagnostic_id": "e0d6b60e-ad32-4d65-8f44-acd5d9d29384",
    "session_id": "6f3c696a-633b-4242-bb39-75999bcb9c68",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.232563,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.022193,
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
    "timestamp": "2026-10-30T02:30:45.345613+00:00",
    "diagnostic_id": "e0d6b60e-ad32-4d65-8f44-acd5d9d29384",
    "session_id": "6f3c696a-633b-4242-bb39-75999bcb9c68",
    "stage": "decision",
    "values": {
      "checkin_id": "a02f5747-2d3a-4c23-a850-56101340b168",
      "status": "approved",
      "risk_score": 0.1326,
      "venue_risk_score": 0.0337,
      "module3_risk_score": 0.132563,
      "effective_threshold": 0.5,
      "distance_meters": 6.74,
      "radius_meters": 100.0,
      "accuracy_meters": 40.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.911227,
      "face_match_passed": true,
      "face_match_score": 0.9185184541380378,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-30T02:30:46.603447+00:00",
    "diagnostic_id": "e0d6b60e-ad32-4d65-8f44-acd5d9d29384",
    "session_id": "6f3c696a-633b-4242-bb39-75999bcb9c68",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "a02f5747-2d3a-4c23-a850-56101340b168",
      "status": "approved",
      "risk_score": 0.1326
    }
  }
]
```

### phone_screen / 715fe939-66e5-43f6-983e-5a1d791e517f

Passive liveness passed; enrolled-face match passed.

The final risk is the maximum of venue risk and backend-adjusted Module 3 risk; existing device policy replaces its placeholder contribution before combination. Liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-30T02:33:13.911902+00:00",
    "diagnostic_id": "715fe939-66e5-43f6-983e-5a1d791e517f",
    "session_id": "299a5df8-afb5-4a92-832c-2f1a43725aac",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-30T02:33:17.599759+00:00",
    "diagnostic_id": "715fe939-66e5-43f6-983e-5a1d791e517f",
    "session_id": "299a5df8-afb5-4a92-832c-2f1a43725aac",
    "stage": "liveness",
    "values": {
      "liveness_passed": true,
      "liveness_score": 0.937271,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.93649,
        "depth_score": 0.9286,
        "mesh_plausibility_score": 0.84232,
        "texture_analysis_score": 0.99923,
        "color_distribution_score": 1.0,
        "weighted_component_score": 0.938967,
        "presentation_integrity_score": 0.998194,
        "challenge_evidence_score": 1.0,
        "challenge_integrity_score": 1.0,
        "threshold": 0.85,
        "depth_threshold": 0.8,
        "mesh_threshold": 0.8,
        "pre_gate_liveness_score": 0.937271,
        "face_mesh_complete": true,
        "depth_detected": true,
        "depth_passed": true,
        "mesh_passed": true,
        "single_image_challenge_proxy": false,
        "landmark_count": 468,
        "landmark_z_variance": 0.0006188,
        "relative_nose_depth": 0.04533,
        "depth_quality": "good",
        "weighted_contributions": {
          "depth": 0.27858,
          "mesh": 0.210579,
          "texture": 0.249808,
          "color": 0.2
        },
        "component_weights": {
          "depth": 0.3,
          "mesh": 0.25,
          "texture": 0.25,
          "color": 0.2
        },
        "presentation_integrity_checks": {
          "periodicity": 0.998194,
          "texture_diversity": 0.999578,
          "color_diversity": 1.0
        },
        "texture_signals": {
          "laplacian_variance": 171.651,
          "sharpness_score": 1.0,
          "luma_variance_score": 1.0,
          "fft_naturalness_score": 0.99744,
          "fft_high_frequency_ratio": 0.10424,
          "fft_peak_concentration": 0.08012,
          "fft_peak_to_mean": 38.681,
          "periodic_artifact_penalty": 0.00301,
          "lbp_naturalness_score": 1.0,
          "lbp_entropy": 5.897,
          "lbp_peak_fraction": 0.09978
        },
        "color_signals": {
          "chroma_variance_score": 1.0,
          "channel_spread_score": 1.0,
          "luminance_variance_score": 1.0,
          "skin_chroma_fraction": 0.97479,
          "gamut_score": 1.0
        }
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-30T02:33:17.704614+00:00",
    "diagnostic_id": "715fe939-66e5-43f6-983e-5a1d791e517f",
    "session_id": "299a5df8-afb5-4a92-832c-2f1a43725aac",
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
    "timestamp": "2026-10-30T02:33:17.709962+00:00",
    "diagnostic_id": "715fe939-66e5-43f6-983e-5a1d791e517f",
    "session_id": "299a5df8-afb5-4a92-832c-2f1a43725aac",
    "stage": "module3_risk",
    "values": {
      "risk_score": 0.229756,
      "risk_threshold": 0.5,
      "pass_threshold": true,
      "risk_level": "LOW",
      "signal_breakdown": {
        "liveness": 0.015682,
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
    "timestamp": "2026-10-30T02:33:17.710195+00:00",
    "diagnostic_id": "715fe939-66e5-43f6-983e-5a1d791e517f",
    "session_id": "299a5df8-afb5-4a92-832c-2f1a43725aac",
    "stage": "decision",
    "values": {
      "checkin_id": "5a381314-889b-44d4-b38b-51a80669ffdd",
      "status": "approved",
      "risk_score": 0.1298,
      "venue_risk_score": 0.043,
      "module3_risk_score": 0.12975599999999998,
      "effective_threshold": 0.5,
      "distance_meters": 8.6,
      "radius_meters": 100.0,
      "accuracy_meters": 40.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.937271,
      "face_match_passed": true,
      "face_match_score": 0.9037036276176811,
      "reason": "below_threshold"
    }
  },
  {
    "timestamp": "2026-10-30T02:33:18.830009+00:00",
    "diagnostic_id": "715fe939-66e5-43f6-983e-5a1d791e517f",
    "session_id": "299a5df8-afb5-4a92-832c-2f1a43725aac",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "5a381314-889b-44d4-b38b-51a80669ffdd",
      "status": "approved",
      "risk_score": 0.1298
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
