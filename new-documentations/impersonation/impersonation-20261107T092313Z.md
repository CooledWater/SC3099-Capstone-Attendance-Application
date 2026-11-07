

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-07T17:32:22+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / f00e1871-9ce6-40d9-8875-5fe658137345

Identity mismatch observed; unexpected rejection of the genuine control. No attendance commit is required.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | not evaluated | — | — | — | — | not evaluated | — | — |
| last_frame | not evaluated | — | — | — | — | not evaluated | — | — |

Sequence stop reason: identity_failed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.5666666666666667 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | -0.1333333333333333 |
| Identity comparisons performed | 1 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 43 |
| Maximum observed differing bits | 43 |
| Bit margin below acceptance limit | -20 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 70 | True | True | 43 | 0.16796875 | 0.5666666666666667 | False |

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
    "timestamp": "2026-11-07T09:27:34.421513+00:00",
    "diagnostic_id": "389c1969-6d8c-4ed6-83d2-74bbf207a3c9",
    "session_id": "a39aecda-2cc5-42a3-951e-c0d2c5cdd2a4",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "f00e1871-9ce6-40d9-8875-5fe658137345"
  },
  {
    "timestamp": "2026-11-07T09:27:45.496791+00:00",
    "diagnostic_id": "b74e3296-6fb3-45ec-a73b-4dc7daf97c72",
    "session_id": "a39aecda-2cc5-42a3-951e-c0d2c5cdd2a4",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "f00e1871-9ce6-40d9-8875-5fe658137345"
  },
  {
    "timestamp": "2026-11-07T09:27:49.192894+00:00",
    "diagnostic_id": "b74e3296-6fb3-45ec-a73b-4dc7daf97c72",
    "session_id": "a39aecda-2cc5-42a3-951e-c0d2c5cdd2a4",
    "stage": "motion_sequence",
    "values": {
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.5666666666666667,
      "diagnostics": {
        "challenge_version": 2,
        "completed_steps": 0,
        "turn_passed": false,
        "frame_count": 54,
        "processed_frames": 1,
        "duration_ms": 5079,
        "last_frame_index": 0,
        "last_timestamp_ms": 70,
        "identity_checks": 1,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 43,
        "min_hamming_distance": 43,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 70,
            "match_score": 0.5666666666666667,
            "match_passed": false,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 43,
            "hamming_fraction": 0.16796875
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
    "challenge_id": "f00e1871-9ce6-40d9-8875-5fe658137345"
  },
  {
    "timestamp": "2026-11-07T09:27:49.651863+00:00",
    "diagnostic_id": "b74e3296-6fb3-45ec-a73b-4dc7daf97c72",
    "session_id": "a39aecda-2cc5-42a3-951e-c0d2c5cdd2a4",
    "stage": "motion_verified",
    "values": {
      "passed": false,
      "blink_count": 0,
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "liveness_score": 0.0,
      "face_match_score": 0.5666666666666667
    },
    "challenge_id": "f00e1871-9ce6-40d9-8875-5fe658137345"
  }
]
```

### impersonation_test — student1@gmail.com / 8c30221e-1c12-4b41-8661-095d5811ea3d

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
    "timestamp": "2026-11-07T09:31:52.062597+00:00",
    "diagnostic_id": "2dd21e21-bb7d-49b5-95a1-dc5443cea988",
    "session_id": "2c117e48-ecca-462d-8714-4b3348f5e796",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "8c30221e-1c12-4b41-8661-095d5811ea3d"
  }
]
```

### impersonation_test — student1@gmail.com / 039caefd-34b3-4b17-8d1a-9046fea6b6b7

Identity mismatch observed; expected impersonation rejection. No attendance commit is required.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.97786 | 0.990609 | not used | evaluated | 0.999956 | True |
| last_frame | not evaluated | — | — | — | — | not evaluated | — | — |

Sequence stop reason: identity_failed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.6933333333333334 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | -0.006666666666666599 |
| Identity comparisons performed | 4 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 17 |
| Maximum observed differing bits | 24 |
| Bit margin below acceptance limit | -1 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 68 | True | True | 18 | 0.0703125 | 0.7652173913043478 | True |
| 8 | 811 | True | True | 17 | 0.06640625 | 0.7782608695652173 | True |
| 16 | 1587 | True | True | 21 | 0.08203125 | 0.726086956521739 | True |
| 24 | 2353 | True | True | 24 | 0.09375 | 0.6933333333333334 | False |

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
    "timestamp": "2026-11-07T09:32:07.620945+00:00",
    "diagnostic_id": "86bebf49-0a2f-40eb-a990-37229e779d67",
    "session_id": "2c117e48-ecca-462d-8714-4b3348f5e796",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "039caefd-34b3-4b17-8d1a-9046fea6b6b7"
  },
  {
    "timestamp": "2026-11-07T09:32:16.685969+00:00",
    "diagnostic_id": "8eee7359-33fc-4389-97ba-a97f482d1658",
    "session_id": "2c117e48-ecca-462d-8714-4b3348f5e796",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "039caefd-34b3-4b17-8d1a-9046fea6b6b7"
  },
  {
    "timestamp": "2026-11-07T09:32:19.777695+00:00",
    "diagnostic_id": "8eee7359-33fc-4389-97ba-a97f482d1658",
    "session_id": "2c117e48-ecca-462d-8714-4b3348f5e796",
    "stage": "motion_sequence",
    "values": {
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.990609,
      "face_match_score": 0.6933333333333334,
      "diagnostics": {
        "challenge_version": 2,
        "completed_steps": 0,
        "turn_passed": false,
        "frame_count": 50,
        "processed_frames": 25,
        "duration_ms": 4699,
        "last_frame_index": 24,
        "last_timestamp_ms": 2353,
        "identity_checks": 4,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 24,
        "min_hamming_distance": 17,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 68,
            "match_score": 0.7652173913043478,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 18,
            "hamming_fraction": 0.0703125
          },
          {
            "frame_index": 8,
            "timestamp_ms": 811,
            "match_score": 0.7782608695652173,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 17,
            "hamming_fraction": 0.06640625
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1587,
            "match_score": 0.726086956521739,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 21,
            "hamming_fraction": 0.08203125
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2353,
            "match_score": 0.6933333333333334,
            "match_passed": false,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 24,
            "hamming_fraction": 0.09375
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
          "timestamp_ms": 68,
          "liveness_passed": true,
          "liveness_score": 0.990609,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.97296,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.97786,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 0.99483,
            "weighted_component_score": 0.993432,
            "presentation_integrity_score": 0.997159,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.990609,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.244465,
              "texture": 0.25,
              "color": 0.198967
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
              "color_diversity": 0.997159
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.0
            },
            "pad_live_score": 0.999956,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999928,
            "pad_v1se_live_score": 0.999983,
            "pre_pad_liveness_score": 0.990609,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 23.726,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": false
        },
        "reason": "identity_failed"
      },
      "outcome": "received",
      "http_status": 200
    },
    "challenge_id": "039caefd-34b3-4b17-8d1a-9046fea6b6b7"
  },
  {
    "timestamp": "2026-11-07T09:32:20.215661+00:00",
    "diagnostic_id": "8eee7359-33fc-4389-97ba-a97f482d1658",
    "session_id": "2c117e48-ecca-462d-8714-4b3348f5e796",
    "stage": "motion_verified",
    "values": {
      "passed": false,
      "blink_count": 0,
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "liveness_score": 0.990609,
      "face_match_score": 0.6933333333333334
    },
    "challenge_id": "039caefd-34b3-4b17-8d1a-9046fea6b6b7"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
