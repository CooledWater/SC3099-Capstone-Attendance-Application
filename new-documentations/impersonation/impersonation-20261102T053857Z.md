# Live impersonation trial — 2 November 2026

## Corrected account and attempt mapping

The participant confirmed that their **own live face** was presented in both
completed attempts. The original video-replay labels were misleading and the
actual account assignment was reversed from the guide's suggested assignment:

| Corrected attempt | Signed-in account | Original session name | Session ID |
| --- | --- | --- | --- |
| Impersonation test: participant against another person's enrollment | `student1@gmail.com` | `Video PAD real_face_control 2026-11-02 05:39 UTC` | `e348bfa9-4a0c-4a92-aac2-b3613e62fc4a` |
| Genuine control: participant against their own enrollment | `wcstudent1@example.com` | `Video PAD phone_video 2026-11-02 05:39 UTC` | `cd71fc39-72f3-4949-a95f-f5170ec3fc39` |

The readable headings below use the corrected roles/accounts. Original session
names above are retained for traceability; no live session or historical config
was renamed. Raw JSON events, IDs, timestamps and measurements are unchanged.
Account/enrollment attribution comes from the participant's clarification;
the scalar diagnostics do not contain authenticated email addresses or templates.

## Identity comparison and finding

| Measurement | Genuine control: `wcstudent1@example.com` | Impersonation test: `student1@gmail.com` |
| --- | --- | --- |
| Minimum sampled face-match score | 0.881481 | 0.711111 |
| Recorded identity cutoff | 0.70 | 0.70 |
| Margin above identity cutoff | +0.181481 | +0.011111 |
| Identity checks / processed frames | 9 / 51 | 9 / 54 |
| Completed blinks | 2 | 2 |
| Minimum passive liveness / cutoff | 0.997354 / 0.85 | 0.967365 / 0.85 |
| PAD first / last frame (cutoff 0.75) | 0.999994 / 0.999994; both passed | 0.999983 / 0.999970; both passed |
| Final risk / attendance risk threshold | 0.0948 / 0.5 | 0.2311 / 0.5 |
| Server-confirmed committed status | `approved` | `approved` |
| Check-in ID | `b08e137c-bb53-4334-b586-952eb65d4c09` | `96160373-0672-4ab1-8333-73929bb5a306` |

**Finding: the identity matcher falsely accepted the impersonation attempt in this
trial, given the participant-confirmed account/enrollment mapping.** The minimum
score across nine comparisons remained above the cutoff, so the motion challenge
passed and the server committed approved attendance. The lower impostor score
shows some separation, but the current acceptance boundary did not reject this
person/enrollment pair. PAD and blinks also passed with a live person present;
these measurements do not establish that the live person owns the account.

The [motion analyzer](../../module3-face-recognition/app/motion.py) returns the
minimum sampled identity score and stops on any failed comparison. The
[template matcher](../../module3-face-recognition/app/template.py) converts
256-bit SimHash Hamming distance into the reported score. Its default boundary,
`FACE_MATCH_HAMMING_FRACTION=0.158203`, was calibrated using the small supplied
Obama/Biden corpus ([configuration](../../module3-face-recognition/app/config.py),
[calibration script](../../module3-face-recognition/scripts/calibrate.py)).
This trial demonstrates that the deployed identity decision is insufficient for
this pair; broader calibration and verification of the enrolled reference are
needed to determine the general failure cause.

Changing `FACE_MATCH_THRESHOLD` alone is insufficient to tighten this matcher:
the score mapping also uses that setting, preserving the underlying Hamming
acceptance boundary for ordinary nonzero thresholds. At the source defaults, the
two recorded scores are exactly reproduced by 16/256 differing bits for the
control and 39/256 for impersonation, with up to 40 bits accepted. Those distances
are **inferred under default calibration**, not directly recorded measurements;
the effective Hamming boundary and individual comparison scores were not logged.
Do not select a replacement cutoff from this single pair or treat scores as
identity probabilities. Evaluate repeated genuine/impostor trials across people
before adjusting the Hamming boundary or template design.

Evidence limits: the earlier issued impersonation challenge has no verification
result and is not a measured rejection. Both completed attempts have
`distance_meters=null` with venue risk 0, so this log does not establish that a
geofence was evaluated. Check-in ownership and the enrolled reference should also
be independently checked through authenticated attendance/enrollment reads.

## Diagnostics for further trials

**A new diagnostic engine is not required.** Existing session/challenge correlation,
identity scores/cutoffs, liveness, PAD and commit events already expose this failure.
A small extension to the existing setup/reporting helper would prevent further
label confusion: use `genuine_control` and `impersonation_test`, record the intended
account and actual presenter separately, and summarize expected versus observed
identity results with score margins. The current collector rejects these new
labels, so config edits alone are insufficient; retain an explicit mapping until
the helper supports them.

For calibration work, additional scalar instrumentation would be useful: log the
effective Hamming boundary and per-comparison distance/score, frame index and
verdict. Keep raw images, embeddings, templates and credentials out of the report.
This reporting extension would improve attribution and diagnosis; fixing the
identity matcher is a separate change. No helper or recognition code was changed
by this review.

<!-- PHONE_REPLAY_DIAGNOSTICS_BEGIN -->
## Instrumented observations

Monitor state: **all sessions reached terminal motion outcomes; diagnostics disabled (monitor-reported)**. Participant presentation/account mapping is confirmed above.

Updated: 2026-11-02T13:45:01+08:00.

Attempt headings reflect the participant-confirmed account mapping. JSON below preserves the original scoped measurements.

### Impersonation test — student1@gmail.com / 41fbdbce-81aa-48ed-b506-36131b5d8f6e

No completed server motion verification recorded; browser-only capture is not a server result.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | unknown | — | — | — | — | not evaluated | — | — |
| last_frame | unknown | — | — | — | — | not evaluated | — | — |

Sequence stop reason: unknown.

```json
[
  {
    "timestamp": "2026-11-02T05:42:27.796986+00:00",
    "diagnostic_id": "8070dc7e-70aa-451f-a1e8-65c90bba912e",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "41fbdbce-81aa-48ed-b506-36131b5d8f6e"
  }
]
```

### Impersonation test — student1@gmail.com / 5aab715b-eaf8-4d29-9727-09f61a0b175b

Server accepted the participant's live face against the other person's enrollment; saved attendance status: approved. This is the impersonation attempt, as confirmed by the participant.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 0.97879 | 0.89719 | 0.967365 | not used | evaluated | 0.999983 | True |
| last_frame | yes | 0.98483 | 0.90046 | 0.970566 | not used | evaluated | 0.99997 | True |

Sequence stop reason: passed.

```json
[
  {
    "timestamp": "2026-11-02T05:42:36.355819+00:00",
    "diagnostic_id": "eb73410f-65bd-4471-a760-fc15356f2e2a",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  },
  {
    "timestamp": "2026-11-02T05:42:46.911089+00:00",
    "diagnostic_id": "cf3ea53f-3039-4af8-a03b-a7859cb22c2b",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  },
  {
    "timestamp": "2026-11-02T05:42:51.147936+00:00",
    "diagnostic_id": "cf3ea53f-3039-4af8-a03b-a7859cb22c2b",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.967365,
      "face_match_score": 0.7111108828530432,
      "diagnostics": {
        "frame_count": 54,
        "processed_frames": 54,
        "duration_ms": 4981,
        "last_frame_index": 53,
        "last_timestamp_ms": 4983,
        "identity_checks": 9,
        "face_match_threshold": 0.7,
        "liveness_threshold": 0.85,
        "ear_closed_threshold": 0.19,
        "ear_open_threshold": 0.23,
        "min_closure_ms": 40,
        "max_closure_ms": 700,
        "first_frame": {
          "evaluated": true,
          "frame_index": 0,
          "timestamp_ms": 2,
          "liveness_passed": true,
          "liveness_score": 0.967365,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.87063,
            "depth_score": 0.97879,
            "mesh_plausibility_score": 0.89719,
            "texture_analysis_score": 0.99981,
            "color_distribution_score": 0.99958,
            "weighted_component_score": 0.9678,
            "presentation_integrity_score": 0.99955,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.967365,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.293636,
              "mesh": 0.224296,
              "texture": 0.249952,
              "color": 0.199916
            },
            "component_weights": {
              "depth": 0.3,
              "mesh": 0.25,
              "texture": 0.25,
              "color": 0.2
            },
            "presentation_integrity_checks": {
              "periodicity": 0.99955,
              "texture_diversity": 0.999895,
              "color_diversity": 0.999769
            },
            "texture_signals": {
              "periodic_artifact_penalty": 0.00075
            },
            "pad_live_score": 0.999983,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.999971,
            "pad_v1se_live_score": 0.999996,
            "pre_pad_liveness_score": 0.967365,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 31.725,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 53,
          "timestamp_ms": 4983,
          "liveness_passed": true,
          "liveness_score": 0.970566,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.91274,
            "depth_score": 0.98483,
            "mesh_plausibility_score": 0.90046,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.970566,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.970566,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.29545,
              "mesh": 0.225116,
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
            "pad_live_score": 0.99997,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 0.99996,
            "pad_v1se_live_score": 0.999979,
            "pre_pad_liveness_score": 0.970566,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 10.777,
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
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  },
  {
    "timestamp": "2026-11-02T05:42:51.922155+00:00",
    "diagnostic_id": "cf3ea53f-3039-4af8-a03b-a7859cb22c2b",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.967365,
      "face_match_score": 0.7111108828530432
    },
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  },
  {
    "timestamp": "2026-11-02T05:43:00.437691+00:00",
    "diagnostic_id": "69a29c0f-d894-46de-b81e-3d6a6411419d",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  },
  {
    "timestamp": "2026-11-02T05:43:04.667375+00:00",
    "diagnostic_id": "69a29c0f-d894-46de-b81e-3d6a6411419d",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "decision",
    "values": {
      "checkin_id": "96160373-0672-4ab1-8333-73929bb5a306",
      "status": "approved",
      "risk_score": 0.2311,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.23111129371756542,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.967365,
      "face_match_passed": true,
      "face_match_score": 0.7111108828530432,
      "reason": "below_threshold"
    },
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  },
  {
    "timestamp": "2026-11-02T05:43:05.820977+00:00",
    "diagnostic_id": "69a29c0f-d894-46de-b81e-3d6a6411419d",
    "session_id": "e348bfa9-4a0c-4a92-aac2-b3613e62fc4a",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "96160373-0672-4ab1-8333-73929bb5a306",
      "status": "approved",
      "risk_score": 0.2311
    },
    "challenge_id": "5aab715b-eaf8-4d29-9727-09f61a0b175b"
  }
]
```

### Genuine control — wcstudent1@example.com / e5cfb63d-4824-435f-ab17-e389b29345f3

Server accepted the participant's live face against their own enrollment; saved attendance status: approved. This is the genuine control, as confirmed by the participant.

| Passive frame | Evaluated | Depth | Mesh | Liveness | Depth / mesh gates | PAD status | PAD live score | PAD passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_frame | yes | 1.0 | 0.98946 | 0.997366 | not used | evaluated | 0.999994 | True |
| last_frame | yes | 1.0 | 0.98942 | 0.997354 | not used | evaluated | 0.999994 | True |

Sequence stop reason: passed.

```json
[
  {
    "timestamp": "2026-11-02T05:44:19.820921+00:00",
    "diagnostic_id": "0960b49f-3e71-40dc-abcb-7775108f5020",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "motion_challenge_issued",
    "values": {
      "max_duration_ms": 8000,
      "max_frames": 120
    },
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  },
  {
    "timestamp": "2026-11-02T05:44:39.085250+00:00",
    "diagnostic_id": "a160d3d0-6d22-423a-9304-f5c99ae8cba7",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "motion_verification_started",
    "values": {},
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  },
  {
    "timestamp": "2026-11-02T05:44:42.520061+00:00",
    "diagnostic_id": "a160d3d0-6d22-423a-9304-f5c99ae8cba7",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "motion_sequence",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.997354,
      "face_match_score": 0.8814813878371459,
      "diagnostics": {
        "frame_count": 51,
        "processed_frames": 51,
        "duration_ms": 4622,
        "last_frame_index": 50,
        "last_timestamp_ms": 4626,
        "identity_checks": 9,
        "face_match_threshold": 0.7,
        "liveness_threshold": 0.85,
        "ear_closed_threshold": 0.19,
        "ear_open_threshold": 0.23,
        "min_closure_ms": 40,
        "max_closure_ms": 700,
        "first_frame": {
          "evaluated": true,
          "frame_index": 0,
          "timestamp_ms": 4,
          "liveness_passed": true,
          "liveness_score": 0.997366,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.94678,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.98946,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.997366,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.997366,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.247366,
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
            "pad_live_score": 0.999994,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 1.0,
            "pad_v1se_live_score": 0.999989,
            "pre_pad_liveness_score": 0.997366,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 11.28,
            "pad_mode": "enforce",
            "pad_status": "evaluated",
            "pad_model_version": "minifasnet-v2-v1se-onnx-v1"
          }
        },
        "last_frame": {
          "evaluated": true,
          "frame_index": 50,
          "timestamp_ms": 4626,
          "liveness_passed": true,
          "liveness_score": 0.997354,
          "liveness_threshold": 0.85,
          "details": {
            "face_detection_confidence": 0.95025,
            "depth_score": 1.0,
            "mesh_plausibility_score": 0.98942,
            "texture_analysis_score": 1.0,
            "color_distribution_score": 1.0,
            "weighted_component_score": 0.997354,
            "presentation_integrity_score": 1.0,
            "challenge_evidence_score": 1.0,
            "challenge_integrity_score": 1.0,
            "threshold": 0.85,
            "pre_gate_liveness_score": 0.997354,
            "face_mesh_complete": true,
            "depth_detected": true,
            "weighted_contributions": {
              "depth": 0.3,
              "mesh": 0.247354,
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
            "pad_live_score": 0.999994,
            "pad_threshold": 0.75,
            "pad_v2_live_score": 1.0,
            "pad_v1se_live_score": 0.999989,
            "pre_pad_liveness_score": 0.997354,
            "pad_evaluated": true,
            "pad_passed": true,
            "pre_pad_liveness_passed": true,
            "pad_would_veto": false,
            "pad_inference_ms": 9.565,
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
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  },
  {
    "timestamp": "2026-11-02T05:44:43.108275+00:00",
    "diagnostic_id": "a160d3d0-6d22-423a-9304-f5c99ae8cba7",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "motion_verified",
    "values": {
      "passed": true,
      "blink_count": 2,
      "liveness_score": 0.997354,
      "face_match_score": 0.8814813878371459
    },
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  },
  {
    "timestamp": "2026-11-02T05:44:52.774349+00:00",
    "diagnostic_id": "81e682e6-5b9e-40e6-99af-262860780234",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "attempt_started",
    "values": {},
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  },
  {
    "timestamp": "2026-11-02T05:44:57.469466+00:00",
    "diagnostic_id": "81e682e6-5b9e-40e6-99af-262860780234",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "decision",
    "values": {
      "checkin_id": "b08e137c-bb53-4334-b586-952eb65d4c09",
      "status": "approved",
      "risk_score": 0.0948,
      "venue_risk_score": 0.0,
      "module3_risk_score": 0.09481488973028328,
      "effective_threshold": 0.5,
      "distance_meters": null,
      "radius_meters": 100.0,
      "accuracy_meters": 35.0,
      "liveness_available": true,
      "face_match_available": true,
      "module3_risk_available": true,
      "liveness_passed": true,
      "liveness_score": 0.997354,
      "face_match_passed": true,
      "face_match_score": 0.8814813878371459,
      "reason": "below_threshold"
    },
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  },
  {
    "timestamp": "2026-11-02T05:44:58.620340+00:00",
    "diagnostic_id": "81e682e6-5b9e-40e6-99af-262860780234",
    "session_id": "cd71fc39-72f3-4949-a95f-f5170ec3fc39",
    "stage": "attendance_committed",
    "values": {
      "checkin_id": "b08e137c-bb53-4334-b586-952eb65d4c09",
      "status": "approved",
      "risk_score": 0.0948
    },
    "challenge_id": "e5cfb63d-4824-435f-ab17-e389b29345f3"
  }
]
```

<!-- PHONE_REPLAY_DIAGNOSTICS_END -->
