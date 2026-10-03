# Integration test results

Run started: 2026-10-03 01:31 UTC.

Run completed: 2026-10-03 02:58 UTC, including browser sign-out.

Code revision: `048c53b1ce7b296b0da3c7ed9b7f8a54e7cc20f2`. Run ID: `20261003-0131`.

Plan: [integration-test-plan.md](integration-test-plan.md). IT-01 passed after the retained failed attempts and environment repairs below. Every coordinate in this report is a synthetic fixture value; it does not represent or imply the user's physical location. No physical location was collected or inferred, and physical GPS is not claimed.

## Execution policy

- Run IT-01 in order, retaining failed attempts and recording setup adjustments.
- Use dedicated test data/database; preserve existing volumes and records.
- Operator runs browsers, API requests, SQL checks, and log inspection. Request the user's participation for real webcam evidence.
- Do not save passwords, tokens, raw photos/frames, embeddings, or landmarks in this report.
- PASS means observed evidence meets the step's criteria. FAIL means observed behavior differs. BLOCKED means a prerequisite prevents completion. NOT RUN means the step has not yet been attempted.

## Environment and preparation

| Check | Result | Observation |
| --- | --- | --- |
| Initial working tree | Recorded | Existing untracked files: `list-of-features-02OCT.md` and `new-documentations/integration-test-plan.md`; preserved. |
| Docker access, first attempt | BLOCKED, resolved | Sandbox denied access to Docker socket. Retried with user-approved Docker permission. |
| Docker availability | PASS | Docker Desktop 4.93.0; client/server 29.8.1; Linux ARM64 daemon. |
| Initial Compose state | PASS | No services running for this project. |
| Existing data isolation | PASS | `docker volume ls` returned no volumes before startup. The newly initialized local `saiv` PostgreSQL database is dedicated to this integration run. |
| Compose build/start | PASS | All nine services are running; PostgreSQL, Redis, and M3 report healthy. Compose warns that top-level `version` is obsolete. M1 logs that `next start` is used despite standalone output, but the server is available. |
| M2 health | PASS | `GET /health` → 200 `{"status":"healthy"}`; `GET /db-health` → 200 `{"database":"connected"}`. |
| M3 health | PASS | Container health check passes and service startup completed. |
| M4 default CORS | FAIL, resolved for retry | Dashboard-origin preflight `OPTIONS /api/v1/auth/login` with origin `http://localhost:8501` → 400 `Disallowed CORS origin`. M2 initially allowed only M1 at port 3000. Added the explicit localhost dashboard origin to M2's credentialed allowlist, rebuilt M2, and observed retry → 200 with `Access-Control-Allow-Origin: http://localhost:8501`. Initial failure retained. |
| M4 login UI attempt | FAIL, fix ready for retry | After entering the instructor email, the page stopped responding to user clicks and no M2 login request appeared. Earlier console evidence reported invalid HTML nesting/hydration: M4 rendered an `<html>` document inside Vite's existing `#root` div. Removed the incompatible router document shell, rebuilt M4, and passed `npm run build` (175 modules; 511 ms). Restarted M4 for a user-driven browser retry; the initial failure is retained. |
| M1 synthetic location setup | PASS for retry | The ChatGPT in-app browser timed out without returning coordinates. Added an opt-in build-time fixture, rebuilt M1 with the configured venue point `1.3483, 103.6831` and 10 m accuracy, and restarted only M1. Next.js compilation and type checking passed; the running container serves `/` with 200 and its client bundle contains the fixture. Normal builds remain on browser geolocation when the variable is absent. This validates the application integration path, not physical GPS. The dependency install also reported 16 known audit findings (15 high, 1 critical); they were not changed during the run. |
| Cross-app localhost authentication | FAIL, retry setup required | Reloading M1 after the synthetic-location rebuild restored the instructor through the backend's host-wide `saiv_refresh_token`, which had most recently been replaced by the M4 instructor login. M1 did not reject the non-student role and allowed the check-in UI to proceed. The first synthetic-location/enrollment attempt therefore ran as the instructor. The attempt is retained; M1 must be explicitly signed out and signed back in as the student before retrying. |
| Grafana datasource provisioning | FAIL, resolved for retry | Grafana's API initially returned an empty datasource list because Compose mounted `datasources.yml` and `dashboards.yml` at `/etc/grafana/provisioning/` rather than the subdirectories Grafana scans. Corrected the two explicit mount targets and recreated only Grafana. Startup logged insertion of default datasource `Prometheus` (`PBFA97CFB590B2093`); Grafana's authenticated datasource proxy then returned the same M3 samples as direct Prometheus queries. Initial failure retained. |
| Monitoring baseline | PASS with known M2 gap | After M3 startup: Prometheus targets `prometheus` and `saiv-face-recognition` UP. `saiv-backend` remains DOWN because `/metrics` → 404, the known unsupported route. Baseline taken before biometric enrollment. |

## IT-01 progress

| Step | Test | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Register through M1 | PASS | M1 displayed `Account created. Sign in to continue.`; M2 preflight 200 and registration 201. `STUDENT_ID=b89179bd-1bf5-47cd-92b7-934a04c0213d`. SQL: one active student; bcrypt-format hash; both consents false; face not enrolled; no template; zero check-ins. |
| 2 | Log in through M1 | PASS | M1 showed the registered student dashboard and `No active sessions`. Login used the real account; no demo mode. Independent retry: login 200, refresh cookie has HttpOnly, SameSite=Lax, and path `/api/v1/auth`; `/users/me` → 200 with the same student ID. |
| 3 | Course enrollment | PASS | Admin API returned 201; `ENROLLMENT_ID=2af0dcff-85f8-4ae8-ad95-68a9fc3666d3`. Student read returned one enrollment; instructor roster reported `total_enrolled=1` with the student ID. SQL confirmed the active student/course relation. `COURSE_ID=be876c24-990c-41f3-a495-23bb81433ab3`, code `IT-20261003-0131`, instructor `4675d2cc-37c0-47ba-af34-f7d8cf58b8ce`. |
| 4 | Create lecture through M4; configure and activate | PASS after UI repair | First M4 login attempt froze before reaching M2 because of invalid nested document rendering; CORS and router-shell fixes were applied and retained above. Retry login succeeded. M4 called course/session lists, `POST /sessions/` → 201, refreshed the lists, and displayed session creation success. `SESSION_ID=a947d2b1-36fa-4b93-95c6-6f88974d9319`; scheduled name `Integration Test Room session`, lecture, correct venue and 100 m radius. Instructor policy PATCH → 200; admin activation PATCH → 200. API and SQL show active status, non-null actual start, all three verification requirements true, risk threshold 0.5, and `session_motion_policies.required=true`. Window: 02:03–02:48 UTC. |
| 5 | Discover active lecture in M1 | PASS | User reloaded M1 and confirmed the expected registered identity, active test session, Online state, CHECK-IN OPEN, and `Integration Test Room`. API `/sessions/active` → 200 with exactly one matching session and mandatory motion/liveness/face matching. |
| 6 | Camera consent and webcam | PASS | User accepted camera consent and the workflow advanced to the location step, demonstrating that M1 obtained a live camera stream. Frame capture and biometric processing remain covered by Steps 8–10. |
| 7 | Location consent and coordinates | PASS after two failed attempts | Attempt 1 in the ChatGPT in-app browser timed out without coordinates. The first synthetic attempt used the instructor because of the shared localhost refresh cookie and was rejected as student evidence. After explicit sign-out and student login, the user repeated camera/location consent and advanced to face verification with the configured venue point `1.3483, 103.6831` and 10 m accuracy. The top-bar account was confirmed as the student. Physical GPS remains untested. |
| 8 | Real M2 → M3 face enrollment | PASS after wrong-identity attempt | Attempt 1 successfully enrolled the instructor because M1 had restored M4's shared localhost refresh cookie; that failure and template are retained. After explicit logout/login, the student retry advanced from `Set up face verification` to `Blink twice`. M2 logged fresh student login 200, `GET /users/me` 200, consent `PUT /users/me` 200, and enrollment 200. M3's enrollment outcome/HTTP success counters increased again, from 1 to 2. SQL now finds `camera_consent=true`, `face_enrolled=true`, and a 64-character hexadecimal template on student `b89179bd-1bf5-47cd-92b7-934a04c0213d`; geolocation consent remains false and the session still has zero check-ins. A fresh independent login and `/users/me` read returned the same student ID/role and enrollment state. |
| 9 | Challenge and two blinks | PASS after browser-interruption failure | Attempt 1 issued `b3c3aa04-bcb0-4146-bccc-5ad929db09af` with POST 201 and reached `2 / 2`, but switching applications stopped the camera, cleared local frames, and left the challenge expired/issued with null result and zero check-ins. The user repeated the whole flow without leaving Safari. The accepted current challenge is `f16b8cd2-a82a-4292-a619-f85c9acd1c35`; the browser again reached two detected blinks and offered sequence verification. Logs also show an intervening successfully verified challenge `f4de35fe-c7cc-4390-bba9-d7fdb476ce9d` that was replaced when another challenge was started; the final submission used only the latest proof. |
| 10 | M3 sequence verification | PASS | M2 logged `POST /motion/challenges/f16b8cd2-a82a-4292-a619-f85c9acd1c35/verify` → 200 and M3's successful generic POST counter increased. Before submission, SQL showed `state=verified`, `passed=true`, `blink_count=2`, liveness `0.898102`, face match `0.9333332806583946`, and zero check-ins. The persisted result contains only the four allowed outcome fields. M3's generic successful POST counter reached 2 because the replaced `f4de35fe-...` retry also reached sequence verification. |
| 11 | Approved check-in | PASS with time-display defect | M1 displayed `Attendance confirmed`, time `2:30:25 AM`, and risk `0.10`. M2 logged consent `PUT /users/me` → 200 and `POST /checkins/` → 201. `CHECKIN_ID=f7d0abf5-46db-4ff7-af7f-6a6a5f93b390`. API/SQL status is approved with both biometric flags true, blink evidence, zero-metre synthetic-fixture distance, and risk `0.1019`, exactly `round(max(0, 1-0.898102, 1-0.9333332806583946), 4)`. The stored timestamp is 02:30:25 UTC; M1 displayed that naive UTC value directly instead of converting it to the browser's configured local time. |
| 12 | Independent PostgreSQL verification | PASS | A separate read found one active bcrypt-backed student with both consents true, enrollment/template present, the correct active course/session/policies, consumed challenge `f16b8cd2-...` with matching reference and saved scores, and exactly one attendance row. Coordinates are `1.3483,103.6831`, accuracy 10 m, distance 0 m; checked/verified times match, status approved, risk 0.1019, clean risk factors are SQL NULL, and expected `face_embedding_hash`/`device_id` fields on attendance are NULL. Fresh student and instructor API reads both returned exactly `f7d0abf5-...` with matching identity, session, timestamp, status, distance, and risk. |
| 13 | M4 student attendance | PASS with time-display defect | User signed in to M4 as the test student. Dashboard displayed My check-ins `1`, Attendance rate `100%`, Flagged `0`, and Missed sessions `0`. History showed course `IT-20261003-0131`, date `03 Oct 2026`, status `Approved`, and time `02:30 AM`. M2 logs show browser login/me 200 and repeated polling of `/checkins/my-checkins?limit=100` → 200. The row matches `CHECKIN_ID=f7d0abf5-...` through the independently verified API, but M4 repeats M1's timestamp defect by displaying the naive UTC value as though it were already browser-local. |
| 14 | M4 staff attendance | PASS with time-display defect | Instructor Overview showed 1 course, 1 active session, 1 student, 100% check-in rate, 0 flagged items, and average risk 10. Check-ins showed the correct student/course, Approved, risk 10, and 02:30 AM. The expanded session attendance list matched with no functional discrepancy except the same nine-hour time error. M2 logs confirm real browser login/me, session-list, and session-check-in reads returned 200 repeatedly. |
| 15 | Prometheus, Grafana, and collector evidence | PASS after Grafana provisioning repair | Direct Prometheus: M3 target UP (`up=1`); backend target remains DOWN because `/metrics` is 404. From zero baseline, enrollment outcome and `/face/enroll` HTTP counters reached 2 because both the wrong-instructor attempt and corrected student attempt succeeded; generic successful POST `route="other"` reached 2 for the two successful sequence verifications. Collector logs contain two 201 `/face/enroll` server spans plus `face_enroll` operation spans, and two 200 `/liveness/sequence` server spans with scalar face/match metadata and no payloads or credentials. Grafana initially had no datasource; after the mount fix, its Prometheus proxy returned the same `1,2,2,2` samples. The user then verified those four results successfully in Grafana Explore. |
| 16 | Persistence after backend restart | PASS | Restarted only M2. New `/health` and `/db-health` reads returned 200. A fresh PostgreSQL connection returned the identical `CHECKIN_ID=f7d0abf5-...`, relationships, approved status, timestamps, coordinates, biometric scores, risk 0.1019, consumed challenge, and count 1. Fresh student/instructor logins and API reads returned that same row. The user reloaded M4 in both instructor and student roles and confirmed the same staff attendance and student 1/100%/approved history remained. No second check-in was submitted. |

## Defects and gaps found

| ID | Severity | Status | Finding |
| --- | --- | --- | --- |
| IT01-D01 | High | OPEN | M1 and M4 share the backend's host-wide localhost refresh cookie. Reloading M1 after M4 instructor login restored the instructor in the student app; M1 did not enforce a student-role gate and allowed face enrollment. This stored the user's test face template and camera consent on the instructor fixture before explicit logout/student login. |
| IT01-D02 | Medium | OPEN | M2 serializes naive UTC timestamps without a timezone suffix. M1 and M4 interpret `2026-10-03T02:30:25.091998` as browser-local time and display 02:30 instead of converting it from UTC to the browser's configured local time. |
| IT01-D03 | Medium | OPEN | Prometheus marks `saiv-backend` DOWN because M2 `/metrics` returns 404. M3 monitoring is healthy and fully exercised. |
| IT01-D04 | High | FIXED IN WORKTREE | M4 login initially froze because the router root rendered a nested `<html>` document inside Vite's `#root`. Removing the incompatible document shell restored interaction; M4 build passed. |
| IT01-D05 | Medium | FIXED IN WORKTREE | M2 initially rejected M4's credentialed origin. Adding `http://localhost:8501` to the explicit CORS allowlist produced a correct 200 preflight and allowed real M4 authentication. |
| IT01-D06 | Medium | FIXED IN WORKTREE | Grafana initially loaded no datasource because Compose mounted provisioning files outside the required subdirectories. Explicit datasource/dashboard file mounts restored provisioning and Explore queries. |
| IT01-D07 | Low | OPEN | M1's image reports 16 npm audit findings during install (15 high, 1 critical), Compose's `version` field is obsolete, and M1 starts with `next start` despite standalone output. These did not block this run. |

## Cleanup

- Admin API closed session `a947d2b1-36fa-4b93-95c6-6f88974d9319` after evidence capture; a follow-up read returned `status=closed`.
- Dedicated database records and failed-attempt evidence were preserved as required by the plan.
- User confirmed sign-out from M1, M4, and Grafana.

## Automated checks and additional cases

| Check | Result | Evidence |
| --- | --- | --- |
| Test dependency setup | PASS after environment repairs | System Python 3.9 initially lacked pytest. Created ignored local virtual environments and installed `requirements-test.txt`; the first sandboxed install failed on blocked DNS and the approved network retry succeeded. The bundled Python 3.12 runtime was required for M2's `X | None` annotations. |
| Required public/cookie command, attempt 1 | BLOCKED | Sandboxed localhost access caused 26 service-dependent skips and four cookie-fixture connection errors (`Operation not permitted`) before requests reached M2. |
| Required public/cookie command, retry | PASS | With localhost permission: `30 passed in 14.40s`; public scoring summary 20/20 (100%, A). Covers `test_integration.py`, `test_frontend_dashboard.py`, `test_privacy_basic.py`, and `test_auth_cookie.py`. |
| Backend motion contracts, attempt 1 | BLOCKED | Host Python 3.9 failed collection on M2's PEP 604 union annotation. |
| Backend motion contracts, retry | PASS | Python 3.12: `new-tests/test_motion_backend.py` → 1 passed in 2.26s. |
| Motion sequence logic | PASS | Python 3.12: `new-tests/test_motion_sequence.py` → 15 passed in 2.88s. |
| M3 native edge cases, host attempt | BLOCKED | Combined host requirements omit `face-recognition`/dlib: 11 non-model tests passed, while five failed and six errored with privacy-safe 503 `Face processing is temporarily unavailable`. |
| M3 native edge cases, runtime retry | PASS | Copied tests/source/sample images to a temporary M3-container layout and ran with its native Python 3.11 model dependencies: 22 passed in 5.21s; two deprecation warnings. |
| Native static-photo rejection | PASS | M3 container: `new-tests/test_motion_native.py` → 1 passed in 1.65s; two deprecation warnings. |
| Frontend builds | PASS | M1 optimized Next.js build compiled, linted, and type-checked successfully with the opt-in location fixture. M4 Vite build passed after the router-shell repair (175 modules, 511 ms). |
| Final static/configuration checks | PASS | `git diff --check` returned no errors. `docker compose config -q` passed with only the known obsolete-version warning. |

Supplementary tests do not replace the live IT-01 case. IT-02–IT-26 remain NOT RUN.
