

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-03T09:06:37+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / 0004f836-218b-4b6b-a098-204b79769457

Expected genuine identity acceptance. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.99441 | 0.998602 | not used | evaluated | 0.99949 | True |
| last_frame | yes | 1.0 | 0.99402 | 0.998505 | not used | evaluated | 0.999528 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.853515625 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.15351562500000004 |
| Identity comparisons performed | 6 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.12 |
| Maximum accepted differing bits | 30 |
| Minimum observed differing bits | 10 |
| Maximum observed differing bits | 15 |
| Bit margin below acceptance limit | 15 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 66 | True | True | 12 | 0.046875 | 0.8828125 | True |
| 8 | 803 | True | True | 12 | 0.046875 | 0.8828125 | True |
| 16 | 1555 | True | True | 13 | 0.05078125 | 0.873046875 | True |
| 20 | 1929 | True | True | 10 | 0.0390625 | 0.90234375 | True |
| 24 | 2301 | True | True | 10 | 0.0390625 | 0.90234375 | True |
| 32 | 3041 | True | True | 15 | 0.05859375 | 0.853515625 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.1172 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.1171875 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.1172 |

```json
[
  {
    "timestamp": "2026-11-03T01:05:12.252611+00:00",
    "diagnostic_id": "128200ec-57b0-419b-8c30-7d855680df59",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  },
  {
    "timestamp": "2026-11-03T01:05:20.815284+00:00",
    "diagnostic_id": "881a88be-120a-4aaa-a245-0a7e26d08edb",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  },
  {
    "timestamp": "2026-11-03T01:05:24.725982+00:00",
    "diagnostic_id": "881a88be-120a-4aaa-a245-0a7e26d08edb",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.998505,
      "face_match_score": 0.853515625,
      "diagnostics": {
        "frame_count": 33,
        "processed_frames": 33,
        "duration_ms": 2975,
        "last_frame_index": 32,
        "last_timestamp_ms": 3041,
        "identity_checks": 6,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.12,
        "max_accepted_hamming_distance": 30,
        "max_hamming_distance": 15,
        "min_hamming_distance": 10,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 66,
            "match_score": 0.8828125,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 8,
            "timestamp_ms": 803,
            "match_score": 0.8828125,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1555,
            "match_score": 0.873046875,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 13,
            "hamming_fraction": 0.05078125
          },
          {
            "frame_index": 20,
            "timestamp_ms": 1929,
            "match_score": 0.90234375,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 10,
            "hamming_fraction": 0.0390625
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2301,
            "match_score": 0.90234375,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 10,
            "hamming_fraction": 0.0390625
          },
          {
            "frame_index": 32,
            "timestamp_ms": 3041,
            "match_score": 0.853515625,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 15,
            "hamming_fraction": 0.05859375
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
          "timestamp_ms": 66,
          "liveness_passed": true,
          "liveness_score": 0.998602,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.92146,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.99441,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.998602,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.998602,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.248602,
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
            "pad_live_score": 0.99949,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999212,
            "pad_v1se_live_score": 0.999767,
            "pre_pad_liveness_score": 0.998602,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 9.005,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 32,
          "timestamp_ms": 3041,
          "liveness_passed": true,
          "liveness_score": 0.998505,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.92747,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.99402,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.998505,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.998505,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.248505,
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
            "pad_live_score": 0.999528,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.99939,
            "pad_v1se_live_score": 0.999666,
            "pre_pad_liveness_score": 0.998505,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 15.395,
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
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  },
  {
    "timestamp": "2026-11-03T01:05:25.412603+00:00",
    "diagnostic_id": "881a88be-120a-4aaa-a245-0a7e26d08edb",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.998505,
      "face_match_score": 0.853515625
    },
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  },
  {
    "timestamp": "2026-11-03T01:05:33.179133+00:00",
    "diagnostic_id": "b3225a0a-5915-4b92-86d5-9d37f877beac",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  },
  {
    "timestamp": "2026-11-03T01:05:37.824708+00:00",
    "diagnostic_id": "b3225a0a-5915-4b92-86d5-9d37f877beac",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "decision",
    "values": {
      "checkin_id": "1cf727c6-5539-4841-bb84-f748a3715619",
      "status": "approved",
      "risk_score": 0.1172,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.1171875,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.998505,
      "face_match_passed": true,
      "face_match_score": 0.853515625,
      "reason": "below_threshold"
    },
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  },
  {
    "timestamp": "2026-11-03T01:05:39.027665+00:00",
    "diagnostic_id": "b3225a0a-5915-4b92-86d5-9d37f877beac",
    "session_id": "e655aef9-2768-418a-af84-e7f4e1a5eacf",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "1cf727c6-5539-4841-bb84-f748a3715619",
      "status": "approved",
      "risk_score": 0.1172
    },
    "challenge_id": "0004f836-218b-4b6b-a098-204b79769457"
  }
]
```

### impersonation_test — student1@gmail.com / fcc935ea-2c1f-4202-9ec3-c0d42652a214

Identity mismatch observed; expected impersonation rejection. No attendance commit is required.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | not evaluated | — | — | — | — | not evaluated | — | — |
| last_frame | not evaluated | — | — | — | — | not evaluated | — | — |

Sequence stop reason: identity_failed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.6907894736842105 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | -0.009210526315789447 |
| Identity comparisons performed | 1 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.12 |
| Maximum accepted differing bits | 30 |
| Minimum observed differing bits | 32 |
| Maximum observed differing bits | 32 |
| Bit margin below acceptance limit | -2 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 22 | True | True | 32 | 0.125 | 0.6907894736842105 | False |

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
    "timestamp": "2026-11-03T01:06:24.778827+00:00",
    "diagnostic_id": "bbf2aae3-3270-4fae-989a-5ecb8706442b",
    "session_id": "6a127528-b3bc-4136-8d9f-6ce2d77920fc",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "fcc935ea-2c1f-4202-9ec3-c0d42652a214"
  },
  {
    "timestamp": "2026-11-03T01:06:31.983438+00:00",
    "diagnostic_id": "406a8a04-88c9-464d-8159-96d41804ef7d",
    "session_id": "6a127528-b3bc-4136-8d9f-6ce2d77920fc",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "fcc935ea-2c1f-4202-9ec3-c0d42652a214"
  },
  {
    "timestamp": "2026-11-03T01:06:34.340387+00:00",
    "diagnostic_id": "406a8a04-88c9-464d-8159-96d41804ef7d",
    "session_id": "6a127528-b3bc-4136-8d9f-6ce2d77920fc",
    "stage": "motion_sequence",
    "values": {
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.6907894736842105,
      "diagnostics": {
        "frame_count": 28,
        "processed_frames": 1,
        "duration_ms": 2556,
        "last_frame_index": 0,
        "last_timestamp_ms": 22,
        "identity_checks": 1,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.12,
        "max_accepted_hamming_distance": 30,
        "max_hamming_distance": 32,
        "min_hamming_distance": 32,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 22,
            "match_score": 0.6907894736842105,
            "match_passed": false,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 32,
            "hamming_fraction": 0.125
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
    "challenge_id": "fcc935ea-2c1f-4202-9ec3-c0d42652a214"
  },
  {
    "timestamp": "2026-11-03T01:06:35.011539+00:00",
    "diagnostic_id": "406a8a04-88c9-464d-8159-96d41804ef7d",
    "session_id": "6a127528-b3bc-4136-8d9f-6ce2d77920fc",
    "stage": "motion_verified",
    "values": {
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.6907894736842105
    },
    "challenge_id": "fcc935ea-2c1f-4202-9ec3-c0d42652a214"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
