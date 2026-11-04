

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; participant presentation confirmation still required; diagnostics disabled**.

Updated: 2026-11-03T10:41:13+08:00.

Presentation labels identify the assigned session; they do not independently establish what the camera saw.

### Planned account assignments

| Session | Intended signed-in account | Actual presenter assignment | Expected identity match |
| --- | --- | --- | --- |
| genuine_control | wcstudent1@example.com | Same live participant | True |
| impersonation_test | student1@gmail.com | Same live participant | False |

Assignments are operator-provided, not authenticated account readback. Confirm the displayed login, actual presenter, and saved attendance ownership separately.

### genuine_control — wcstudent1@example.com / 6fa33394-cb7b-47bc-97b7-4e2933a8ec44

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
    "timestamp": "2026-11-03T02:38:47.647006+00:00",
    "diagnostic_id": "45a2b373-b03f-44e7-97bd-fe99033fd8be",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "6fa33394-cb7b-47bc-97b7-4e2933a8ec44"
  }
]
```

### genuine_control — wcstudent1@example.com / b941f812-2b53-40e7-9626-dc0068b4bdf6

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
    "timestamp": "2026-11-03T02:39:02.061042+00:00",
    "diagnostic_id": "398e1fab-27d6-49b6-94b0-b081dd930c93",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "b941f812-2b53-40e7-9626-dc0068b4bdf6"
  }
]
```

### genuine_control — wcstudent1@example.com / 87f9e19f-f9d1-44dd-88df-d9aa44d3e074

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
    "timestamp": "2026-11-03T02:39:19.087678+00:00",
    "diagnostic_id": "dc6cf591-6be7-435b-a5c2-1988ddddb212",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "87f9e19f-f9d1-44dd-88df-d9aa44d3e074"
  }
]
```

### genuine_control — wcstudent1@example.com / 692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d

Expected genuine identity acceptance. Saved attendance status: approved.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.99311 | 0.998276 | not used | evaluated | 0.997671 | True |
| last_frame | yes | 1.0 | 0.9941 | 0.998525 | not used | evaluated | 0.997557 | True |

Sequence stop reason: passed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.7521739130434782 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | 0.05217391304347829 |
| Identity comparisons performed | 9 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 10 |
| Maximum observed differing bits | 19 |
| Bit margin below acceptance limit | 4 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 66 | True | True | 10 | 0.0390625 | 0.8695652173913043 | True |
| 8 | 811 | True | True | 12 | 0.046875 | 0.8434782608695652 | True |
| 16 | 1555 | True | True | 12 | 0.046875 | 0.8434782608695652 | True |
| 24 | 2303 | True | True | 13 | 0.05078125 | 0.8304347826086956 | True |
| 32 | 3050 | True | True | 15 | 0.05859375 | 0.8043478260869565 | True |
| 40 | 3800 | True | True | 18 | 0.0703125 | 0.7652173913043478 | True |
| 43 | 4079 | True | True | 16 | 0.0625 | 0.7913043478260869 | True |
| 48 | 4548 | True | True | 16 | 0.0625 | 0.7913043478260869 | True |
| 52 | 4919 | True | True | 19 | 0.07421875 | 0.7521739130434782 | True |

Hamming is computed from the compared templates without additional face inference. An unavailable comparison is unknown, not a measured zero.

#### Attendance decision

| Measurement | Value |
| --- | --- |
| Calculated status | approved |
| Decision reason | below_threshold |
| Final risk score | 0.1983 |
| Effective risk threshold | 0.5 |
| Venue risk score | 0.0 |
| Module 3 risk score (at decision) | 0.1982608695652174 |
| Saved attendance status | approved |
| Saved attendance risk score | 0.1983 |

```json
[
  {
    "timestamp": "2026-11-03T02:39:32.404506+00:00",
    "diagnostic_id": "339e6042-d62e-4727-b2bc-afa7c96f1119",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  },
  {
    "timestamp": "2026-11-03T02:39:42.062441+00:00",
    "diagnostic_id": "f1777fc0-f7b2-4abf-8a6e-96c7ec1d6462",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  },
  {
    "timestamp": "2026-11-03T02:39:46.440778+00:00",
    "diagnostic_id": "f1777fc0-f7b2-4abf-8a6e-96c7ec1d6462",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_sequence",
    "values": {
      "challenge_version": 2,
      "completed_steps": 2,
      "turn_passed": true,
      "passed": true,
      "blink_count": 1,
      "liveness_score": 0.998276,
      "face_match_score": 0.7521739130434782,
      "diagnostics": {
        "challenge_version": 2,
        "completed_steps": 2,
        "turn_passed": true,
        "frame_count": 53,
        "processed_frames": 53,
        "duration_ms": 4853,
        "last_frame_index": 52,
        "last_timestamp_ms": 4919,
        "identity_checks": 9,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 19,
        "min_hamming_distance": 10,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 66,
            "match_score": 0.8695652173913043,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 10,
            "hamming_fraction": 0.0390625
          },
          {
            "frame_index": 8,
            "timestamp_ms": 811,
            "match_score": 0.8434782608695652,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 16,
            "timestamp_ms": 1555,
            "match_score": 0.8434782608695652,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 12,
            "hamming_fraction": 0.046875
          },
          {
            "frame_index": 24,
            "timestamp_ms": 2303,
            "match_score": 0.8304347826086956,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 13,
            "hamming_fraction": 0.05078125
          },
          {
            "frame_index": 32,
            "timestamp_ms": 3050,
            "match_score": 0.8043478260869565,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 15,
            "hamming_fraction": 0.05859375
          },
          {
            "frame_index": 40,
            "timestamp_ms": 3800,
            "match_score": 0.7652173913043478,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 18,
            "hamming_fraction": 0.0703125
          },
          {
            "frame_index": 43,
            "timestamp_ms": 4079,
            "match_score": 0.7913043478260869,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 16,
            "hamming_fraction": 0.0625
          },
          {
            "frame_index": 48,
            "timestamp_ms": 4548,
            "match_score": 0.7913043478260869,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 16,
            "hamming_fraction": 0.0625
          },
          {
            "frame_index": 52,
            "timestamp_ms": 4919,
            "match_score": 0.7521739130434782,
            "match_passed": true,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 19,
            "hamming_fraction": 0.07421875
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
          "liveness_score": 0.998276,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.93197,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.99311,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.998276,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.998276,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.248276,
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
            "pad_live_score": 0.997671,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.998137,
            "pad_v1se_live_score": 0.997205,
            "pre_pad_liveness_score": 0.998276,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 10.302,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 52,
          "timestamp_ms": 4919,
          "liveness_passed": true,
          "liveness_score": 0.998525,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.90356,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.9941,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.998525,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.998525,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.248525,
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
            "pad_live_score": 0.997557,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.997836,
            "pad_v1se_live_score": 0.997278,
            "pre_pad_liveness_score": 0.998525,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 12.606,
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
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  },
  {
    "timestamp": "2026-11-03T02:39:46.975522+00:00",
    "diagnostic_id": "f1777fc0-f7b2-4abf-8a6e-96c7ec1d6462",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 1,
      "challenge_version": 2,
      "completed_steps": 2,
      "turn_passed": true,
      "liveness_score": 0.998276,
      "face_match_score": 0.7521739130434782
    },
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  },
  {
    "timestamp": "2026-11-03T02:39:56.832163+00:00",
    "diagnostic_id": "802a4190-208d-41d0-ba49-df1876703093",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  },
  {
    "timestamp": "2026-11-03T02:40:02.484492+00:00",
    "diagnostic_id": "802a4190-208d-41d0-ba49-df1876703093",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "decision",
    "values": {
      "checkin_id": "c330e4cb-20cb-4678-891c-9322ac4e6737",
      "status": "approved",
      "risk_score": 0.1983,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.1982608695652174,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.998276,
      "face_match_passed": true,
      "face_match_score": 0.7521739130434782,
      "reason": "below_threshold"
    },
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  },
  {
    "timestamp": "2026-11-03T02:40:03.683735+00:00",
    "diagnostic_id": "802a4190-208d-41d0-ba49-df1876703093",
    "session_id": "2a767003-f38a-485c-8a28-e11f653f3df5",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "c330e4cb-20cb-4678-891c-9322ac4e6737",
      "status": "approved",
      "risk_score": 0.1983
    },
    "challenge_id": "692dcbb5-7366-4afa-a0b1-ffcc9aaabf1d"
  }
]
```

### impersonation_test — student1@gmail.com / b5511f73-fdda-4939-8787-dd613d5ba8b4

Identity mismatch observed; expected impersonation rejection. No attendance commit is required.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | not evaluated | — | — | — | — | not evaluated | — | — |
| last_frame | not evaluated | — | — | — | — | not evaluated | — | — |

Sequence stop reason: identity_failed.

#### Identity comparison

| Measurement | Value |
| --- | --- |
| Minimum identity score | 0.6199999999999999 |
| Identity score cutoff | 0.7 |
| Score margin above cutoff | -0.08000000000000007 |
| Identity comparisons performed | 1 |
| Matcher version | dlib128-simhash256-v1 |
| Score mapping version | piecewise-hamming-v1 |
| Template bits | 256 |
| Hamming fraction boundary | 0.08984375 |
| Maximum accepted differing bits | 23 |
| Minimum observed differing bits | 35 |
| Maximum observed differing bits | 35 |
| Bit margin below acceptance limit | -12 |

| Frame | Time (ms) | Face detected | Hamming evaluated | Differing bits | Hamming fraction | Identity score | Identity passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 30 | True | True | 35 | 0.13671875 | 0.6199999999999999 | False |

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
    "timestamp": "2026-11-03T02:40:57.267191+00:00",
    "diagnostic_id": "1755ad78-9fea-4f9b-b0f2-ecec1415f03d",
    "session_id": "7b545bf2-b322-4b3a-8516-698cc134b3af",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "b5511f73-fdda-4939-8787-dd613d5ba8b4"
  },
  {
    "timestamp": "2026-11-03T02:41:09.240066+00:00",
    "diagnostic_id": "eb2b535a-7e43-4ab3-8816-f810772a2d5f",
    "session_id": "7b545bf2-b322-4b3a-8516-698cc134b3af",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "b5511f73-fdda-4939-8787-dd613d5ba8b4"
  },
  {
    "timestamp": "2026-11-03T02:41:11.505310+00:00",
    "diagnostic_id": "eb2b535a-7e43-4ab3-8816-f810772a2d5f",
    "session_id": "7b545bf2-b322-4b3a-8516-698cc134b3af",
    "stage": "motion_sequence",
    "values": {
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "passed": false,
      "blink_count": 0,
      "liveness_score": 0.0,
      "face_match_score": 0.6199999999999999,
      "diagnostics": {
        "challenge_version": 2,
        "completed_steps": 0,
        "turn_passed": false,
        "frame_count": 53,
        "processed_frames": 1,
        "duration_ms": 4940,
        "last_frame_index": 0,
        "last_timestamp_ms": 30,
        "identity_checks": 1,
        "face_match_threshold": 0.7,
        "simhash_bits": 256,
        "face_match_hamming_fraction": 0.08984375,
        "max_accepted_hamming_distance": 23,
        "max_hamming_distance": 35,
        "min_hamming_distance": 35,
        "identity_comparisons_truncated": false,
        "identity_comparisons": [
          {
            "frame_index": 0,
            "timestamp_ms": 30,
            "match_score": 0.6199999999999999,
            "match_passed": false,
            "face_detected": true,
            "hamming_evaluated": true,
            "hamming_distance": 35,
            "hamming_fraction": 0.13671875
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
    "challenge_id": "b5511f73-fdda-4939-8787-dd613d5ba8b4"
  },
  {
    "timestamp": "2026-11-03T02:41:12.102460+00:00",
    "diagnostic_id": "eb2b535a-7e43-4ab3-8816-f810772a2d5f",
    "session_id": "7b545bf2-b322-4b3a-8516-698cc134b3af",
    "stage": "motion_verified",
    "values": {
      "passed": false,
      "blink_count": 0,
      "challenge_version": 2,
      "completed_steps": 0,
      "turn_passed": false,
      "liveness_score": 0.0,
      "face_match_score": 0.6199999999999999
    },
    "challenge_id": "b5511f73-fdda-4939-8787-dd613d5ba8b4"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
