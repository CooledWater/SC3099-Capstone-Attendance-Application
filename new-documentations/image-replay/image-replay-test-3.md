# Phone image replay test 3 — 30 October 2026

State: **stopped for participant-requested retry; genuine control rejected by multiple-face guard; phone-photo trial not submitted. Diagnostics disabled and allowlist cleared.**

## Scope and matched sessions

Account `wcstudent1@example.com` is active, actively enrolled in SC4000, face enrolled, and has camera/geolocation consent. Eligibility was verified by scalar-only projection without retrieving templates or credentials. Participant performs both captures manually. No operator attendance submission or enrollment, template, consent, location, device trust, threshold or recognition algorithm changes are made. Attendance and audit records are preserved.

Venue **LT26**, catalogue coordinates 1.3434326, 103.6815837; radius 100.0 m; risk threshold 0.5. Both lecture sessions permit single-photo capture (`require_motion_check=false`) and require passive liveness and enrolled-face matching. Scheduled and check-in windows are identical, exactly two hours: **2026-10-30T10:21:05+08:00** to **2026-10-30T12:21:05+08:00**.

| Presentation | Name | Session ID |
| --- | --- | --- |
| real_face_control | Image replay R3 CONTROL real face (30 Oct 10:21 SGT) | `715523e9-a1a3-49cc-9c21-7b404ef49b01` |
| phone_screen | Image replay R3 TEST static phone photo (30 Oct 10:21 SGT) | `ccbd4379-1703-41a1-844c-7f2d54a890c5` |

Both sessions were independently confirmed active before inviting captures. Both creations returned HTTP 201. Authenticated student readback verified matched policies/venue and zero existing attendance for each session. Tokens were transient and never saved.

## Conditions

Capture device/browser, lighting, display brightness, camera distance and visible borders/reflections: **unknown**, as requested by the participant. Session labels alone do not prove physical presentation. No captures are inspected or retained.

## Baseline and checks

Reviewed AGENTS.md, relevant source paths across all four modules, existing scalar instrumentation and monitor, historical image reports and latest video report, and session/check-in/integration/database contracts. `docs/` remains read-only. A temporary SHA-256 preservation manifest covers 84 existing source/document/report/config files. Existing working-tree changes predate this run and remain untouched.

Existing monitor and scalar instrumentation tests in a network-disabled disposable container: **22 passed, 6 deselected**, two harmless pytest cache warnings because the repository was mounted read-only. Live attendance-producing integration tests were excluded. Backend and face-service diagnostics started disabled with empty allowlists. Running thresholds: liveness 0.85, depth 0.80, mesh 0.80, identity 0.70, risk 0.50; strict mode false. All nine deployed backend/face-service source hashes match local source; no rebuild was needed. After backend recreation, its four instrumentation hashes still match. Both health endpoints returned HTTP 200. Backend diagnostics are enabled for exactly these two new IDs; face-service diagnostics remain disabled with an empty allowlist. The monitor emitted MONITOR_READY before inviting captures.

Only fixed-schema session-scoped scalar diagnostics are retained. No raw images, video, base64 payloads, landmarks, biometric templates, credentials or unfiltered Docker logs are saved.

## Verified real-face control

The participant confirmed the real-face capture in chat. Six diagnostic stages for attempt `a619868f-7540-495b-91c4-e8463f1c5f26` correlate to committed check-in `e9ba7187-0ffa-46ee-b40d-db2879da4e8f`, the intended student and control session. Saved at **10:22:06.691567 SGT**, attendance is **rejected**, final risk **0.5900**. Authenticated my-checkins and detail endpoints returned HTTP 200 and agree with an independent scalar-only database ownership/score projection. Both preserved audit events were verified: `checkin_attempted` (`21b0db76-dc34-4143-a820-e0f2b9187413`, success true) and `checkin_rejected` (`d84f287c-42ee-4431-a1aa-82180ff9eb8d`, success false, recording the rejected outcome). This is committed attendance, not only a calculated decision.

The liveness service returned a usable HTTP 200 response with **multiple_faces=true**, detection confidence **0.911398**, and failed liveness **0.0 / 0.85**. Source review confirms that this face-count guard returns before embedding extraction and component-based liveness analysis. Therefore depth, mesh, texture, color and challenge scores reported as zero, incomplete mesh, absent depth and failed geometry flags are **early-return defaults, not measured component failures**. Weighted contributions, presentation integrity and periodic-artifact penalties were not evaluated and remain **unavailable**. The detector reported multiple faces; no image was inspected to establish whether this represented another person, background content or a detector false positive.

Face verification returned usable HTTP 200, `face_detected=true`, match false and score **0.0 / 0.70**. Its existing multiple-face branch also returns before template comparison. In this observed context the zero is a rejection sentinel, not evidence of measured identity dissimilarity. The service calls ran and rejected the presentation; downstream component/identity comparisons were not performed. This is distinct from an unavailable service.

| Measurement | Real-face control | Phone-photo presentation |
| --- | --- | --- |
| Detection guard | multiple faces reported | pending |
| Depth / mesh / texture / color | not evaluated; default zeros | pending |
| Presentation integrity / periodic penalty | unavailable; not evaluated | pending |
| Passive liveness verdict / threshold | false, 0.0 / 0.85; face-count rejection | pending |
| Identity verdict / threshold | false, sentinel 0.0 / 0.70; comparison not evaluated | pending |
| Module 3 liveness contribution | 0.250000 | pending |
| Module 3 identity contribution | 0.250000 | pending |
| Module 3 placeholder device contribution | 0.100000 | pending |
| Module 3 network contribution | 0.075000 | pending |
| Module 3 geolocation contribution | 0.015000 | pending |
| Module 3 service total | 0.690000 | pending |
| Backend-adjusted Module 3 total | 0.590000 | pending |
| Venue risk / distance / radius | 0.0337 / 6.74 m / 100 m | pending |
| Reported location accuracy | 40 m | pending |
| Final risk / threshold | 0.5900 / 0.50 | pending |
| Saved attendance | rejected | pending |

Existing backend device policy replaces the placeholder device contribution: observed risk changes from **0.69** to **0.59**, consistent with replacing **0.10** by **0.00**. Final risk is `round(max(0.0337, 0.59), 4) = 0.5900`. Saved risk factors are `liveness_failed` (high, weight 1.0) and `face_match_failed` (critical, weight 1.0); diagnostic decision reason is `liveness_failed`. The service's neutral device/network contributions do not themselves prove successful checks. No device policy or trust state was altered by the operator.

This participant-reported genuine control failed the face-count guard, so it does not establish a successful genuine-face baseline for component comparison. No replay conclusion can be drawn before the phone-photo trial, and component differences cannot be inferred from these default zeros. Keep this observed control result rather than replacing it or altering attendance. All capture conditions remain unknown at participant request.

After correlation, the monitor remained running, backend health returned HTTP 200, and diagnostics remained enabled for exactly the two new IDs. The phone-photo session was independently confirmed active until **12:21:05 SGT**, with zero saved attendance at that readback. Cleanup remains pending the second manual submission or a participant stop request.

## Interpretation and specification gaps

Unavailable or unperformed checks remain unknown; they are not genuine passes. Calculated decisions must be correlated to saved attendance through authenticated readback and scalar database/audit projections. Compare liveness components and gates, presentation penalties, identity score, Module 3 contributions, venue and final risk, and saved status after each capture. Model-inferred depth/mesh do not establish physical depth. Neutral device/network scores do not establish successful checks. Conclusions are limited to this observed pair.

Existing gaps: the session-create documentation example uses `session_name`, while the deployed API accepts `name`; documentation's older liveness example uses 0.60 while deployed policy is 0.85 with 0.80 geometry gates. Non-strict outages must be treated as unavailable even if attendance saves. Device policy can independently flag attendance and modify Module 3/final risk. The monitor's generic maximum-risk sentence omits that device adjustment; the report's correlation will use the actual source and saved risk factors. Diagnostic `decision.reason=risk_threshold` may label device flags below the cutoff. No code or documentation change is proposed for these existing gaps.

## Endpoints reused

`POST /api/v1/sessions/`, `GET /api/v1/sessions/{id}`, `GET /api/v1/sessions/active`, `GET /api/v1/checkins/my-checkins`, `GET /api/v1/checkins/{id}`, backend/face-service `GET /health`. Participant-only `POST /api/v1/checkins/` calls the existing internal `/liveness/check`, `/face/verify` and `/risk/assess`. No endpoint implemented.

## Monitoring and cleanup

Use new configuration `new-tests/phone-image-replay-20261030T021935Z.json` and this report with the existing image-mode monitor. Enable backend diagnostics only for the two IDs above; face-service diagnostics remain disabled. The monitor has a 125-minute safety timeout and automatically attempts disabled diagnostics/empty backend allowlist after both commits, interruption or timeout. Independently verify runtime flags and health, then finalize this report. Attendance and audit records remain preserved.

## Run stopped for retry

Participant requested another genuine single-photo check-in because the multiple-face guard does not address the intended comparison. The operator gracefully stopped this run's monitor, which disabled backend diagnostics and cleared its allowlist. Both flag assertions passed. The immediate health probe met a transient startup connection refusal during recreation; the subsequent preflight verified backend and face-service health HTTP 200. The existing rejected attendance and its two audit events were independently verified preserved before preparing the next run. No phone-photo outcome was observed in this run. This is an incomplete comparison, not evidence of replay resistance. A fresh matched pair and report 4 continue the requested test; report 3 and its observations remain intact.

## Files changed

Added `new-tests/phone-image-replay-20261030T021935Z.json` and this report only. No existing source or report is modified by this run.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **monitor stopped by operator; incomplete tests remain pending; diagnostics disabled**.

Updated: 2026-10-30T10:26:02+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### real_face_control / a619868f-7540-495b-91c4-e8463f1c5f26

Passive liveness rejected this capture.

The final risk is the maximum of venue risk and Module 3 risk; a liveness failure can independently reject attendance.

```json
[
  {
    "timestamp": "2026-10-30T02:22:05.722291+00:00",
    "diagnostic_id": "a619868f-7540-495b-91c4-e8463f1c5f26",
    "session_id": "715523e9-a1a3-49cc-9c21-7b404ef49b01",
    "stage": "attempt_started",
    "values": {}
  },
  {
    "timestamp": "2026-10-30T02:22:10.552098+00:00",
    "diagnostic_id": "a619868f-7540-495b-91c4-e8463f1c5f26",
    "session_id": "715523e9-a1a3-49cc-9c21-7b404ef49b01",
    "stage": "liveness",
    "values": {
      "liveness_passed": false,
      "liveness_score": 0.0,
      "liveness_threshold": 0.85,
      "challenge_type": "passive",
      "details": {
        "face_detection_confidence": 0.911398,
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
        "multiple_faces": true,
        "landmark_count": 0,
        "depth_quality": "poor"
      },
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-30T02:22:10.581053+00:00",
    "diagnostic_id": "a619868f-7540-495b-91c4-e8463f1c5f26",
    "session_id": "715523e9-a1a3-49cc-9c21-7b404ef49b01",
    "stage": "face_match",
    "values": {
      "match_passed": false,
      "match_score": 0.0,
      "match_threshold": 0.7,
      "face_detected": true,
      "outcome": "received",
      "http_status": 200
    }
  },
  {
    "timestamp": "2026-10-30T02:22:10.582232+00:00",
    "diagnostic_id": "a619868f-7540-495b-91c4-e8463f1c5f26",
    "session_id": "715523e9-a1a3-49cc-9c21-7b404ef49b01",
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
    "timestamp": "2026-10-30T02:22:10.582341+00:00",
    "diagnostic_id": "a619868f-7540-495b-91c4-e8463f1c5f26",
    "session_id": "715523e9-a1a3-49cc-9c21-7b404ef49b01",
    "stage": "decision",
    "values": {
      "checkin_id": "e9ba7187-0ffa-46ee-b40d-db2879da4e8f",
      "status": "rejected",
      "risk_score": 0.59,
      "venue_risk_score": 0.0337,
      "module3_risk_score": 0.59,
      "effective_threshold": 0.5,
      "distance_meters": 6.74,
      "radius_meters": 100.0,
      "accuracy_meters": 40.0,
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
    "timestamp": "2026-10-30T02:22:11.657236+00:00",
    "diagnostic_id": "a619868f-7540-495b-91c4-e8463f1c5f26",
    "session_id": "715523e9-a1a3-49cc-9c21-7b404ef49b01",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "e9ba7187-0ffa-46ee-b40d-db2879da4e8f",
      "status": "rejected",
      "risk_score": 0.59
    }
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
