# Integration test cases by priority

Priority now follows the supplied evaluation slide: **P0 covers the hidden-test focus areas and the prerequisites needed to exercise them**, P1 covers other core workflows, and P2 covers supporting workflows/gap review. IDs restart at 01 within each priority group. Start with P0-01 deployment readiness, then [P0-02 happy path](P0-02-test-plan.md), before testing negative scenarios.

The slide is titled “System Feature: 40 Hidden Tests” and gives **points**, not individual test definitions: Advanced Security 12, Privacy Audit 8, Face Recognition Advanced 10, Liveness 3, and Stress Testing 7 (40 points total). It explicitly names GPS spoofing, replay prevention, network security, database inspection for raw images, encryption verification, real attack images, and 100 concurrent users. The mapping below is proposed coverage of those focus areas; it does not claim knowledge of all 40 private tests, exact pass thresholds, or a one-case-per-point correspondence.

Prepared/reprioritized: 09 October 2026. **Documentation only; no tests executed for this update.** New entries describe acceptance tests to plan/run; they are not automated test implementations or passing results. Missing implementation remains required P0 coverage and must be recorded as FAIL/NOT IMPLEMENTED or BLOCKED as applicable.

## P0 — Evaluation security, privacy, biometrics, liveness, and stress coverage

- **P0-01 — Browser deployment contracts:** Check credentialed CORS/preflight and API base URLs for both apps, localhost/HTTPS permissions, and a mobile browser deployment; ensure host/container URLs are not confused.
- **P0-02 — Happy path:** Register, authenticate, enroll the face, complete real two-blink verification, submit one approved attendance, and verify database persistence, M4 visibility, and monitoring. Follow the [test plan](P0-02-test-plan.md) and [execution record](P0-02-test-result.md).
- **P0-03 — Authentication failures:** Exercise duplicate registration, invalid fields, incorrect credentials, expired/invalid tokens, and inactive accounts; confirm errors reach both clients without unauthorized data changes.
- **P0-04 — Role and data isolation:** Use actual student/TA/instructor/admin accounts to check read/write permissions, personal-history isolation, instructor course scope, and admin layout previews; record current TA session-list and staff ownership gaps.
- **P0-05 — Session lifecycle and time boundaries:** Test scheduled/active/closed/cancelled states, opening/closing instants, activation, and timezone handling across M4 creation, M1 discovery, M2 eligibility, and SQL.
- **P0-06 — Enrollment eligibility:** Test missing/inactive enrollment and inactive courses; ensure session visibility is not mistaken for permission and document current course-active enforcement behavior.
- **P0-07 — Consent and browser permissions:** Deny/revoke camera or location permissions, withdraw stored consent, and retry; verify capture gates, enrollment/motion enforcement, and the legacy photo API consent gap. Follow the [step-by-step test plan](P0-07-test-plan.md) and [execution record](P0-07-test-result.md).
- **P0-08 — Venue inheritance and geofencing:** Exercise course defaults, session overrides, exact radius/twice-radius boundaries, missing venue configuration, poor accuracy, and out-of-range coordinates; compare decision, distance, and saved risk factors.
- **P0-09 — Failed liveness or identity:** Test insufficient blinks, incomplete reopening, a different person's face, multiple faces, and abrupt movement; ensure no usable proof is issued and attendance is not approved through required motion. Follow the [step-by-step test plan](P0-09-test-plan.md).
- **P0-10 — Proof ownership and reuse:** Try another student/session's verification ID, failed/unverified IDs, and reused consumed proof; confirm rejection without extra attendance or unintended challenge changes.
- **P0-11 — Duplicate and concurrent attendance:** Submit twice and race independent requests for the same student/session; verify one record, a useful error rather than an unhandled database exception, and consistent proof consumption.
- **P0-12 — Database transaction failures:** Inject an attendance insert/commit failure and verify proof consumption rolls back, no partial attendance remains, and later reads show a consistent state.
- **P0-13 — M3 outage and malformed responses:** Interrupt enrollment/sequence/photo calls; required motion/enrollment must not fabricate success, while the legacy photo path's geofence-only fallback must be documented and its biometric fields remain NULL.
- **P0-14 — Photo check-in:** For a session without mandatory motion, select the photo alternative; verify M2 calls M3 passive liveness, face verification, and risk assessment as applicable, then persists and displays the result.
- **P0-15 — Enrollment rejection and recovery:** Submit no-face, multiple-face, blurred, low-quality, malformed, and oversized images; verify M3 errors map through M2 without persisting a successful enrollment.
- **P0-16 — Sequence contract limits:** Exercise frame-count/body limits, duplicate/reordered timestamps, excessive gaps, short/long capture, and invalid images; verify bounded errors without biometric reflection or database leakage.
- **P0-17 — Challenge lifetime and replacement:** Expire, resubmit, cancel/restart, replace, or re-enroll during a challenge; verify stale evidence cannot be used and a fresh eligible attempt can succeed.
- **P0-18 — Refresh and logout:** Verify M1 cookie restoration/one-time 401 retry and both apps' sign-out state; expose M4's missing token refresh and the absence of server-side access-token revocation.
- **P0-19 — Browser interruption and retry:** Hide the tab, stop/revoke camera access, switch sessions, or retake evidence mid-flow; verify stale frames/proof cannot silently complete the wrong lecture.
- **P0-20 — Large datasets and 100-user stress:** Exceed 100 sessions/courses/personal records and verify complete pagination. Run 100 distinct enrolled students concurrently against real PostgreSQL/M2/M3, using separate credentials and fresh student/session-bound evidence. Measure login, enrollment, sequence verification, final submission, and dashboard reads separately, then run a mixed workload and repeated waves. Check exact attendance counts, no cross-user proof/score mixing, no deadlocks/unhandled 5xx, bounded timeouts/resources, and successful recovery. Record achieved simultaneous requests, throughput, success rate, p50/p95/p99 latency, CPU/memory, and pool usage; state whether evidence was captured live or from consented fixtures. Ten parallel logins, sequential submissions, or a run with biometric checks disabled do not satisfy this case. Apply evaluator latency/error targets when supplied; do not invent them.
- **P0-21 — Monitoring failures and privacy:** Stop/restart Prometheus or the collector, disable telemetry, and inspect bounded labels/logs/storage; verify attendance independence, recovery, and absence of raw biometrics/credentials in telemetry.
- **P0-22 — GPS spoofing detection beyond geofencing:** Use a consenting test participant or declared synthetic fixture, and compare valid in-venue check-in with DevTools/mock-location coordinates, an API-edited in-range location from an out-of-venue fixture, impossible jumps between attempts, and forged accuracy/location metadata. Keep identity/session eligibility valid. Inspect the risk decision and persisted reasons; suspicious location evidence must be detected and handled by the documented policy rather than silently accepted as trusted. A radius check alone proves geofencing, not spoof detection. Record missing trusted-location or cross-signal detection as a gap; do not claim a server can distinguish identical client coordinates without additional evidence.
- **P0-23 — Network security and request tampering:** Exercise disallowed/forged Origins, credentialed preflight, bearer-token tampering and algorithm/signature errors, cross-role registration attempts, unauthorized direct M3 access in the intended deployment, forged proxy/IP headers, SQL-injection strings, and stored/reflected XSS inputs. Inspect browser output, API errors, database changes, and internal-service exposure. Expect authentication/authorization enforcement, exact origin allowlisting, parameterized queries, inert user content, and no secret/error leakage. Verify proxy/VPN risk signals reach the actual M2 attendance decision where claimed; a standalone M3 risk response does not establish end-to-end enforcement. Preserve legitimate traffic as a control.
- **P0-24 — Rate limiting and abuse isolation:** In an isolated environment, exceed the documented limits from docs/SECURITY-REQUIREMENTS.md: login 60/hour/IP, registration 10/hour/IP, API 1000/hour/user, and check-in 10/minute/user. Check the boundary and next request, parallel bursts, independent users/IPs, window expiry, and limiter dependency failure. Expect documented throttling (429 and retry information where specified), no excess writes, and fresh permitted requests after expiry. A wrong-password 401 is not rate-limit evidence. Missing limiting is FAIL/NOT IMPLEMENTED, not a pass because public tests tolerate it.
- **P0-25 — Fresh-challenge evidence replay and attestation replay:** Capture a consented passing sequence once and replay the identical frames into a fresh challenge for the same user/session, a different session, and another student; also replay a recorded blink video shown to the camera and stale photo evidence on the supported photo path. Keep all unrelated eligibility checks valid. Test any exposed device-attestation interface with repeated challenge/signature pairs and wrong key/user/session binding. Require documented freshness/binding controls and no approved attendance from replay. Consumed verification-ID rejection alone does not prove frame/video freshness; a valid signature alone does not prove a one-time challenge. Record unbound frames or unattached attestation enforcement as gaps.
- **P0-26 — Database and storage inspection for raw biometrics:** Enroll, verify, submit, fail, and retry with real consented test images; inspect all application tables/column types and stored values, including users, checkins, motion_challenges, audit_logs, risk records, and any additional schema tables. Inspect service volumes, temp files, caches, and backups produced during the run after request completion and restart. Check for image bytes/base64, full embeddings, landmarks, and hidden copies rather than relying only on field names or API responses. Expect no persisted raw biometric evidence; permitted stored templates and scalar outcomes must match the documented minimization contract. Use protected local inspection and save only redacted findings, not biometric dumps.
- **P0-27 — Encryption and cryptographic protection verification:** Inventory persisted PII/biometric templates, database volumes/backups, credentials, signing keys, and any transport encryption configuration. Verify password bcrypt algorithm/cost against the security requirements, JWT signing/key source, and whether sensitive storage/backups have actual encryption and controlled keys; test ciphertext/tamper behavior where an encryption mechanism exists. Distinguish encoding, password hashing, and cancelable SimHash templates from encryption, and record the schema's SHA-256 terminology mismatch. The supplied slide requires encryption verification but does not define data/scope; record the evaluator-required scope as unresolved until available. Project docs explicitly exempt TLS, so absence of TLS is not automatically a project-contract failure. If evaluator-required encryption is absent, report NOT IMPLEMENTED/FAIL; never treat a 64-hex template or base64 as proof of encryption.
- **P0-28 — Real-image presentation attacks and anti-spoofing:** With consented participant photos and documented real attack-image fixtures, test printed photographs, faces displayed on phone/laptop screens, cropped/resized/compressed attack images, and recorded blink videos. Exercise M3 passive liveness and the full M1 → M2 → M3 photo/motion routes under required biometric policies; include real live-person positives and different-person negatives. Expect spoof rejection/no usable motion proof and no approved attendance from attacks. Report per-attack scores, decisions, false accepts and false rejects, fixture provenance, lighting/device conditions, and active thresholds; do not tune thresholds on evaluation inputs. Synthetic uniform images, two detected blinks, or a unit-test mock do not replace real attack-image evidence.
- **P0-29 — Privacy audit, retention, and data-access acceptance:** Generate actual login, enrollment, rejected/approved check-in, and export events; inspect persisted audit events, admin-only access, append-only behavior, and sanitized details. Inspect self/admin API responses and exports for passwords, hashes, raw biometrics, templates, credentials, and unrelated users' PII. Exercise the documented retention/deletion workflow with expired isolated records, check retained records and audit invariants, then verify removal through independent SQL/API reads and relevant stores. Consent withdrawal is covered by P0-07 and does not automatically prove deletion. A scheduled-deletion column or an empty audit response is insufficient; absent cleanup is NOT IMPLEMENTED/BLOCKED. This is inferred supporting privacy coverage from project requirements, not a disclosed individual hidden test.

## P1 — Other core workflows

- **P1-01 — Offline operation:** Verify sanitized, unexpired session-cache reads, expired-cache removal, and disabled real submission; confirm there is no attendance queue or background write from the inactive prototype.
- **P1-02 — Dashboard refresh and transformation:** Check polling after new attendance, sorting/course/session/status filters, risk scaling, timezone display, pending/rejected status mapping, course average risk, and trends spanning multiple dates.

## P2 — Supporting workflows and remaining feature-gap review

- **P2-01 — CSV consistency:** Export filtered/session attendance and compare IDs, status, risk units, quoting, and timestamps with M2/SQL; expose missing identity, biometric, location, and room fields rather than treating fallback values as real data.
- **P2-02 — Device API persistence:** Exercise registration/re-registration, ownership conflicts, inventory, trust updates, revocation, and deletion; verify database reads and explicitly track that check-in device binding/attestation is not connected.
- **P2-03 — Remaining feature-gap review (not an executable test):** Review staff assignments, reviews/appeals, QR attendance, device binding/attestation integration, and remaining dashboard/metrics contracts. Verify current implementations before labeling them missing. Privacy audit/retention requirements are executable acceptance cases under P0-29; do not leave them only in this backlog. Mark each genuinely absent feature NOT IMPLEMENTED/BLOCKED until acceptance can be exercised.

## Evaluation coverage map

Every P0 case appears below. A prerequisite/control case helps execute and diagnose a category; it does not by itself prove that category passes. Cases may contribute to multiple categories, so point totals must not be allocated to individual cases without the evaluator's rubric.

| Evaluation category | Slide points | P0 coverage | Coverage rationale |
| --- | --- | --- | --- |
| Advanced Security | 12 | P0-01–P0-06, P0-08, P0-10–P0-13, P0-16–P0-19, P0-22–P0-25 | Deployment/auth/access controls and valid control flow; session/window binding; geofence versus spoof detection; proof and raw-evidence replay; duplicate/rollback integrity; dependency failure; request limits; token/browser stale state; network tampering and abuse controls. |
| Privacy Audit | 8 | P0-02, P0-04, P0-07, P0-15–P0-16, P0-21, P0-26–P0-27, P0-29 | Real persisted control data; consent and isolation; rejected-payload minimization; telemetry leakage; database/storage inspection; cryptographic protection; audit, retention, response/export minimization. |
| Face Recognition Advanced | 10 | P0-02, P0-09, P0-13–P0-15, P0-28 | Real enrollment/identity controls, failure propagation, supported photo path, malformed/low-quality enrollment, and actual printed/screen/video presentation attacks. |
| Liveness | 3 | P0-02, P0-09, P0-13–P0-14, P0-16–P0-17, P0-25, P0-28 | Positive two-blink control; incomplete blink/reopening and passive-liveness negatives; fail-closed processing; temporal contracts and fresh challenge/evidence; recorded-video attacks. |
| Stress Testing | 7 | P0-11–P0-12, P0-16, P0-20, P0-24 | Duplicate races/atomic rollback, bounded hostile payloads, real 100-user workloads with resource/latency/error evidence, and isolation of abusive traffic. |

## Execution and necessity notes

- All previous cases are retained. Eight explicit acceptance cases (P0-22–P0-29) fill missing or previously implicit coverage. P0-20 now explicitly requires 100 concurrent users; a public ten-login test is insufficient.
- Related previous P1 cases moved to P0 because they exercise security, privacy, face/liveness, or load boundaries. P1-01 offline browsing and P1-02 dashboard transformations remain required supporting core checks. CSV consistency and device record CRUD remain P2; security/privacy of exports and replay/binding are explicitly tested under P0-23/P0-25/P0-29.
- Keep shared fixtures where safe, but record separate assertions: geofencing is not spoof detection, proof consumption is not raw-frame freshness, blink counting is not presentation-attack protection, and template hashing is not encryption.
- Use real native models and PostgreSQL for biometric/load acceptance. Mocked contract tests remain useful supplements. Validate 100 simultaneous users with separate accounts; do not reuse one person's evidence across accounts as if it were genuine identity coverage.
- Record PASS / FAIL / BLOCKED / NOT RUN per scenario, actual decisions, sanitized evidence, fixture provenance, and unresolved evaluator thresholds. Keep existing failures and historical logs. An unavailable feature is not a passing test or a reason to downgrade its priority.
- The current source includes audit and metrics implementations; verify them rather than assuming older inventory statements that they are missing still apply. Retention, trusted GPS, evidence freshness, network-signal integration, and encryption need direct checks; this document does not assert they are implemented.
- TLS/encryption expectations require scope reconciliation: [security requirements](../../docs/SECURITY-REQUIREMENTS.md) and [API specification](../../docs/API-SPECIFICATION.md) exempt TLS, while the supplied evaluation slide does not define encryption scope. Record this uncertainty in P0-27 instead of inventing a requirement or silently waiving encryption verification.

## ID migration and existing log files

Existing P0-01–P0-13 IDs remain unchanged, including the happy-path, consent, and liveness plans/results. No existing log filename needs another rename. References to promoted P1 cases in those documents are updated; historical outcomes, fixtures, and defect IDs remain unchanged.

| ID before evaluation reprioritization | Current ID | Case |
| --- | --- | --- |
| P1-01 | P0-14 | Photo check-in |
| P1-02 | P0-15 | Enrollment rejection and recovery |
| P1-03 | P0-16 | Sequence contract limits |
| P1-04 | P0-17 | Challenge lifetime and replacement |
| P1-05 | P0-18 | Refresh and logout |
| P1-06 | P0-19 | Browser interruption and retry |
| P1-09 | P0-20 | Large datasets and 100-user stress |
| P1-10 | P0-21 | Monitoring failures and privacy |
| P1-07 | P1-01 | Offline operation |
| P1-08 | P1-02 | Dashboard refresh and transformation |

### Original IT identifiers

| Original case-list ID | Current ID |
| --- | --- |
| IT-01 | P0-02 |
| IT-02 | P0-01 |
| IT-03 | P0-03 |
| IT-04 | P0-04 |
| IT-05 | P0-05 |
| IT-06 | P0-06 |
| IT-07 | P0-07 |
| IT-08 | P0-08 |
| IT-09 | P0-09 |
| IT-10 | P0-10 |
| IT-11 | P0-11 |
| IT-12 | P0-12 |
| IT-13 | P0-13 |
| IT-14 | P0-14 |
| IT-15 | P0-15 |
| IT-16 | P0-16 |
| IT-17 | P0-17 |
| IT-18 | P0-18 |
| IT-19 | P0-19 |
| IT-20 | P1-01 |
| IT-21 | P1-02 |
| IT-22 | P0-20 |
| IT-23 | P0-21 |
| IT-24 | P2-01 |
| IT-25 | P2-02 |
| IT-26 | P2-03 |

The consent documents originally used IT-09 headings while the renumbered case list identified consent as IT-07. They remain P0-07 by subject. The former liveness/identity case remains P0-09. Historical IT09 defect/fixture identifiers are preserved.
