# P0-07 — Consent and browser permissions: execution record

Documentation IDs updated on 09 October 2026. Historical fixture names, run IDs, defect IDs, timestamps, and recorded outcomes are unchanged.

**Status: TERMINATED AT USER REQUEST — INCOMPLETE.** Ended 09 October 2026, 11:51:26 SGT. All services remain running. Steps 1–5 passed for the recorded coverage; Step 6 enrollment/motion repair retest passed, but live camera revocation did not clear evidence or prevent requests. Steps 7–12 were not run before termination. P0-07 is not a pass.

## Run and environment

- Run ID: `20261009-IT09-1041`; started 09 October 2026, 10:41 SGT (02:41 UTC).
- Plan: [P0-07-test-plan.md](P0-07-test-plan.md).
- Revision: `418764d81d9edb98854c0fa7bab36cceba14653c`, with pre-existing working-tree changes (three documentation deletions and untracked `new-documentations/test-logs/`). Application source has not been modified for this run.
- Host: participant's MacBook running macOS; browser Safari. Exact OS and Safari versions pending.
- M1 `http://localhost:3000`; M2 `http://localhost:8000/api/v1`; M3 `http://localhost:8001`; M4 `http://localhost:8501`.
- User explicitly requested real location instead of the plan's synthetic fixture: participant reported browser latitude `1.3479958295360819`, longitude `103.68084571096686`, accuracy `36 m`. Course and all six sessions use that venue and a 100 m radius. Browser tests must use fresh real geolocation, without DevTools overrides; later readings may differ and will be recorded independently.
- Temporary operator bearer tokens are confined to a mode-0600 state file in the backend container; no tokens, photos, templates, or passwords are included in this report.

## Preparation observations

| Check | Result | Observed evidence |
| --- | --- | --- |
| Docker access | PASS after access retry | All nine containers running; PostgreSQL, Redis, and M3 report healthy. A later sandboxed Docker call was denied access to the socket; retry through approved elevated Docker access succeeded. |
| M2 and DB connectivity | PASS | Container-side HTTP `/health` 200, `status=healthy`; `/db-health` 200, `database=connected`. |
| M3 reachability/dependencies | PASS for preliminary checks | `/health` 200, `/metrics` 200; `face_recognition` and `mediapipe` imports succeed. Actual model processing remains to be established by real enrollment/sequence steps. Import emitted a nonfatal matplotlib cache warning and used a temporary cache. |
| M1 page | PASS for HTTP reachability | HTTP 200 from service network. Browser rendering/login pending. |
| M4 page | PASS for HTTP reachability | Internal `Host: dashboard:8501` received 403; repeating with expected `Host: localhost:8501` received 200. This was a development-server host check, not an application failure. |
| M4 CORS | PASS for preflight | OPTIONS dashboard login with origin `http://localhost:8501` returned 200, matching allow-origin and `allow-credentials=true`. Browser authenticated reads pending. |
| Location bypass | Preliminary check clear | Running M1 variable `NEXT_PUBLIC_INTEGRATION_TEST_GEOLOCATION` is empty. Static bundle searches found neither the variable name nor P0-02's synthetic literal `1.3483,103.6831,10`. Actual permission denial must still establish browser-gate behavior. |
| Test identities | PASS | Dedicated admin/instructor/student registration 201 and login 200. Student `/users/me` 200; independent SQL confirms both consents false, face enrollment false, no template. |
| Fixtures | PASS | Course/enrollment/session creation 201; session activation 200. Active student enrollment read succeeds. All six sessions are active, liveness/face match required, risk threshold 0.5. Motion required except isolated photo variants. Staff-authenticated attendance read for S_MOTION returns `[]`. |

## Identity and fixture references

| Reference | ID |
| --- | --- |
| Student | `3c9bfb2f-e0a1-4f01-9429-6432a1539b60` |
| Instructor | `a460a7ec-053d-4778-8ffe-44e50d8122a6` |
| Admin | `5baaf56d-3271-4574-a385-720a50773775` |
| Course `IT09-20261009-1041` | `2758349f-9de4-4795-9a4b-f88fd087d17a` |
| Enrollment | `b6ec195c-63bd-4789-81ea-c72cd1c771c3` |
| S_MOTION | `e1ed1ed7-bc6a-45ef-b891-e85162adca8b` |
| S_GEO | `69cc3345-0e23-4bda-9ca2-c0af3e5b61b4` |
| S_PHOTO_A | `99db33c5-c94b-4a42-b049-49b1bf11ad85` |
| S_PHOTO_B | `044c528e-9f09-46fd-8d58-ea371d573feb` |
| S_PHOTO_C | `6da3da90-ea92-4f5d-9d83-d2a3662fa55a` |
| S_RECOVERY | `8ee1e086-32cb-4fea-8567-29611169c12b` |

All fixture windows close at **09 October 2026 16:49:53 SGT** (`08:49:53 UTC`). Recheck/extend through the API if needed before an attempt. Initial attendance count is zero for every student/session pair; initial student challenge count is zero. Device binding is disabled for this isolated test course as specified in P0-02; biometric policy is intact.

## Step results

| Step | Status | Evidence / next action |
| --- | --- | --- |
| 1 — Starting identity/consent | PASS | Participant confirms correct student name, selected S_MOTION, camera checkbox unchecked and camera button disabled, Safari camera/location site settings Ask, and Preserve Log enabled. SQL recheck at 11:00:41 SGT confirms camera/location consent false, enrollment false, no template, zero attendance, zero challenges; S_MOTION active with open window. Location checkbox appears only at the later location phase. Exact Safari version remains metadata pending. |
| 2 — Refuse application camera consent | PASS | Participant confirms button becomes enabled when checked and disabled again when unchecked, no permission prompt or live preview, and no rows for all three Network route filters. SQL at 11:03:23 SGT: both consents false, no enrollment/template, zero attendance and challenges. M2 access logs from 11:00:41 through 11:03:19 SGT contain only monitoring GET /metrics; no enrollment, motion, or check-in requests. |
| 3 — Deny browser camera permission | PASS | Participant reports “As expected” after denial/retry instructions: expected “Camera access is blocked. Allow it in your browser site settings, then retry.”, retry remains blocked, no live preview, stays at Camera access. Operator SQL at 11:07:00 SGT confirms both stored consents false, no enrollment/template, zero attendance/challenges. Backend access logs from 11:03:23 through 11:06:49 SGT show only GET /metrics; no enrollment, sequence, or check-in requests. Evidence is participant-reported browser behavior plus independently observed logs/SQL; no screenshot captured. |
| 4 — Restore camera/refuse location consent | PASS | Participant confirms live camera preview, advancement to Confirm your location, unchecked location consent, disabled Share precise location / Use current location button, and no location prompt. Independent SQL at 11:09:57 SGT confirms both stored consents still false, no enrollment/template, zero attendance/challenges. Restoring browser camera permission and starting preview did not persist stored camera consent. |
| 5 — Deny/recover browser location | PASS for reported denial/recovery behavior; coordinate metadata pending | Participant reports “Expected” after denial/retry instructions: “Location access is blocked. Allow precise location in site settings, then retry.” and remains at Confirm your location after blocked retry. SQL at 11:11:04 SGT confirms both stored consents false, no enrollment/template, zero attendance/challenges. Backend logs from 11:09:57 through 11:11:04 SGT show only monitoring GET /metrics, no enrollment/motion/check-in. Participant then reports “Expected” after restoration/retry instructions, indicating advancement to Set up face verification without a reported error. Fresh recovery SQL confirms both consents remain false, no enrollment/template and zero attendance/challenges. No override instructed; exact coordinates/accuracy for this application capture have not yet been observed and will be checked in subsequent payload/review evidence. |
| 6 — Revoke camera after verification | INCOMPLETE; observed revocation behavior FAIL, cause/coverage unresolved | Live repaired proof verified with two blinks and passing scores. After Safari Camera set to Deny, preview continued, evidence remained, and two check-in requests were sent (409 after proof expiry); zero attendance. Further Safari permission/track diagnostics and fresh denied-request check were not performed before termination. Do not count expiry rejection as consent enforcement or claim a post-revocation attendance write. Earlier failures retained. |
| 7 — Revoke captured location | NOT RUN | Requires fresh proof and real captured point; examine recovery UI. |
| 8 — Stored camera withdrawal/enrollment | NOT RUN | Requires participant-approved valid temporary photo from consented capture. |
| 9 — Stored camera withdrawal/motion stages | NOT RUN | Requires fresh valid frames/proofs for respective stages. |
| 10 — Stored location withdrawal | NOT RUN | Isolated S_GEO, valid fresh proof; any write is a failure. |
| 11A/B/C — Legacy photo consent | NOT RUN | Separate photo sessions; retain any defect rows. |
| 12 — Fresh recovery and M4 read | NOT RUN | Untouched S_RECOVERY; real biometrics and exactly one approved row required. |

## Defects and cleanup

### Step 6 camera revocation observation — investigation IT09-OBS-02

Participant subsequently reports Network 409 and preview still moving. M2 logs show **two** consent PUTs (200) followed by check-in POSTs (409) at 11:41:29 and 11:41:34 SGT, both after proof expiry at 11:40:23. SQL at 11:42:19 SGT confirms zero attendance, proof remains `verified`/unconsumed, and both stored consents are now true (M1 persisted the checked flags before failed submission). Given the expired proof, zero attendance does not prove browser-consent enforcement; the HTTP rejection is consistent with the motion expiry gate. Local evidence was not cleared and submission was not blocked. Whether Safari reports live camera permission changes or terminates existing tracks still needs read-only browser diagnostics and a fresh denied request after reload; do not claim the live-revocation requirement passed.

Participant set Safari localhost Camera to Deny and reported “Nothing in M1 changed. I haven't clicked submit check in.” Local evidence clearing and revocation detection therefore have not been demonstrated; participant has not yet attempted submission. SQL at 11:40:07 SGT: prepared proof `afeaa3eb-a9f8-4860-9225-6c92c4f37ce4` still verified/unconsumed, expires 11:40:23 SGT; attendance zero. Stored camera consent true and location consent false (browser permission change is distinct from stored withdrawal). Next attempt will examine whether M1 sends a check-in request while site Camera remains denied. Proof expiry may prevent an attendance write, but an expiry rejection cannot establish a working local revocation gate. Actual stream movement, track state, and Safari permission-query support still need clarification before assigning a cause.

### IT09-D01 repair — approved and automated verification

**Live repair retest PASS:** participant reports verification succeeded. SQL confirms challenge `afeaa3eb-a9f8-4860-9225-6c92c4f37ce4` on S_MOTION is verified with two server blinks and passing scores, while attendance remains zero. IT09-D01 reproduced failure is retained; repair verified for this participant/capture. This does not certify accuracy across other users/cameras or complete P0-07.

Participant explicitly approved application repair. Operator reviewed M1 capture/model and check-in flow, M2 motion/proof and face-service contracts, M3 sequence/identity/liveness/error handling and packaging, and M4 attendance mapping; no contract conflict found. Changed M3 sequence landmarks to a fresh Tasks FaceLandmarker VIDEO tracker using a bundled byte-identical copy of M1's version-1 float16 model (SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`). Missing/corrupt assets and native inference errors fail closed. Original sequence limits, blink thresholds/timing, identity sampling, passive liveness, consent checks, and proof rules remain intact. Updated motion documentation and regression tests; no backend/frontend/dashboard source changes.

- Host Python 3.12: temporal/landmark/backend-wrapper suite **23 passed in 2.17 s**. The backend wrapper runs its isolated motion cases; mocked transport does not prove native accuracy.
- Isolated M3-container native environment: temporal, new landmark checks, native static-photo/unavailable-model checks, and existing M3 regressions **47 passed in 6.40 s**, two warnings, no skips. Covers model parity, no/multiple faces, abrupt movement, native inference failure, missing/corrupt model HTTP 503, retained static-photo rejection, and existing identity/privacy/risk behavior.
- `git diff --check` passed. Original pre-existing documentation deletions remain untouched.
- Rebuilt and recreated only M3 through Compose; deployed image ID `d55e6281f95f41cfd0da3df8d8f4efa3584948225665c7518165c336be3b79f3`. M2-to-M3 health returned 200; deployed bundled model digest matches and Tasks initialization succeeds. Native initialization warnings are nonfatal.
- Deployed public HTTP face suite **15 passed in 3.06 s**, no skips (15/15 scoring points).
- SQL at 11:34:07 SGT: camera consent true, location consent false, face enrolled/template present, zero attendance; S_MOTION active with window open. Database/student fixtures retained.
- Live positive capture and remaining P0-07 steps still pending; automated passes do not close IT09-D01 without participant retest. Browser must restore original fetch/remove the temporary diagnostic hook before live retry.
- Operator stopped the localhost diagnostic listener after evidence capture. M3 recreation discarded its temporary analyzer/model comparison files. No participant images or frames were saved to disk.

### IT09-D01 — incompatible eye measurements between M1 and M3 (reproduced)

At 11:27 SGT, challenge `72c38b44-9839-4b82-b142-f31d96da3c6e` on S_MOTION failed: server blink count 0, liveness `0.98546`, face match `0.8962962143575026`; attendance remains zero. Diagnostic compared **the exact same 22 submitted JPEG frames**, spanning 1,941 ms, with unchanged blink thresholds/counter:

| Model path | Blink count | EAR at first closure (frame 7) | EAR at second closure (frame 20) |
| --- | --- | --- | --- |
| Current M3 Solutions FaceMesh tracker | 0 | 0.24630 | 0.24505 |
| Solutions FaceMesh static-image mode | 0 | 0.20060 | 0.20798 |
| M1 Tasks FaceLandmarker model, replayed in M3 diagnostic | 2 | 0.07823 | 0.06946 |

Both Tasks closures fall below 0.19 and reopen above 0.23 within the existing 40–700 ms window. All current M3 tracker frames contain exactly one face with low movement. This demonstrates a model-dependent landmark measurement mismatch, not absence of blink evidence in submitted images, missing native dependencies, or stale application files. Merely switching Solutions to static-image mode would not fix this capture. The proposed repair is to align M3 sequence eye landmarks with the existing M1 Tasks model while retaining server-side identity/passive-liveness checks, sequence validation, blink thresholds, consent gates, and proof consumption rules. No repair has been applied; this run remains incomplete, with proof-dependent consent tests blocked. Earlier IT09-OBS-01 evidence is retained below and now supports IT09-D01.

### IT09-OBS-01 — per-frame diagnostic (11:23 SGT)

Longer capture at 11:25 SGT: challenge `da9c7749-8da0-4d6a-8b08-08f579caf962`, S_MOTION, failed with zero server blinks, liveness `0.985328`, face match `0.9555555204389297`; attendance zero. Diagnostic: 30 frames over 2,681 ms, exactly one face in each, EAR range 0.22574–0.31883, maximum nose jump 0.0037. Neither apparent blink minimum crosses 0.19. Repeating ordinary capture has not resolved this blocker. Expanded temporary analyzer to compare Solutions static-image landmarks and M1's Tasks model on the exact same submitted JPEG frames; copied only the existing model asset into M3's temporary directory and passed a synthetic blank-frame self-test for both comparison paths. Application policy and source remain unchanged. Step 6 live revocation still cannot be tested without a valid proof.

Challenge `f2a2c08c-7af9-46ef-9fca-0b8b49360a70`, S_MOTION, failed; liveness `0.98163`, face match `0.9481481071787513`, server blinks 0, attendance zero. Diagnostic successfully analyzed 19 frames spanning 1,652 ms (timestamps 21–1,673 ms; consecutive gaps 84–95 ms). Exactly one face tracked in every frame; maximum normalized nose displacement 0.0052, below the 0.15 motion rejection threshold. Server eye aspect ratios range 0.23930–0.33125; minima at 653 ms (0.23930) and 1,578 ms (0.25324). No frame crosses the server's closed-eye threshold (<0.19), so the counter cannot register closure/reopening. This establishes absent server closed-eye measurements for this capture, rather than dropped face tracking or missing frames. It does not establish whether model differences, capture timing, or brief/incomplete closure caused the mismatch. Next controlled capture will hold each closure roughly 0.4 s, reopen fully between them, and preserve policy/thresholds; diagnostic remains active.

Diagnostic attempt: participant console reported `IT09 diagnostic {error: "Native diagnostic failed"}`. Application challenge `c1ebf75a-3efe-4fa9-95e7-56efed88493d` on S_MOTION still independently failed with server blink count 0, liveness `0.976068`, face match `0.9481481071787513`; attendance zero at 11:22:35 SGT. Analyzer startup failed because a script under `/tmp` lacked `/app` on Python's import path (`ModuleNotFoundError: app`), an operator diagnostic setup error rather than application dependency failure. Corrected temporary script import path and verified it using 15 in-memory synthetic blank JPEG frames: exit 0, expected zero faces/blinks, valid sanitized JSON output. Participant image payload from the failed diagnostic was discarded, so a fresh sequence is needed; no application source or policy changed.

### Step 6 — first motion attempt, unsuccessful (11:13 SGT)

- Participant saw: “The server could not verify your face and two blinks. Please retry.”
- M2 issued challenge `d4fe6085-3cfe-4bc8-b7bd-3a26d0f29993` at 11:13:43 SGT (201), and verification returned 200 at 11:13:54 SGT with an unsuccessful biometric result. SQL state `failed`; `passed=false`, `blink_count=0`, `liveness_score=0.979006`, `face_match_score=0.9481481071787513`. Zero attendance remains. This is an unsuccessful capture, not an HTTP/service outage; exact cause of zero server blinks is not yet established.
- **Fixture discrepancy:** SQL ties this challenge to `044c528e-9f09-46fd-8d58-ea371d573feb` (S_PHOTO_B), rather than S_MOTION. Earlier participant confirmation of selected S_MOTION conflicts with this independently observed attempt. Do not attribute this motion attempt to S_MOTION. Reconfirm selected session after reload before retry. The photo fixture still has zero attendance and remains preserved.
- Operator's initial read used nonexistent `motion_challenges.created_at`; corrected to ordering by `expires_at`. No database mutation occurred.
- Live camera revocation remains NOT RUN within Step 6 until a valid proof has been prepared on the intended fixture.

Step 6 retry: participant reports “Sequence ready. 2/2”. SQL at 11:16:07 SGT confirms fresh challenge `019ee4cd-c88b-4bc7-827a-ea6e30f2db73` belongs to S_MOTION (`e1ed1ed7-bc6a-45ef-b891-e85162adca8b`), state `issued`, no result yet, expires 11:18:42 SGT. Attendance remains zero. Browser-local blink detection is confirmed by participant; server verification remains pending.

Step 6 retry result: participant again reports “The server could not verify your face and two blinks. Please retry.” SQL confirms the S_MOTION challenge is now `failed`, `passed=false`, `blink_count=0`, `liveness_score=0.980423`, `face_match_score=0.9777777602194648`. Zero attendance. Browser 2/2 versus server 0 is a reproduced disagreement (investigation reference IT09-OBS-01); root cause remains unconfirmed. Browser uses MediaPipe Tasks FaceLandmarker and M3 uses MediaPipe Solutions FaceMesh on JPEG frames, with matching blink thresholds (open >=0.23, closed <0.19, closure/reopening 40–700 ms). No missing-model/service-unavailable error observed. A controlled fresh capture with clearly separated blinks will be attempted before any code change; consent revocation portions still require a valid proof.

Controlled retry also failed: challenge `7bac2250-b130-4d61-894d-c14705ea4101` on S_MOTION, SQL at 11:18:58 SGT: `state=failed`, `passed=false`, `blink_count=0`, liveness `0.960007`, face match `0.9111110408778594`; attendance zero. Running M3 motion/liveness/imaging file hashes match repository source, ruling out stale versions of those files. Temporary diagnostic scripts installed outside application source: localhost-only operator listener (port 8765) and M3 frame analyzer. Next sequence will be processed in memory to emit only per-frame timestamp, face count, eye aspect ratio, nose displacement, and blink count. No image/frame payload files or templates are saved; original application request/result will be preserved. Root cause and live-revocation coverage remain pending.

Step 6 enrollment corroboration: M3 metrics after enrollment show exactly one successful POST `/face/enroll` (`2xx`) and `face_operation_outcomes_total{operation="enroll",outcome="success"}=1`; request duration approximately 1.036 s. Preliminary pre-enrollment metrics had no enrollment series. This corroborates native M3 processing alongside the M2 response and SQL write.

## Termination and cleanup

User explicitly requested termination with services left running. At 11:51:26 SGT, admin API closed all six P0-07 sessions; independent SQL confirms each `status=closed`. Dedicated accounts, course, enrollment, template, and remaining challenge metadata are preserved. Student attendance count is zero. Temporary operator credential state and setup script removed from the backend container; diagnostic listener was already stopped and participant image/frame inputs were never saved to disk. All nine containers are still running, M3/PostgreSQL/Redis healthy. Approved M3 repair remains deployed.

Browser sign-out/camera stop and restoration of preferred Safari permissions require the participant; operator has not controlled the browser and does not claim these were completed. Exact Safari version/OS version and application-capture coordinates remain metadata limitations. Steps 7–12, including stored location consent and legacy photo consent enforcement, remain untested; plan expectations are not findings. No further tests will run in this terminated session.
