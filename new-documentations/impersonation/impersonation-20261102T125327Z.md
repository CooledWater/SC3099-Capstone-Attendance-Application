

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-02T20:59:12+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / 58ff4408-6b03-47bd-928e-66ecbfaabbd6

Expected genuine identity acceptance. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.99338 | 0.998253 | not used | evaluated | 0.999986 | True |
| last_frame | yes | 1.0 | 0.99462 | 0.998303 | not used | evaluated | 0.999973 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.8518517347964324 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.15185173479643244 |
| Identity comparisons performed | 12 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.158203 |
| Maximum accepted differing bits | 40 |
| Minimum observed differing bits | 6 |
| Maximum observed differing bits | 20 |
| Bit margin below acceptance limit | 20 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 64 | True | True | 6 | 0.0234375 | 0.9555555204389297 | True |
| 8 | 804 | True | True | 12 | 0.046875 | 0.9111110408778594 | True |
| 16 | 1546 | True | True | 10 | 0.0390625 | 0.9259258673982163 | True |
| 24 | 2292 | True | True | 14 | 0.0546875 | 0.8962962143575026 | True |
| 32 | 3034 | True | True | 14 | 0.0546875 | 0.8962962143575026 | True |
| 40 | 3782 | True | True | 12 | 0.046875 | 0.9111110408778594 | True |
| 48 | 4530 | True | True | 18 | 0.0703125 | 0.8666665613167892 | True |
| 55 | 5187 | True | True | 20 | 0.078125 | 0.8518517347964324 | True |
| 56 | 5280 | True | True | 19 | 0.07421875 | 0.8592591480566107 | True |
| 64 | 6022 | True | True | 16 | 0.0625 | 0.8814813878371459 | True |
| 72 | 6773 | True | True | 17 | 0.06640625 | 0.8740739745769676 | True |
| 75 | 7052 | True | True | 14 | 0.0546875 | 0.8962962143575026 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.1185 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.11851861216285409 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.1185 |

```json
[
  {
    "timestamp": "2026-11-02T12:57:58.669359+00:00",
    "diagnostic_id": "a71146b3-f20e-4eed-857c-74d01f609b1e",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  },
  {
    "timestamp": "2026-11-02T12:58:09.995459+00:00",
    "diagnostic_id": "972f6305-b121-4223-8994-836ed422914d",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  },
  {
    "timestamp": "2026-11-02T12:58:14.154563+00:00",
    "diagnostic_id": "972f6305-b121-4223-8994-836ed422914d",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.998253,
      "face_match_score": 0.8518517347964324,
      "diagnostics": {
        "frame_count": 76,
        "processed_frames": 76,
        "duration_ms": 6988,
        "last_frame_index": 75,
        "last_timestamp_ms": 7052,
        "identity_checks": 12,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.158203,
        "max_accepted_hamming_distance": 40,
        "max_hamming_distance": 20,
        "min_hamming_distance": 6,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 64,
            "match_score": 0.9555555204389297,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 6,
            "hamming_fraction": 0.0234375
          },
          {
            "frame_index": 8,
            "timestamp_ms": 804,
            "match_score": 0.9111110408778594,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1546,
            "match_score": 0.9259258673982163,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 10,
            "hamming_fraction": 0.0390625
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2292,
            "match_score": 0.8962962143575026,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 32,
            "timestamp_ms": 3034,
            "match_score": 0.8962962143575026,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 40,
            "timestamp_ms": 3782,
            "match_score": 0.9111110408778594,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 48,
            "timestamp_ms": 4530,
            "match_score": 0.8666665613167892,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 18,
            "hamming_fraction": 0.0703125
          },
          {
            "frame_index": 55,
            "timestamp_ms": 5187,
            "match_score": 0.8518517347964324,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 20,
            "hamming_fraction": 0.078125
          },
          {
            "frame_index": 56,
            "timestamp_ms": 5280,
            "match_score": 0.8592591480566107,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 19,
            "hamming_fraction": 0.07421875
          },
          {
            "frame_index": 64,
            "timestamp_ms": 6022,
            "match_score": 0.8814813878371459,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 16,
            "hamming_fraction": 0.0625
          },
          {
            "frame_index": 72,
            "timestamp_ms": 6773,
            "match_score": 0.8740739745769676,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 17,
            "hamming_fraction": 0.06640625
          },
          {
            "frame_index": 75,
            "timestamp_ms": 7052,
            "match_score": 0.8962962143575026,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
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
          "timestamp_ms": 64,
          "liveness_passed": true,
          "liveness_score": 0.998253,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.95573,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.99338,
            "texture_analysis_score": 0.99989,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.998316,
            "presentation_integrity_score": 0.999937,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.998253,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.248344,
              "texture": 0.249971,
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
              "texture_diversity": 0.999937,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999986,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999996,
            "pad_v1se_live_score": 0.999976,
            "pre_pad_liveness_score": 0.998253,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 14.517,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 75,
          "timestamp_ms": 7052,
          "liveness_passed": true,
          "liveness_score": 0.998303,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.89982,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.99462,
            "texture_analysis_score": 0.99956,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.998545,
            "presentation_integrity_score": 0.999758,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.998303,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.248655,
              "texture": 0.24989,
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
              "texture_diversity": 0.999758,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999973,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999975,
            "pad_v1se_live_score": 0.999972,
            "pre_pad_liveness_score": 0.998303,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 16.113,
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
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  },
  {
    "timestamp": "2026-11-02T12:58:14.602790+00:00",
    "diagnostic_id": "972f6305-b121-4223-8994-836ed422914d",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.998253,
      "face_match_score": 0.8518517347964324
    },
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  },
  {
    "timestamp": "2026-11-02T12:58:20.407207+00:00",
    "diagnostic_id": "588f68b7-b4dc-40cf-bae9-3918b21bddc4",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  },
  {
    "timestamp": "2026-11-02T12:58:23.404012+00:00",
    "diagnostic_id": "588f68b7-b4dc-40cf-bae9-3918b21bddc4",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "decision",
    "values": {
      "checkin_id": "99a255f4-0bc5-4d86-a6ec-100ad8158c80",
      "status": "approved",
      "risk_score": 0.1185,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.11851861216285409,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 59.856353759765625,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.998253,
      "face_match_passed": true,
      "face_match_score": 0.8518517347964324,
      "reason": "below_threshold"
    },
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  },
  {
    "timestamp": "2026-11-02T12:58:24.153596+00:00",
    "diagnostic_id": "588f68b7-b4dc-40cf-bae9-3918b21bddc4",
    "session_id": "1348cc30-b1ac-47cb-8532-de9058c221fa",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "99a255f4-0bc5-4d86-a6ec-100ad8158c80",
      "status": "approved",
      "risk_score": 0.1185
    },
    "challenge_id": "58ff4408-6b03-47bd-928e-66ecbfaabbd6"
  }
]
```

### impersonation_test — student1@gmail.com / 685e5da8-4d0d-445e-83c2-68d9adb89547

Identity acceptance contrary to the expected mismatch: potential false acceptance, subject to account/presenter confirmation. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 0.91434 | 0.8687 | 0.941476 | not used | evaluated | 0.999981 | True |
| last_frame | yes | 0.89341 | 0.85659 | 0.93217 | not used | evaluated | 0.999977 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.7333331226335783 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.03333312263357835 |
| Identity comparisons performed | 6 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.158203 |
| Maximum accepted differing bits | 40 |
| Minimum observed differing bits | 31 |
| Maximum observed differing bits | 36 |
| Bit margin below acceptance limit | 4 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 70 | True | True | 31 | 0.12109375 | 0.7703701889344703 | True |
| 8 | 838 | True | True | 35 | 0.13671875 | 0.7407405358937568 | True |
| 14 | 1410 | True | True | 36 | 0.140625 | 0.7333331226335783 | True |
| 16 | 1597 | True | True | 33 | 0.12890625 | 0.7555553624141135 | True |
| 24 | 2350 | True | True | 33 | 0.12890625 | 0.7555553624141135 | True |
| 26 | 2542 | True | True | 34 | 0.1328125 | 0.7481479491539351 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.2133 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.21333350189313738 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.2133 |

```json
[
  {
    "timestamp": "2026-11-02T12:58:52.904984+00:00",
    "diagnostic_id": "1f9fda8a-ce32-403f-b6f3-916e6c2f8ffb",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  },
  {
    "timestamp": "2026-11-02T12:58:58.982032+00:00",
    "diagnostic_id": "b950159b-f2bb-4dd0-a678-ba0d616dd97b",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  },
  {
    "timestamp": "2026-11-02T12:59:01.231113+00:00",
    "diagnostic_id": "b950159b-f2bb-4dd0-a678-ba0d616dd97b",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.93217,
      "face_match_score": 0.7333331226335783,
      "diagnostics": {
        "frame_count": 27,
        "processed_frames": 27,
        "duration_ms": 2472,
        "last_frame_index": 26,
        "last_timestamp_ms": 2542,
        "identity_checks": 6,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.158203,
        "max_accepted_hamming_distance": 40,
        "max_hamming_distance": 36,
        "min_hamming_distance": 31,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 70,
            "match_score": 0.7703701889344703,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 31,
            "hamming_fraction": 0.12109375
          },
          {
            "frame_index": 8,
            "timestamp_ms": 838,
            "match_score": 0.7407405358937568,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 35,
            "hamming_fraction": 0.13671875
          },
          {
            "frame_index": 14,
            "timestamp_ms": 1410,
            "match_score": 0.7333331226335783,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 36,
            "hamming_fraction": 0.140625
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1597,
            "match_score": 0.7555553624141135,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 33,
            "hamming_fraction": 0.12890625
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2350,
            "match_score": 0.7555553624141135,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 33,
            "hamming_fraction": 0.12890625
          },
          {
            "frame_index": 26,
            "timestamp_ms": 2542,
            "match_score": 0.7481479491539351,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 34,
            "hamming_fraction": 0.1328125
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
          "timestamp_ms": 70,
          "liveness_passed": true,
          "liveness_score": 0.941476,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.93811,
            "depth_score": 0.91434,
            "mesh_plausibility_score": 0.8687,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.941476,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.941476,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.274301,
              "mesh": 0.217174,
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
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999981,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999999,
            "pad_v1se_live_score": 0.999963,
            "pre_pad_liveness_score": 0.941476,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 17.458,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 26,
          "timestamp_ms": 2542,
          "liveness_passed": true,
          "liveness_score": 0.93217,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.93672,
            "depth_score": 0.89341,
            "mesh_plausibility_score": 0.85659,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.93217,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.93217,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.268023,
              "mesh": 0.214147,
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
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999977,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999997,
            "pad_v1se_live_score": 0.999956,
            "pre_pad_liveness_score": 0.93217,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 13.006,
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
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  },
  {
    "timestamp": "2026-11-02T12:59:01.577214+00:00",
    "diagnostic_id": "b950159b-f2bb-4dd0-a678-ba0d616dd97b",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.93217,
      "face_match_score": 0.7333331226335783
    },
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  },
  {
    "timestamp": "2026-11-02T12:59:07.281602+00:00",
    "diagnostic_id": "fe4a5dcb-7830-4a0b-9b1b-c064fbf51232",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  },
  {
    "timestamp": "2026-11-02T12:59:10.077744+00:00",
    "diagnostic_id": "fe4a5dcb-7830-4a0b-9b1b-c064fbf51232",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "decision",
    "values": {
      "checkin_id": "b9c0b3da-7ab5-4a64-9e88-1c9e81b34aef",
      "status": "approved",
      "risk_score": 0.2133,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.21333350189313738,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 50.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.93217,
      "face_match_passed": true,
      "face_match_score": 0.7333331226335783,
      "reason": "below_threshold"
    },
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  },
  {
    "timestamp": "2026-11-02T12:59:10.993707+00:00",
    "diagnostic_id": "fe4a5dcb-7830-4a0b-9b1b-c064fbf51232",
    "session_id": "39f68409-ad81-4403-abbb-982b53fd6fd1",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "b9c0b3da-7ab5-4a64-9e88-1c9e81b34aef",
      "status": "approved",
      "risk_score": 0.2133
    },
    "challenge_id": "685e5da8-4d0d-445e-83c2-68d9adb89547"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
