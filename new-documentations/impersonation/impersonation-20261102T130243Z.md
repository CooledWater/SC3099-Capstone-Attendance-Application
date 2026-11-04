

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-02T21:05:56+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / fc006570-2a9a-4348-8e41-06bfca7491b3

Expected genuine identity acceptance. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.98867 | 0.99716 | not used | evaluated | 0.999915 | True |
| last_frame | yes | 1.0 | 0.98829 | 0.997046 | not used | evaluated | 0.999847 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.8666665613167892 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.16666656131678925 |
| Identity comparisons performed | 6 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.158203 |
| Maximum accepted differing bits | 40 |
| Minimum observed differing bits | 15 |
| Maximum observed differing bits | 18 |
| Bit margin below acceptance limit | 22 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 43 | True | True | 15 | 0.05859375 | 0.8888888010973244 | True |
| 8 | 789 | True | True | 17 | 0.06640625 | 0.8740739745769676 | True |
| 16 | 1502 | True | True | 17 | 0.06640625 | 0.8740739745769676 | True |
| 19 | 1783 | True | True | 16 | 0.0625 | 0.8814813878371459 | True |
| 24 | 2244 | True | True | 18 | 0.0703125 | 0.8666665613167892 | True |
| 29 | 2707 | True | True | 17 | 0.06640625 | 0.8740739745769676 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.1067 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.10666675094656863 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.1067 |

```json
[
  {
    "timestamp": "2026-11-02T13:04:49.338307+00:00",
    "diagnostic_id": "53ca89a8-8c85-4779-9c0a-054236936653",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  },
  {
    "timestamp": "2026-11-02T13:04:55.989706+00:00",
    "diagnostic_id": "cb3efae6-d6af-4c81-98d5-22e6f56ebbcf",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  },
  {
    "timestamp": "2026-11-02T13:04:58.906214+00:00",
    "diagnostic_id": "cb3efae6-d6af-4c81-98d5-22e6f56ebbcf",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.997046,
      "face_match_score": 0.8666665613167892,
      "diagnostics": {
        "frame_count": 30,
        "processed_frames": 30,
        "duration_ms": 2664,
        "last_frame_index": 29,
        "last_timestamp_ms": 2707,
        "identity_checks": 6,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.158203,
        "max_accepted_hamming_distance": 40,
        "max_hamming_distance": 18,
        "min_hamming_distance": 15,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 43,
            "match_score": 0.8888888010973244,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 15,
            "hamming_fraction": 0.05859375
          },
          {
            "frame_index": 8,
            "timestamp_ms": 789,
            "match_score": 0.8740739745769676,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 17,
            "hamming_fraction": 0.06640625
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1502,
            "match_score": 0.8740739745769676,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 17,
            "hamming_fraction": 0.06640625
          },
          {
            "frame_index": 19,
            "timestamp_ms": 1783,
            "match_score": 0.8814813878371459,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 16,
            "hamming_fraction": 0.0625
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2244,
            "match_score": 0.8666665613167892,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 18,
            "hamming_fraction": 0.0703125
          },
          {
            "frame_index": 29,
            "timestamp_ms": 2707,
            "match_score": 0.8740739745769676,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 17,
            "hamming_fraction": 0.06640625
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
          "timestamp_ms": 43,
          "liveness_passed": true,
          "liveness_score": 0.99716,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.90962,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.98867,
            "texture_analysis_score": 0.99999,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.997166,
            "presentation_integrity_score": 0.999994,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.99716,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.247168,
              "texture": 0.249997,
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
              "texture_diversity": 0.999994,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999915,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999997,
            "pad_v1se_live_score": 0.999832,
            "pre_pad_liveness_score": 0.99716,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 7.773,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 29,
          "timestamp_ms": 2707,
          "liveness_passed": true,
          "liveness_score": 0.997046,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.89166,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.98829,
            "texture_analysis_score": 0.99997,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.997064,
            "presentation_integrity_score": 0.999982,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.997046,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.247072,
              "texture": 0.249992,
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
              "texture_diversity": 0.999982,
              "color_diversity": 1.0
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999847,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999996,
            "pad_v1se_live_score": 0.999697,
            "pre_pad_liveness_score": 0.997046,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 11.448,
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
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  },
  {
    "timestamp": "2026-11-02T13:04:59.259054+00:00",
    "diagnostic_id": "cb3efae6-d6af-4c81-98d5-22e6f56ebbcf",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.997046,
      "face_match_score": 0.8666665613167892
    },
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  },
  {
    "timestamp": "2026-11-02T13:05:04.726168+00:00",
    "diagnostic_id": "6a0bb8a6-963b-40a7-a511-4dea361238c9",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  },
  {
    "timestamp": "2026-11-02T13:05:07.657405+00:00",
    "diagnostic_id": "6a0bb8a6-963b-40a7-a511-4dea361238c9",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "decision",
    "values": {
      "checkin_id": "784e1638-2476-49a7-883a-7574797547d9",
      "status": "approved",
      "risk_score": 0.1067,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.10666675094656863,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 45.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.997046,
      "face_match_passed": true,
      "face_match_score": 0.8666665613167892,
      "reason": "below_threshold"
    },
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  },
  {
    "timestamp": "2026-11-02T13:05:08.595787+00:00",
    "diagnostic_id": "6a0bb8a6-963b-40a7-a511-4dea361238c9",
    "session_id": "4ec3b453-8d5f-46a1-a011-96fe470bb954",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "784e1638-2476-49a7-883a-7574797547d9",
      "status": "approved",
      "risk_score": 0.1067
    },
    "challenge_id": "fc006570-2a9a-4348-8e41-06bfca7491b3"
  }
]
```

### impersonation_test — student1@gmail.com / a83a62ed-2fb1-4986-b9e2-129ddb48ae08

Identity acceptance contrary to the expected mismatch: potential false acceptance, subject to account/presenter confirmation. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 0.90398 | 0.8371 | 0.930469 | not used | evaluated | 0.999666 | True |
| last_frame | yes | 0.90622 | 0.83322 | 0.930172 | not used | evaluated | 0.999416 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.7185182961132216 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.018518296113221644 |
| Identity comparisons performed | 5 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.158203 |
| Maximum accepted differing bits | 40 |
| Minimum observed differing bits | 33 |
| Maximum observed differing bits | 38 |
| Bit margin below acceptance limit | 2 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 65 | True | True | 36 | 0.140625 | 0.7333331226335783 | True |
| 8 | 836 | True | True | 33 | 0.12890625 | 0.7555553624141135 | True |
| 11 | 1113 | True | True | 38 | 0.1484375 | 0.7185182961132216 | True |
| 16 | 1597 | True | True | 36 | 0.140625 | 0.7333331226335783 | True |
| 19 | 1885 | True | True | 36 | 0.140625 | 0.7333331226335783 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.2252 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.22518536310942272 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.2252 |

```json
[
  {
    "timestamp": "2026-11-02T13:05:38.180271+00:00",
    "diagnostic_id": "aaf3c522-94c8-4cd4-9ee2-3a7e418b9d09",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  },
  {
    "timestamp": "2026-11-02T13:05:43.939927+00:00",
    "diagnostic_id": "6a83dd55-c398-4bd2-b8f8-2f38820c57bb",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  },
  {
    "timestamp": "2026-11-02T13:05:46.041458+00:00",
    "diagnostic_id": "6a83dd55-c398-4bd2-b8f8-2f38820c57bb",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.930172,
      "face_match_score": 0.7185182961132216,
      "diagnostics": {
        "frame_count": 20,
        "processed_frames": 20,
        "duration_ms": 1820,
        "last_frame_index": 19,
        "last_timestamp_ms": 1885,
        "identity_checks": 5,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.158203,
        "max_accepted_hamming_distance": 40,
        "max_hamming_distance": 38,
        "min_hamming_distance": 33,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 65,
            "match_score": 0.7333331226335783,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 36,
            "hamming_fraction": 0.140625
          },
          {
            "frame_index": 8,
            "timestamp_ms": 836,
            "match_score": 0.7555553624141135,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 33,
            "hamming_fraction": 0.12890625
          },
          {
            "frame_index": 11,
            "timestamp_ms": 1113,
            "match_score": 0.7185182961132216,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 38,
            "hamming_fraction": 0.1484375
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1597,
            "match_score": 0.7333331226335783,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 36,
            "hamming_fraction": 0.140625
          },
          {
            "frame_index": 19,
            "timestamp_ms": 1885,
            "match_score": 0.7333331226335783,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 36,
            "hamming_fraction": 0.140625
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
          "timestamp_ms": 65,
          "liveness_passed": true,
          "liveness_score": 0.930469,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.94001,
            "depth_score": 0.90398,
            "mesh_plausibility_score": 0.8371,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.930469,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.930469,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.271194,
              "mesh": 0.209275,
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
            "pad_live_score": 0.999666,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999994,
            "pad_v1se_live_score": 0.999339,
            "pre_pad_liveness_score": 0.930469,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 13.63,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 19,
          "timestamp_ms": 1885,
          "liveness_passed": true,
          "liveness_score": 0.930172,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.9423,
            "depth_score": 0.90622,
            "mesh_plausibility_score": 0.83322,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.930172,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.930172,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.271866,
              "mesh": 0.208306,
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
            "pad_live_score": 0.999416,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999987,
            "pad_v1se_live_score": 0.998844,
            "pre_pad_liveness_score": 0.930172,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 10.959,
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
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  },
  {
    "timestamp": "2026-11-02T13:05:46.437592+00:00",
    "diagnostic_id": "6a83dd55-c398-4bd2-b8f8-2f38820c57bb",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.930172,
      "face_match_score": 0.7185182961132216
    },
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  },
  {
    "timestamp": "2026-11-02T13:05:52.204674+00:00",
    "diagnostic_id": "35aa3417-f907-4cfc-873d-f77d2735743e",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  },
  {
    "timestamp": "2026-11-02T13:05:55.152112+00:00",
    "diagnostic_id": "35aa3417-f907-4cfc-873d-f77d2735743e",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "decision",
    "values": {
      "checkin_id": "4239dbab-e7c2-43b8-a389-0d598a8cb098",
      "status": "approved",
      "risk_score": 0.2252,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.22518536310942272,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 45.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.930172,
      "face_match_passed": true,
      "face_match_score": 0.7185182961132216,
      "reason": "below_threshold"
    },
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  },
  {
    "timestamp": "2026-11-02T13:05:55.926791+00:00",
    "diagnostic_id": "35aa3417-f907-4cfc-873d-f77d2735743e",
    "session_id": "953637ea-65ba-4a27-a94d-2e6a2777553e",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "4239dbab-e7c2-43b8-a389-0d598a8cb098",
      "status": "approved",
      "risk_score": 0.2252
    },
    "challenge_id": "a83a62ed-2fb1-4986-b9e2-129ddb48ae08"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
