

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-03T09:18:48+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / 6e6af5e4-c7d5-4a08-955f-3cfe66896e39

Expected genuine identity acceptance. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.97602 | 0.991478 | not used | evaluated | 0.999918 | True |
| last_frame | yes | 1.0 | 0.97598 | 0.988196 | not used | evaluated | 0.999914 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.7652173913043478 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.0652173913043479 |
| Identity comparisons performed | 5 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 12 |
| Maximum observed differing bits | 18 |
| Bit margin below acceptance limit | 5 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 14 | True | True | 15 | 0.05859375 | 0.8043478260869565 | True |
| 8 | 755 | True | True | 18 | 0.0703125 | 0.7652173913043478 | True |
| 9 | 848 | True | True | 15 | 0.05859375 | 0.8043478260869565 | True |
| 16 | 1496 | True | True | 13 | 0.05078125 | 0.8304347826086956 | True |
| 19 | 1775 | True | True | 12 | 0.046875 | 0.8434782608695652 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.1878 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.18782608695652173 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.1878 |

```json
[
  {
    "timestamp": "2026-11-03T01:17:09.009145+00:00",
    "diagnostic_id": "5c717ad8-05fc-4c17-964b-d16bcb097d6e",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  },
  {
    "timestamp": "2026-11-03T01:17:15.687155+00:00",
    "diagnostic_id": "9030ca9d-7208-424c-a1c0-1aaac4a8fa89",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  },
  {
    "timestamp": "2026-11-03T01:17:19.141740+00:00",
    "diagnostic_id": "9030ca9d-7208-424c-a1c0-1aaac4a8fa89",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.988196,
      "face_match_score": 0.7652173913043478,
      "diagnostics": {
        "frame_count": 20,
        "processed_frames": 20,
        "duration_ms": 1761,
        "last_frame_index": 19,
        "last_timestamp_ms": 1775,
        "identity_checks": 5,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 18,
        "min_hamming_distance": 12,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 14,
            "match_score": 0.8043478260869565,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 15,
            "hamming_fraction": 0.05859375
          },
          {
            "frame_index": 8,
            "timestamp_ms": 755,
            "match_score": 0.7652173913043478,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 18,
            "hamming_fraction": 0.0703125
          },
          {
            "frame_index": 9,
            "timestamp_ms": 848,
            "match_score": 0.8043478260869565,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 15,
            "hamming_fraction": 0.05859375
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1496,
            "match_score": 0.8304347826086956,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 13,
            "hamming_fraction": 0.05078125
          },
          {
            "frame_index": 19,
            "timestamp_ms": 1775,
            "match_score": 0.8434782608695652,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          }
        ],
        "matcher_version": "dlib128-simhash256-v1",
        "score_mapping_version": "piecewise-hamming-v1",
        "liveness_threshold": 0.85,
        "ear_closed_threshold": 0.19,
        "ear_open_threshold": 0.23,
        "min_closure_ms": 40,
        "max_closure_ms": 700,
        "first_frame": {
          "evaluated": true,
          "frame_index": 0,
          "timestamp_ms": 14,
          "liveness_passed": true,
          "liveness_score": 0.991478,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.92571,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.97602,
            "texture_analysis_score": 0.99902,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.993761,
            "presentation_integrity_score": 0.997702,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.991478,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.244006,
              "texture": 0.249756,
              "color": 0.2
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.997702,
              "texture_diversity": 0.999462,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.00383
            },
            "pad_live_score": 0.999918,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999912,
            "pad_v1se_live_score": 0.999924,
            "pre_pad_liveness_score": 0.991478,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 26.196,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 19,
          "timestamp_ms": 1775,
          "liveness_passed": true,
          "liveness_score": 0.988196,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.93076,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.97598,
            "texture_analysis_score": 0.99776,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.993436,
            "presentation_integrity_score": 0.994726,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.988196,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.243996,
              "texture": 0.24944,
              "color": 0.2
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.994726,
              "texture_diversity": 0.998767,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.00879
            },
            "pad_live_score": 0.999914,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999912,
            "pad_v1se_live_score": 0.999916,
            "pre_pad_liveness_score": 0.988196,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 20.857,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "reason": "passed"
      },
      "outcome": "received",
      "http_status": 200
    },
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  },
  {
    "timestamp": "2026-11-03T01:17:19.767277+00:00",
    "diagnostic_id": "9030ca9d-7208-424c-a1c0-1aaac4a8fa89",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.988196,
      "face_match_score": 0.7652173913043478
    },
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  },
  {
    "timestamp": "2026-11-03T01:17:27.917240+00:00",
    "diagnostic_id": "05c3eeaa-7ea3-4f49-b977-65ec57befdf2",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  },
  {
    "timestamp": "2026-11-03T01:17:32.408120+00:00",
    "diagnostic_id": "05c3eeaa-7ea3-4f49-b977-65ec57befdf2",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "decision",
    "values": {
      "checkin_id": "594da818-ed8a-41e1-a8eb-773633057136",
      "status": "approved",
      "risk_score": 0.1878,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.18782608695652173,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.988196,
      "face_match_passed": true,
      "face_match_score": 0.7652173913043478,
      "reason": "below_threshold"
    },
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  },
  {
    "timestamp": "2026-11-03T01:17:33.658972+00:00",
    "diagnostic_id": "05c3eeaa-7ea3-4f49-b977-65ec57befdf2",
    "session_id": "13df319d-4ea3-4944-b80c-b38a88745703",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "594da818-ed8a-41e1-a8eb-773633057136",
      "status": "approved",
      "risk_score": 0.1878
    },
    "challenge_id": "6e6af5e4-c7d5-4a08-955f-3cfe66896e39"
  }
]
```

### impersonation_test — student1@gmail.com / e30d9531-5d03-4186-b1c5-b2938acad17b

Identity mismatch observed; expected impersonation rejection. No attendance commit is required.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | not evaluated | — | — | — | — | not evaluated | — | — |
| last_frame | not evaluated | — | — | — | — | not evaluated | — | — |

Sequence stop reason: identity_failed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.5933333333333333 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | -0.10666666666666669 |
| Identity comparisons performed | 1 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 39 |
| Maximum observed differing bits | 39 |
| Bit margin below acceptance limit | -16 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 28 | True | True | 39 | 0.15234375 | 0.5933333333333333 | False |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | unknown |
| Decision reason | unknown |
| Final risk score | unknown |
| Effective risk threshold | unknown |
| Venue risk score | unknown |
| Module 3 risk score (at decision) | unknown |
| Saved attendance status | unknown |
| Saved attendance risk score | unknown |

```json
[
  {
    "timestamp": "2026-11-03T01:18:35.325053+00:00",
    "diagnostic_id": "5529a428-3628-44b4-b381-c2d6aed52720",
    "session_id": "4225fe43-cc55-47d3-b699-c30d5419a998",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "e30d9531-5d03-4186-b1c5-b2938acad17b"
  },
  {
    "timestamp": "2026-11-03T01:18:43.746031+00:00",
    "diagnostic_id": "ee002b0f-6400-4b26-97d1-8cd9de0b479a",
    "session_id": "4225fe43-cc55-47d3-b699-c30d5419a998",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "e30d9531-5d03-4186-b1c5-b2938acad17b"
  },
  {
    "timestamp": "2026-11-03T01:18:46.092376+00:00",
    "diagnostic_id": "ee002b0f-6400-4b26-97d1-8cd9de0b479a",
    "session_id": "4225fe43-cc55-47d3-b699-c30d5419a998",
    "stage": "motion_sequence",
    "values": {
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.5933333333333333,
      "diagnostics": {
        "frame_count": 21,
        "processed_frames": 1,
        "duration_ms": 1896,
        "last_frame_index": 0,
        "last_timestamp_ms": 28,
        "identity_checks": 1,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 39,
        "min_hamming_distance": 39,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 28,
            "match_score": 0.5933333333333333,
            "match_passed": false,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 39,
            "hamming_fraction": 0.15234375
          }
        ],
        "matcher_version": "dlib128-simhash256-v1",
        "score_mapping_version": "piecewise-hamming-v1",
        "liveness_threshold": 0.85,
        "ear_closed_threshold": 0.19,
        "ear_open_threshold": 0.23,
        "min_closure_ms": 40,
        "max_closure_ms": 700,
        "first_frame": {
          "evaluated": false
        },
        "last_frame": {
          "evaluated": false
        },
        "reason": "identity_failed"
      },
      "outcome": "received",
      "http_status": 200
    },
    "challenge_id": "e30d9531-5d03-4186-b1c5-b2938acad17b"
  },
  {
    "timestamp": "2026-11-03T01:18:46.616531+00:00",
    "diagnostic_id": "ee002b0f-6400-4b26-97d1-8cd9de0b479a",
    "session_id": "4225fe43-cc55-47d3-b699-c30d5419a998",
    "stage": "motion_verified",
    "values": {
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.5933333333333333
    },
    "challenge_id": "e30d9531-5d03-4186-b1c5-b2938acad17b"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
