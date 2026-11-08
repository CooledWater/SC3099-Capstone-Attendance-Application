

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-07T17:06:20+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / b4ddd29e-9cf2-4667-beb8-f8195c9d435c

Expected genuine identity acceptance. Saved attendance status: flagged.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 0.96158 | 0.88246 | 0.959087 | not used | evaluated | 0.999998 | True |
| last_frame | yes | 0.98287 | 0.89474 | 0.968547 | not used | evaluated | 0.999993 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.7521739130434782 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.05217391304347829 |
| Identity comparisons performed | 13 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 12 |
| Maximum observed differing bits | 19 |
| Bit margin below acceptance limit | 4 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 69 | True | True | 12 | 0.046875 | 0.8434782608695652 | True |
| 8 | 830 | True | True | 14 | 0.0546875 | 0.817391304347826 | True |
| 16 | 1578 | True | True | 13 | 0.05078125 | 0.8304347826086956 | True |
| 24 | 2346 | True | True | 17 | 0.06640625 | 0.7782608695652173 | True |
| 29 | 2830 | True | True | 13 | 0.05078125 | 0.8304347826086956 | True |
| 32 | 3118 | True | True | 14 | 0.0546875 | 0.817391304347826 | True |
| 39 | 3789 | True | True | 13 | 0.05078125 | 0.8304347826086956 | True |
| 40 | 3886 | True | True | 14 | 0.0546875 | 0.817391304347826 | True |
| 48 | 4650 | True | True | 19 | 0.07421875 | 0.7521739130434782 | True |
| 56 | 5418 | True | True | 14 | 0.0546875 | 0.817391304347826 | True |
| 64 | 6181 | True | True | 14 | 0.0546875 | 0.817391304347826 | True |
| 72 | 6947 | True | True | 12 | 0.046875 | 0.8434782608695652 | True |
| 79 | 7617 | True | True | 17 | 0.06640625 | 0.7782608695652173 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | flagged |
| Decision reason | risk_threshold |
| Final risk score | 0.3983 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.39826086956521745 |
| Saved attendance status | flagged |
| Saved attendance risk score | 0.3983 |

```json
[
  {
    "timestamp": "2026-11-07T09:00:44.041985+00:00",
    "diagnostic_id": "bc5bbbd6-9cb3-47d8-b1cf-7154e6af778c",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  },
  {
    "timestamp": "2026-11-07T09:00:54.322930+00:00",
    "diagnostic_id": "7d54c857-339a-48c2-b6bb-21101bab932e",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  },
  {
    "timestamp": "2026-11-07T09:00:58.156909+00:00",
    "diagnostic_id": "7d54c857-339a-48c2-b6bb-21101bab932e",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "motion_sequence",
    "values": {
      "challenge_version": 2,
      "completed_steps": 2,
      "turn_passed": true,
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.959087,
      "face_match_score": 0.7521739130434782,
      "diagnostics": {
        "challenge_version": 2,
        "completed_steps": 2,
        "turn_passed": true,
        "frame_count": 80,
        "processed_frames": 80,
        "duration_ms": 7548,
        "last_frame_index": 79,
        "last_timestamp_ms": 7617,
        "identity_checks": 13,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 19,
        "min_hamming_distance": 12,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 69,
            "match_score": 0.8434782608695652,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 8,
            "timestamp_ms": 830,
            "match_score": 0.817391304347826,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1578,
            "match_score": 0.8304347826086956,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 13,
            "hamming_fraction": 0.05078125
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2346,
            "match_score": 0.7782608695652173,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 17,
            "hamming_fraction": 0.06640625
          },
          {
            "frame_index": 29,
            "timestamp_ms": 2830,
            "match_score": 0.8304347826086956,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 13,
            "hamming_fraction": 0.05078125
          },
          {
            "frame_index": 32,
            "timestamp_ms": 3118,
            "match_score": 0.817391304347826,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 39,
            "timestamp_ms": 3789,
            "match_score": 0.8304347826086956,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 13,
            "hamming_fraction": 0.05078125
          },
          {
            "frame_index": 40,
            "timestamp_ms": 3886,
            "match_score": 0.817391304347826,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 48,
            "timestamp_ms": 4650,
            "match_score": 0.7521739130434782,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 19,
            "hamming_fraction": 0.07421875
          },
          {
            "frame_index": 56,
            "timestamp_ms": 5418,
            "match_score": 0.817391304347826,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 64,
            "timestamp_ms": 6181,
            "match_score": 0.817391304347826,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 14,
            "hamming_fraction": 0.0546875
          },
          {
            "frame_index": 72,
            "timestamp_ms": 6947,
            "match_score": 0.8434782608695652,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 79,
            "timestamp_ms": 7617,
            "match_score": 0.7782608695652173,
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
          "timestamp_ms": 69,
          "liveness_passed": true,
          "liveness_score": 0.959087,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.93051,
            "depth_score": 0.96158,
            "mesh_plausibility_score": 0.88246,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.959087,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.959087,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.288473,
              "mesh": 0.220614,
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
            "pad_live_score": 0.999998,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999998,
            "pad_v1se_live_score": 0.999998,
            "pre_pad_liveness_score": 0.959087,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 12.909,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 79,
          "timestamp_ms": 7617,
          "liveness_passed": true,
          "liveness_score": 0.968547,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.92366,
            "depth_score": 0.98287,
            "mesh_plausibility_score": 0.89474,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.968547,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.968547,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.294862,
              "mesh": 0.223685,
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
            "pad_live_score": 0.999993,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.99999,
            "pad_v1se_live_score": 0.999996,
            "pre_pad_liveness_score": 0.968547,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 9.478,
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
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  },
  {
    "timestamp": "2026-11-07T09:00:58.353947+00:00",
    "diagnostic_id": "7d54c857-339a-48c2-b6bb-21101bab932e",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "challenge_version": 2,
      "completed_steps": 2,
      "turn_passed": true,
      "liveness_score": 0.959087,
      "face_match_score": 0.7521739130434782
    },
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  },
  {
    "timestamp": "2026-11-07T09:01:02.298105+00:00",
    "diagnostic_id": "f3e11445-4c38-4d45-a1ea-f7b6a012149b",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  },
  {
    "timestamp": "2026-11-07T09:01:03.937538+00:00",
    "diagnostic_id": "f3e11445-4c38-4d45-a1ea-f7b6a012149b",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "decision",
    "values": {
      "checkin_id": "183af3d3-60d1-4b8f-ac10-30a10af1feab",
      "status": "flagged",
      "risk_score": 0.3983,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.39826086956521745,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 52.331138610839844,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.959087,
      "face_match_passed": true,
      "face_match_score": 0.7521739130434782,
      "reason": "risk_threshold"
    },
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  },
  {
    "timestamp": "2026-11-07T09:01:04.353747+00:00",
    "diagnostic_id": "f3e11445-4c38-4d45-a1ea-f7b6a012149b",
    "session_id": "5c7522dc-7f70-417d-a5b9-e10dc04c9082",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "183af3d3-60d1-4b8f-ac10-30a10af1feab",
      "status": "flagged",
      "risk_score": 0.3983
    },
    "challenge_id": "b4ddd29e-9cf2-4667-beb8-f8195c9d435c"
  }
]
```

### impersonation_test — student1@gmail.com / f64e79ff-2024-408f-bd59-d0c31ac6c603

No completed server identity verdict; request failures or browser-only captures are inconclusive.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | unknown | — | — | — | — | not evaluated | — | — |
| last_frame | unknown | — | — | — | — | not evaluated | — | — |

Sequence stop reason: unknown.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | unknown |
| Identity score cutoff | unknown |
| Score margin above cutoff | unknown |
| Identity comparisons performed | unknown |
| Matcher version | unknown |
| Score mapping version | unknown |
| Template bits | unknown |
| Hamming fraction boundary | unknown |
| Maximum accepted differing bits | unknown |
| Minimum observed differing bits | unknown |
| Maximum observed differing bits | unknown |
| Bit margin below acceptance limit | unknown |

Per-comparison Hamming measurements were not recorded; they cannot be recovered from this report.

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
    "timestamp": "2026-11-07T09:05:59.240161+00:00",
    "diagnostic_id": "2a0368e9-ce51-4c63-9e5b-dedb746be274",
    "session_id": "73e874f4-b1ef-4f5a-9498-0996405fd15f",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "f64e79ff-2024-408f-bd59-d0c31ac6c603"
  }
]
```

### impersonation_test — student1@gmail.com / f0845238-0936-41b8-9c2f-54513eab551b

No completed server identity verdict; request failures or browser-only captures are inconclusive.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | unknown | — | — | — | — | not evaluated | — | — |
| last_frame | unknown | — | — | — | — | not evaluated | — | — |

Sequence stop reason: unknown.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | unknown |
| Identity score cutoff | unknown |
| Score margin above cutoff | unknown |
| Identity comparisons performed | unknown |
| Matcher version | unknown |
| Score mapping version | unknown |
| Template bits | unknown |
| Hamming fraction boundary | unknown |
| Maximum accepted differing bits | unknown |
| Minimum observed differing bits | unknown |
| Maximum observed differing bits | unknown |
| Bit margin below acceptance limit | unknown |

Per-comparison Hamming measurements were not recorded; they cannot be recovered from this report.

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
    "timestamp": "2026-11-07T09:06:05.391346+00:00",
    "diagnostic_id": "fcca8258-8f86-43d6-abbe-152d551aa3a2",
    "session_id": "73e874f4-b1ef-4f5a-9498-0996405fd15f",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "f0845238-0936-41b8-9c2f-54513eab551b"
  }
]
```

### impersonation_test — student1@gmail.com / cb9c1aa6-cf6d-47ca-94b5-c4e68a1d7f15

Identity mismatch observed; expected impersonation rejection. No attendance commit is required.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | not evaluated | — | — | — | — | not evaluated | — | — |
| last_frame | not evaluated | — | — | — | — | not evaluated | — | — |

Sequence stop reason: identity_failed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.6266666666666667 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | -0.07333333333333325 |
| Identity comparisons performed | 1 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 34 |
| Maximum observed differing bits | 34 |
| Bit margin below acceptance limit | -11 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 51 | True | True | 34 | 0.1328125 | 0.6266666666666667 | False |

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
    "timestamp": "2026-11-07T09:06:11.973446+00:00",
    "diagnostic_id": "47f7e8c8-c92b-47cb-be98-cfeca6ab3a7b",
    "session_id": "73e874f4-b1ef-4f5a-9498-0996405fd15f",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "cb9c1aa6-cf6d-47ca-94b5-c4e68a1d7f15"
  },
  {
    "timestamp": "2026-11-07T09:06:18.237538+00:00",
    "diagnostic_id": "2d92e5e2-5a4c-4a4d-985e-137af6998656",
    "session_id": "73e874f4-b1ef-4f5a-9498-0996405fd15f",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "cb9c1aa6-cf6d-47ca-94b5-c4e68a1d7f15"
  },
  {
    "timestamp": "2026-11-07T09:06:19.207089+00:00",
    "diagnostic_id": "2d92e5e2-5a4c-4a4d-985e-137af6998656",
    "session_id": "73e874f4-b1ef-4f5a-9498-0996405fd15f",
    "stage": "motion_sequence",
    "values": {
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.6266666666666667,
      "diagnostics": {
        "challenge_version": 2,
        "completed_steps": 0,
        "turn_passed": false,
        "frame_count": 41,
        "processed_frames": 1,
        "duration_ms": 3754,
        "last_frame_index": 0,
        "last_timestamp_ms": 51,
        "identity_checks": 1,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 34,
        "min_hamming_distance": 34,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 51,
            "match_score": 0.6266666666666667,
            "match_passed": false,
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
    "challenge_id": "cb9c1aa6-cf6d-47ca-94b5-c4e68a1d7f15"
  },
  {
    "timestamp": "2026-11-07T09:06:19.407427+00:00",
    "diagnostic_id": "2d92e5e2-5a4c-4a4d-985e-137af6998656",
    "session_id": "73e874f4-b1ef-4f5a-9498-0996405fd15f",
    "stage": "motion_verified",
    "values": {
      "passed": false,
      "blink_count": 0,
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "liveness_score": 0.0,
      "face_match_score": 0.6266666666666667
    },
    "challenge_id": "cb9c1aa6-cf6d-47ca-94b5-c4e68a1d7f15"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
