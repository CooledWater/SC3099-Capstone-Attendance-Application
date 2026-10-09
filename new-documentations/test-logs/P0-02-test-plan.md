# P0-02 — Happy path: four-module integration test plan

Prepared: 03 October 2026. **Status: plan only; the application and tests have not been run for this document.**

## Purpose and source of requirements

Verify that a student can register, log in, enroll their face, complete live verification, and successfully check in to a lecture, and that the resulting attendance survives database reads and appears in Module 4. A successful test must demonstrate real module calls and persisted data, rather than only a success message.

The requested `new-documentations/list-of-features-02OCT.md` is currently located at [../list-of-features-02OCT.md](../list-of-features-02OCT.md). This plan uses that inventory, the active implementations in all four module directories, [database schema](../../docs/DATABASE-SCHEMA.md), [API specification](../../docs/API-SPECIFICATION.md), [integration guide](../../docs/INTEGRATION-GUIDE.md), and [motion verification contracts](../MOTION-VERIFICATION.md). Older examples in the integration guide describe Streamlit/direct database access; the current M4 app is React/Vite and reads attendance through M2.

### Connections under test

| Connection | What this test must prove | Feature-inventory pathways |
| --- | --- | --- |
| M1 → M2 | Registration, authentication, session discovery, consent, enrollment, motion verification, and final submission use the real API. | P1–P7, P9 |
| M2 → M3 | Enrollment images and timestamped blink frames are processed by the real face service; usable results return to M2. | P5, P7 |
| M2 ↔ PostgreSQL | Account, course, enrollment, session, policy, motion state, and attendance writes can be independently read back. | P1, P4–P7, P9–P12 |
| M4 → M2 | Staff create a session; students and staff retrieve the same attendance written through M1. | P10–P12 |
| M4 monitoring ↔ M3 | Prometheus scrapes M3 metrics, Grafana can query them, and M3 exports traces to the collector. | P15, P16 |

M1 and M4 share persisted attendance through M2; they do not call each other. M1's local MediaPipe capture guidance does not call M3. M3 receives templates from M2 and does not access the application database. Redis is provisioned but is not used by these application flows.

## Environment, people, and preparation

Use a dedicated test database with one test course/session and unique accounts. Run this case without other traffic when comparing counters or dashboard totals. Keep the database volume between persistence checks.

**People/tools:** one student tester with a real webcam, an operator with admin API access, and a staff tester with an instructor account. One person may perform all roles, but use separate browser profiles for student and staff. Keep M1 in the foreground during capture: hiding its tab stops the camera and clears evidence. An API client such as Postman or M2's Swagger UI at `http://localhost:8000/docs` is needed for setup actions without browser controls.

| Component | Default local address / configuration |
| --- | --- |
| M1 student app | `http://localhost:3000`; `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` |
| M2 backend | `http://localhost:8000`; Compose sets `FACE_SERVICE_URL=http://face-recognition:8001` |
| M3 face service | `http://localhost:8001`; real native models and MediaPipe dependencies must work |
| M4 dashboard | `http://localhost:8501`; `VITE_API_BASE_URL=http://localhost:8000/api/v1` |
| PostgreSQL | Host port `5434`; Compose service `postgres`, database/user `saiv` |
| Prometheus / Grafana | `http://localhost:9090` / `http://localhost:3001` |
| OTel collector | Compose endpoint `http://otel-collector:4317` for M3's OTLP gRPC exporter |

From the repository root, start and inspect the stack:

```bash
docker compose up --build -d
docker compose ps
curl -i http://localhost:8000/health
curl -i http://localhost:8000/db-health
curl -i http://localhost:8001/health
curl -i http://localhost:8001/metrics
docker compose logs --tail=100 backend face-recognition dashboard otel-collector
```

Expect M2 `/health` and M3 `/health` to return HTTP 200 with `status: "healthy"`; M2 `/db-health` must return HTTP 200 with `database: "connected"`. `/health` alone does not prove database access or native-model readiness. M3 `/metrics` must contain actual Prometheus series, not merely a dependency-unavailable comment. Open both browser apps and confirm their API requests target M2's `/api/v1` URL. Compose's dashboard `BACKEND_URL`, `DATABASE_URL`, and `PROMETHEUS_URL` do not configure its browser API client.

Before starting the student workflow, record the M3/Prometheus counter baselines listed in Step 15 and the run's start time. Enable M3 telemetry and verify the collector is running before enrollment. Keep browser Network logs available for the test, with sensitive payloads excluded from shared evidence.

### Known setup blocker and implementation limits

- **M4 browser CORS is blocked by default.** M2 currently permits only `http://localhost:3000`, while M4 uses `http://localhost:8501` and has no Vite API proxy. Before the browser test can pass, the test deployment needs an explicit credentialed CORS allowlist including the dashboard origin, or a correctly configured same-origin API proxy. The CORS origin list is hard-coded in M2; adding an arbitrary environment variable will not fix it. This plan does not change application configuration. Check dashboard login and authenticated reads in its Network panel; successful curl/Swagger calls do not establish browser connectivity. Record the default failure and any deployment adjustment. Do not disable browser security to obtain a pass.
- **Session setup needs API actions.** The M4 form creates a scheduled lecture; it does not activate it or set mandatory motion/face-match policy. There is no automatic activation scheduler. Explicit API configuration and activation are part of the case below.
- **Unavailable features are not acceptance evidence.** M2's audit endpoint returns an empty placeholder; M2 has neither `/metrics` nor `/api/v1/metrics/`. Thus the backend Prometheus target is expected to be down and the React Metrics tab cannot provide service metrics. Record these gaps separately; zero-valued UI cards are not successful telemetry. Grafana has a datasource but no supplied dashboard JSON.
- **Some dashboard data is incomplete.** Attendance read responses omit biometric scores/coordinates and the mapper substitutes zero/null; room appears as `—`. Verify the saved biometric and location-test values using SQL and the check-in creation response. Do not interpret dashboard fallback zeros as failed biometrics or invent missing read fields.
- **Schema terminology differs from M3.** The schema calls the stored face value a SHA-256 hash; current M3 produces a 64-character cancelable SimHash template. Check its format and consistent use across modules, and record that terminology difference rather than claiming this test proves SHA-256 storage.

If CORS, the database, models, or monitoring cannot be made ready, mark the affected portion **BLOCKED**, retain completed step results, and do not report the complete four-module case as passed.

### Test data and evidence

Choose a unique `RUN_ID`, for example `20261003-a1`, and record the code revision and effective service settings. Use fresh accounts such as `it.student.<RUN_ID>@example.com`, `it.instructor.<RUN_ID>@example.com`, and `it.admin.<RUN_ID>@example.com`, with passwords of at least eight characters and distinguishable full names.

The operator creates the admin/instructor accounts using `POST /api/v1/auth/register` with the corresponding `role`, logs each in through `POST /api/v1/auth/login`, and retains their bearer tokens in the API client. Expect 201 for registration and 200 for login. The student account must be created through M1 during the test. Never substitute an admin's “View as Student” layout for an actual student account.

The operator creates one course using the admin token:

```http
POST /api/v1/courses/
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json
```

```json
{
  "code": "IT-20261003-A1",
  "name": "Integration Test Course",
  "semester": "AY2026-27 Sem 1",
  "instructor_id": "<INSTRUCTOR_ID>",
  "venue_name": "Integration Test Room",
  "venue_latitude": 1.3483,
  "venue_longitude": 103.6831,
  "geofence_radius_meters": 100,
  "require_device_binding": false,
  "risk_threshold": 0.5
}
```

Replace the course code with the run's unique code. Use non-personal synthetic fixture coordinates for the course and session; they must not represent or imply a participant's physical location. Configure a browser geolocation override with those same coordinates and 10-metre accuracy, and record the result only as synthetic location evidence. Physical GPS requires a separate, explicitly authorized run and is outside this local integration case. Do not increase the risk threshold or disable real biometric checks to make the case pass.

Expect HTTP 201 and record `COURSE_ID`. Verify the course through `GET /api/v1/courses/{COURSE_ID}` with staff credentials and a database read. Defaults on a course do not automatically enable session biometric policy.

Maintain an evidence sheet containing `RUN_ID`, student/instructor/course/session IDs, enrollment ID, challenge/verification ID, check-in ID, step results, request timings, and any defect. Capture browser screenshots and sanitized response summaries. Keep passwords, tokens/cookies, raw photos/frames, embeddings, and landmarks out of shared evidence and exported HAR files. Observe biometric payload structure locally without saving their contents.

## P0-02 — Register, log in, and successfully check in to a lecture

**Priority:** first happy-path case. **Expected outcome:** exactly one `approved` attendance record with passing liveness and face matching, committed to PostgreSQL and visible in both M4 student and staff views. Use mandatory motion so a geofence-only fallback cannot masquerade as successful M3 integration.

### Step 1 — Register through the student app

**Student action:** Open M1, select **Register**, enter the new student's full name, email, and password, then click **Create account**. Do not choose **Continue in demo mode**.

**Visible success:** The app returns to sign-in and displays **“Account created. Sign in to continue.”** It should not log the student in automatically.

**Verify:** Network shows `POST /api/v1/auth/register` → 201 with a UUID, the entered identity, `role: "student"`, and `is_active: true`. Record `STUDENT_ID`. An independent database query finds exactly one matching `users` row, with a bcrypt hash rather than plaintext, both consent flags false, `face_enrolled=false`, and no face template. No check-in exists yet.

### Step 2 — Log in through M1

**Student action:** Enter the registered email/password and click **Sign in securely**.

**Visible success:** The student dashboard shows the registered full name/email and the check-in workflow. A missing-session message is acceptable until the operator creates/activates the lecture below.

**Verify:** `POST /api/v1/auth/login` → 200 with bearer tokens and the same student identity. The browser receives the `saiv_refresh_token` HttpOnly cookie scoped to `/api/v1/auth`; subsequent protected requests carry an access bearer token. M1 keeps its access token in memory. Verify `GET /api/v1/users/me` → 200 with the same `STUDENT_ID` using the student token. A fresh unauthenticated page may initially receive 401 from the startup refresh attempt; that is not a failed login. Do not require `last_login_at` to change: current login code does not update it.

### Step 3 — Enroll the student in the course

**Operator action:** In the API client, use the admin token for `POST /api/v1/admin/enrollments/` with `{"student_id":"<STUDENT_ID>","course_id":"<COURSE_ID>"}`. The student need not perform this administrative setup.

**Verify:** HTTP 201; record `ENROLLMENT_ID`. The `enrollments` row joins the correct student/course with `is_active=true`. Student-authenticated `GET /api/v1/enrollments/my-enrollments` returns that course, and staff `GET /api/v1/enrollments/course/{COURSE_ID}` reports one active student in the isolated course. Registration alone must not count as course enrollment.

### Step 4 — Create the lecture through M4, configure policy, and activate it

**Staff action:** In a separate browser profile, sign in to M4 with the test instructor account using **Sign in to console**. Open **Sessions → New session**. Select the test course, enter **Integration Test Room**, choose a start approximately ten minutes in the future, and enter the same synthetic fixture coordinates and 100-metre radius. Submit the form.

**Visible success:** M4 displays **“Session created.”** and lists the new scheduled/inactive lecture. The current form names it **“Integration Test Room session”**. Its expected-attendance input is unused; the roster-derived expectation must be one.

**Verify:** M4 calls `GET /api/v1/courses/?limit=100`, `POST /api/v1/sessions/` → 201, and refreshes `GET /api/v1/sessions/?limit=100`. Record `SESSION_ID`. SQL finds one session with the correct course/instructor, `session_type="lecture"`, and `status="scheduled"`. It should not yet appear in `/sessions/active`.

**Operator action:** With the instructor token, send:

```http
PATCH /api/v1/sessions/<SESSION_ID>
Authorization: Bearer <INSTRUCTOR_TOKEN>
Content-Type: application/json
```

```json
{
  "require_motion_check": true,
  "require_liveness_check": true,
  "require_face_match": true,
  "risk_threshold": 0.5
}
```

Then use the admin token for `PATCH /api/v1/admin/sessions/{SESSION_ID}/status` with `{"status":"active"}`. Expect HTTP 200 for both actions. Read `GET /api/v1/sessions/{SESSION_ID}` and confirm all three verification flags are true, the venue/radius are correct, and the current UTC time is inside the check-in window. The form defaults that window to start minus 15 minutes through start plus 30 minutes; its scheduled start must still be in the future when created. If more preparation time is needed, extend `checkin_closes_at` explicitly using the session PATCH API before capture.

SQL must show `sessions.status="active"`, a non-null `actual_start`, and `session_motion_policies.required=true` for this session. Recompute all dates on each run; use ISO 8601 with `Z` for API setup. Database timestamps are stored as naive UTC.

### Step 5 — Discover and select the active lecture in M1

**Student action:** Reload M1 after activation; its active-session list is fetched on dashboard mount, not continuously polled. Select the test lecture under **Active session**.

**Visible success:** The real course code, lecture name, venue, start time, and closing time appear. The app shows **Online** and **CHECK-IN OPEN**, with no demo identity or sample lecture.

**Verify:** Reload restores login using `POST /api/v1/auth/refresh` → 200 and `GET /api/v1/users/me` → 200. `GET /api/v1/sessions/active` → 200 includes `SESSION_ID`, course code, effective venue, and `require_motion_check=true`. Compare these with SQL. This list is currently public and not filtered by student enrollment; eligibility is established by Step 3 and subsequent protected calls, not by list visibility alone.

### Step 6 — Grant camera consent and start the webcam

**Student action:** Check **I consent to camera verification**, click **Allow camera access** or **Start camera**, and allow camera permission when the browser prompts. Use localhost or HTTPS and keep only the student in view, with a clear, well-lit face.

**Visible success:** A live preview shows **Camera active** and the flow advances to **Confirm your location**. Capture controls must be unusable before UI consent.

**Verify:** This first step invokes the browser camera API; ticking its box alone does not yet save consent in PostgreSQL. Local MediaPipe assets load from M1's `/mediapipe` paths when guidance initializes. Browser permission and persisted application consent are separate checks.

### Step 7 — Grant location consent and obtain coordinates

**Student action:** Check **I consent to location verification**, click **Share precise location** or **Use current location**, and use the declared synthetic browser location override. Do not describe the fixture as the participant's current or physical location.

**Visible success:** The app advances to face verification. Later, the review screen should show **Location captured (±… m)** with the reported accuracy. There should be no denial, timeout, or low-accuracy warning for this fixture.

**Verify:** The browser obtains the declared synthetic high-accuracy fixture. Record latitude, longitude, and accuracy as test inputs for comparison with the final API payload and SQL. The geolocation checkbox is held locally until submission; the enrollment action below preserves the existing database geolocation preference, so it may still be false until Step 11.

### Step 8 — Enroll the student's face through M2 and M3

**Student action:** As a new user, expect **Set up face verification**. Centre the face, click **Capture image**, inspect the preview, and click **Confirm enrollment**. Use **Retake** first if the photo is blurred or poorly framed.

**Visible success:** The enrollment succeeds and the app changes to **Blink twice**, with no enrollment error.

**Verify the calls and writes:**

1. M1 reads `/api/v1/users/me`, then sends `PUT /api/v1/users/me` → 200 with camera consent true and the existing stored location preference.
2. M1 sends `POST /api/v1/users/me/face/enroll` with a base64 image → 200 with `success=true`, `face_enrolled=true`, and `quality_score` meeting M3's configured threshold (default 0.50).
3. M2 sends `POST /face/enroll` to the actual M3 service with the authenticated student's ID, the image, and `camera_consent=true`. M3 returns 201 with `enrollment_successful=true` and a template matching `^[0-9a-f]{64}$`.
4. SQL finds the same user with `camera_consent=true`, `face_enrolled=true`, and that template in `face_embedding_hash`. A fresh `/users/me` read confirms enrollment. No attendance has been inserted.

M2's external 200 and M3's internal 201 are intentionally different. Use M3 metrics/traces in Step 15 to corroborate the internal call; browser Network cannot display M2's outbound HTTP requests. Do not claim a browser-local face detection result proves server enrollment.

### Step 9 — Request a server challenge and capture two blinks

**Student action:** Wait until guidance says **“Face centred. Keep looking at the camera.”**, then click **Start challenge**. Look straight ahead with eyes open, blink naturally twice, and reopen fully after each blink. Complete capture within eight seconds and keep the app foregrounded.

**Visible success:** The counter reaches **2 / 2 blinks detected**, a first-frame preview appears, and **Verify this sequence** becomes available. Because this lecture requires motion, the photo alternative cannot be selected.

**Verify:** M1 sends `POST /api/v1/motion/challenges` with `SESSION_ID` → 201. Record `CHALLENGE_ID`, `expires_at`, `action="blink_twice"`, `max_duration_ms=8000`, and `max_frames=120`. Challenge issuance itself does not call M3. SQL shows a challenge tied to `STUDENT_ID` and `SESSION_ID`, with the user's enrollment template as `reference_hash`, `state="issued"`, and `result=NULL`. Expiry is at most three minutes from issuance and no later than session closing.

### Step 10 — Have M3 verify the captured sequence

**Student action:** Immediately click **Verify this sequence**, wait for verification, and proceed to submission without switching tabs or letting the challenge expire.

**Visible success:** The flow changes to **Ready to check in** and shows **“Motion verified by server”**. A local blink count alone is insufficient.

**Verify:** M1 sends `POST /api/v1/motion/challenges/{CHALLENGE_ID}/verify` with `frames:[{image,timestamp_ms},…]` → 200. Capture contains 15–120 frames over 1–8 seconds, ordered strictly with gaps at most 250 ms, first timestamp at most 250 ms, at most 100,000 base64 characters per frame and 6,000,000 total. M2 forwards those frames and the stored template to M3 `POST /liveness/sequence` → 200.

The response must contain `passed=true`, `blink_count>=2`, scores in `[0,1]`, and a non-null `verification_id` equal to `CHALLENGE_ID`. With default settings, liveness meets 0.60 and face matching meets 0.70; use effective configured thresholds if different. SQL now shows `state="verified"` and JSON `result` containing only `passed`, `blink_count`, `liveness_score`, and `face_match_score`. No check-in exists yet. A verification timeout or failure requires a new challenge; it is not a passing result.

The browser timeout is 55 seconds, M2's M3 timeout is 45 seconds, and M3 checks a 40-second analysis budget between frames. Record the measured time separately from final submission latency.

### Step 11 — Submit and receive approved attendance

**Student action:** Verify the correct lecture and location readiness, then click **Submit check-in** once before proof/session expiry. Wait for the result.

**Visible success:** The app displays **“Attendance confirmed”** and **“You are checked in. You may now close this page.”**, with the recorded time and risk score. The camera preview and capture stop. **Submitted for review**, **Verification pending**, or **Check-in rejected** fail this happy-path expectation.

**Verify:** M1 first persists both consent flags with `PUT /api/v1/users/me` → 200, then sends:

```json
{
  "session_id": "<SESSION_ID>",
  "latitude": 1.3483,
  "longitude": 103.6831,
  "location_accuracy_meters": 10,
  "device_fingerprint": "<BROWSER_GENERATED_FINGERPRINT>",
  "motion_verification_id": "<CHALLENGE_ID>"
}
```

The coordinates/accuracy must be the synthetic fixture values captured in Step 7, not necessarily the example values. Expect `POST /api/v1/checkins/` → 201 with a new `CHECKIN_ID`, matching student/session IDs, `status="approved"`, `liveness_passed=true`, `face_match_passed=true`, `liveness_challenge_type="blink"`, the saved scores, and `risk_score<0.5`. The calculated fixture distance must be non-null and inside the configured radius.

On this motion path, final submission uses saved verification evidence and makes **no additional M3 liveness/face/risk calls**. Expected risk is the rounded maximum of `min(distance / radius, 2) / 2`, `1 - liveness_score`, and `1 - face_match_score` (four decimal places; account for the distance response's two-decimal rounding). There is no hard rejection for this fixture. The M1 result formats risk to two decimals; M4 attendance rows scale it to `round(risk_score * 100)`.

### Step 12 — Independently verify the committed database state

**Operator action:** Open a separate read session, rather than trusting the POST response. For Compose:

```bash
docker compose exec postgres psql -U saiv -d saiv
```

Use these read-only checks, replacing the example identifiers with values from the evidence sheet:

```sql
\set student_email 'it.student.20261003-a1@example.com'
\set session_id '<SESSION_ID>'
\set challenge_id '<CHALLENGE_ID>'
\set checkin_id '<CHECKIN_ID>'

SELECT id, email, full_name, role, is_active,
       camera_consent, geolocation_consent, face_enrolled,
       hashed_password LIKE '$2%' AS bcrypt_format,
       face_embedding_hash ~ '^[0-9a-f]{64}$' AS template_format
FROM users WHERE email = :'student_email';

SELECT e.id, e.student_id, e.course_id, e.is_active,
       c.code, s.id AS session_id, s.instructor_id, s.session_type,
       s.status, s.actual_start, s.checkin_opens_at, s.checkin_closes_at,
       s.require_liveness_check, s.require_face_match, p.required
FROM enrollments e
JOIN users u ON u.id = e.student_id
JOIN courses c ON c.id = e.course_id
JOIN sessions s ON s.course_id = c.id
LEFT JOIN session_motion_policies p ON p.session_id = s.id
WHERE u.email = :'student_email' AND s.id = :'session_id';

SELECT m.id, m.user_id, m.session_id, m.state, m.expires_at,
       m.reference_hash = u.face_embedding_hash AS reference_matches,
       m.result::jsonb
FROM motion_challenges m JOIN users u ON u.id = m.user_id
WHERE m.id = :'challenge_id';

SELECT k.id, k.student_id, k.session_id, k.status,
       k.checked_in_at, k.verified_at,
       k.latitude, k.longitude, k.location_accuracy_meters,
       k.distance_from_venue_meters, k.liveness_passed, k.liveness_score,
       k.liveness_challenge_type, k.face_match_passed, k.face_match_score,
       k.risk_score, k.risk_factors, k.face_embedding_hash, k.device_id
FROM checkins k WHERE k.id = :'checkin_id';

SELECT count(*) AS attendance_count
FROM checkins k JOIN users u ON u.id = k.student_id
WHERE u.email = :'student_email' AND k.session_id = :'session_id';
```

**Success criteria:** Exactly one account/enrollment/attendance row for this fixture; both consent flags and enrollment true; correct relationships; challenge `state="consumed"` with `reference_matches=true`; attendance `status="approved"`; non-null approval/check-in times inside the attendance window; GPS values/accuracy equal to the request; passing biometric flags and scores equal to the saved motion result; risk equal to the API response. Expected clean risk factors are SQL NULL or an empty array, represented as `[]` by the API. Consumption and attendance are committed together.

For this path, `checkins.face_embedding_hash` and `device_id` are expected to be NULL: the enrollment template stays on `users`/the challenge, and the submitted fingerprint is not linked to a device row. Those NULLs must not be confused with absent biometric verification. No raw image, base64 frame, embedding vector, or landmark array may appear in persisted records or service logs.

### Step 13 — Read the attendance in the real M4 student view

**Student action:** After the M1 result, open M4 in the student's browser profile, sign in with the same registered credentials, and view **Your check-in history**. If already open, wait for its next 30-second poll or reload.

**Visible success for this fresh account:** **My check-ins = 1**, **Attendance rate = 100%**, **Flagged = 0**, and **Missed sessions = 0**. **Check-in history** contains the test course with **Approved**, and recent activity reflects the check-in. The room placeholder `—` is a current mapping limitation.

**Verify:** M4 uses its own login/access token, reads `/users/me`, then calls `GET /api/v1/checkins/my-checkins?limit=100` → 200. The returned array contains exactly the created `CHECKIN_ID`, `SESSION_ID`, session name, course code, `approved` status, timestamp, and risk from SQL. Match IDs in Network because the rendered history does not display all IDs. The same account works across M1/M4, but automatic shared sign-in is not implemented. Check displayed times against UTC database values and the browser timezone; current serializers can omit a timezone suffix, so report any offset error.

### Step 14 — Read the same attendance in the M4 staff view

**Staff action:** In the instructor profile, refresh M4, open **Check-ins**, and select the test lecture. Also inspect **Sessions** and its expandable attendance list.

**Visible success:** One approved attendance row displays the correct student name/email and course, with risk `round(API risk * 100)`. The session shows one expected/enrolled student and one submitted check-in. In an otherwise empty instructor dataset, the overview shows one course, one active session, 100% check-in rate, and zero flagged items.

**Verify:** M4 calls `GET /api/v1/sessions/?limit=100` → 200 and `GET /api/v1/checkins/session/{SESSION_ID}` → 200. The latter returns the same `CHECKIN_ID`, student identity, approved status, check-in time, distance, risk, and `liveness_passed=true`. Compare API response values with SQL and the student read. M4 must not insert a second attendance record during these reads. Permit up to one 30-second polling interval plus request time, or force a reload to verify promptly; its header clock alone does not prove a data refresh.

### Step 15 — Verify actual M3 monitoring traffic reaches M4 infrastructure

**Operator action:** Compare M3 `/metrics` snapshots before Step 8 and after Step 11 without restarting M3. In Prometheus, check the **saiv-face-recognition** target is UP and wait for at least one 15-second scrape after each operation. Query:

```promql
up{job="saiv-face-recognition"}
face_operation_outcomes_total{operation="enroll",outcome="success"}
http_requests_total{service="face-recognition",method="POST",route="/face/enroll",status_class="2xx"}
http_requests_total{service="face-recognition",method="POST",route="other",status_class="2xx"}
```

**Success criteria:** `up=1`; in an isolated run, successful enrollment and its HTTP counter increase by one, and the successful generic `route="other"` counter increases for sequence verification. An absent pre-run label series can be treated as a zero baseline. `/liveness/sequence` currently maps to `other` and has no dedicated blink outcome counter. A counter alone does not identify a student; correlate its delta with the test timestamps and verified database result.

In Grafana, open **Explore**, select the provisioned **Prometheus** datasource, and execute the same queries; see the same sampled values. In `docker compose logs --since=10m otel-collector`, verify M3 HTTP spans for enrollment/sequence and the `face_enroll` operation span arrive after exporter/batch delay (allow approximately 30 seconds after completion). Expect scalar metadata and no biometric payloads or credentials. M3 telemetry must be enabled and the collector running. Do not require an M2 trace or one trace spanning all modules: M2 currently has no tracing setup or outbound trace propagation.

Take the pre-run baseline during preparation; this step checks it retrospectively. Missing scrape/export traffic is an observability failure even if attendance succeeds. The separate missing M2 metrics routes and unimplemented audit trail remain recorded gaps, not implied successes.

### Step 16 — Confirm the result survives a new connection and backend restart

**Operator action:** After recording evidence, restart only M2 with `docker compose restart backend`; wait for `/health` and `/db-health` to return 200. Preserve PostgreSQL and its volume.

**Student/staff action:** Reload M4 in both profiles (re-log in if necessary), then repeat the personal/session attendance reads and SQL count query from a new connection.

**Success criteria:** The identical `CHECKIN_ID`, student/session relationships, scores, status, and timestamps remain; the challenge remains consumed and the count is still one. This demonstrates persisted read-back beyond a browser cache or one backend process. No second check-in submission is needed.

## Acceptance, recording, and repeatability

P0-02 passes only when registration/login, real M3 enrollment/sequence verification, approved attendance, independent PostgreSQL read-back, both M4 attendance views, monitoring delivery, and persistence checks meet the expectations above. HTTP 201 by itself is not acceptance: flagged/rejected attendance and null biometric outcomes fail this case. Track functional and observability results separately, and report every required blocked/failed portion in the overall result.

For each step record **PASS / FAIL / BLOCKED**, actual versus expected results, sanitized request status/timing, relevant IDs, and a defect reference. For a failure, identify the first failing boundary (browser → M2, M2 → M3, M2 → database, M4 → M2, or telemetry export/scrape). Continue independent checks where possible without changing policy to conceal the failure. Record any successful retry as a new attempt and retain the initial failure.

After evidence is collected, close the lecture using the authorized session status API and sign out of both apps. Repeat with a new run ID, student, course, and session so enrollment/check-in uniqueness does not invalidate the next run. Preserve records for investigation in the dedicated test database; do not use a destructive database reset as part of this test.

### Existing automated checks to run alongside manual integration

Run HTTP tests against the isolated running services, using a Python environment with [test dependencies](../../requirements-test.txt):

```bash
TEST_BACKEND_URL=http://localhost:8000 TEST_FACE_URL=http://localhost:8001 \
python3 -m pytest tests/public/test_integration.py \
  tests/public/test_frontend_dashboard.py tests/public/test_privacy_basic.py \
  new-tests/test_auth_cookie.py -v
```

Relevant supplementary files are [backend motion contracts](../../new-tests/test_motion_backend.py), [sequence logic](../../new-tests/test_motion_sequence.py), [native face processing](../../new-tests/test_face_module3.py), and [native static-photo rejection](../../new-tests/test_motion_native.py). Run backend and M3 tests in their appropriate environments separately because both Python packages are named `app`; backend motion cases use a subprocess and mocked M3 transport. They do not prove real browser/native-service/PostgreSQL integration. The native rejection smoke test does not prove a live user can pass two-blink verification.

The existing public happy-path test disables liveness, sends no biometric evidence, and accepts several attendance statuses; it cannot replace P0-02. The public frontend/dashboard tests validate API shapes without browser execution, so they cannot detect CORS or UI flow failures. Record test skips and known unsupported specification routes explicitly. Broader API/security/observability tests can supplement the additional cases below, but no existing test result is asserted by this plan.  