# Impersonation diagnostics extension

Use the [test guide](impersonation-test-guide.md) for a new physical trial. This
extension adds an impersonation profile to the existing helpers; it does not
change recognition thresholds, templates, attendance policy or enrollment.

## Setup and reporting

`new-tests/prepare_video_replay.py --trial-type impersonation` requires distinct
`--control-account` and `--test-account` values before prompting for credentials
or creating sessions. It creates `Impersonation genuine_control ...` and
`Impersonation impersonation_test ...`, retaining the existing motion/liveness/
identity requirements. Configs record intended account, same-live-presenter
assignment and expected identity verdict. Partial failures preserve created IDs
and assignments with `setup_complete=false`; existing configs cannot be overwritten.
The original video-replay mode remains the default.

`new-tests/monitor_phone_replay.py --mode video` recognizes the impersonation config,
validates the role/account assignments, and reports identity scores, margins,
Hamming traces and saved attendance status. A failed challenge is classified as
identity mismatch only when its stop reason identifies identity failure and a
measured template comparison is present. Other capture/liveness/service failures
remain inconclusive for identity discrimination. A passed impersonation challenge
is highlighted even when attendance is not yet committed or later gets flagged.

Account/presenter assignments are operator-provided. They do not replace checking
the authenticated app account, actual presentation and saved attendance ownership.

## Added internal measurements

| Fields | Meaning |
| --- | --- |
| `simhash_bits`, `face_match_hamming_fraction` | Effective template size and configured Hamming boundary |
| `max_accepted_hamming_distance` | Largest integer distance accepted by the actual score mapping/cutoff |
| `matcher_version`, `score_mapping_version` | Algorithm/score-mapping identifiers; effective numeric calibration is recorded separately |
| `identity_comparisons` | Frame index/time, detection flag, Hamming-evaluated flag, measured distance/fraction, identity score and verdict |
| `min_hamming_distance`, `max_hamming_distance` | Extrema across all observed valid comparisons |
| `identity_comparisons_truncated` | Trace exceeded 64 entries; first 63 and most recent are retained |

Distances are recomputed from the exact request-local templates already compared
by the verifier, without additional face inference. An empty/no-face template or
diagnostic computation failure leaves the distance absent and
`hamming_evaluated=false`; it does not create a zero distance or alter verification.
The observer and backend project values onto fixed scalar schemas and cap the
trace. No images, embeddings, template hashes, credentials or SimHash seed are
included. Account email assignments exist only in the local operator config/report.

Both services must enable diagnostics for the same explicit session allowlist.
The normal face/sequence response is unchanged without opt-in. The backend student
response and persisted motion result still contain only their existing fields;
Hamming traces remain diagnostic output. Old reports display missing measurements
as unknown; the extension does not backfill historical data.

## API/specification scope

No endpoint or database schema is added. Existing backend login/course/session
setup, motion challenge/verification and check-in APIs are reused, alongside the
internal `POST /liveness/sequence` diagnostic projection. No new specification
conflict is introduced and `docs/` remains unchanged. Existing SimHash matching
and its score mapping remain unchanged; raising the score cutoff alone rescales
the score and does not tighten its underlying Hamming boundary.

## Validation

Tests use mocked setup requests, temporary SQLite, and isolated containers with
read-only repository mounts and no external networking. A real-model smoke uses
the bundled sample face, not a participant image. No trial sessions or attendance
were created in the existing application, and its services were not restarted.

| Check | Result |
| --- | --- |
| Setup/reporting regressions, including impersonation assignments | 67 passed |
| Backend diagnostics and persistence/privacy regressions | 35 passed |
| Face/motion/PAD/template regressions and real-model Hamming smoke | 137 passed; 1 pre-existing failure |
| Unchanged `tests/public/test_face_recognition.py` against disposable service | 15 passed |
| Protected documentation/history hashes, Python syntax, guide shell syntax and whitespace | Passed |

The existing failing case is
`test_pad_enforcement.py::test_all_ten_recorded_captures_under_real_scoring_function[photo-pad-20261102T040453Z-1fb76484]`.
It expects liveness to pass from a PAD score of 0.999795, although overall liveness
is 0.735096, below the unchanged 0.85 cutoff. The same assertion fails with the
original face-service source mounted in place of the changed files. Its assertion
and the liveness policy were left unchanged.

Build/recreate the two services as shown in the guide before the next trial; these
code changes were tested without deploying them into the running application.
