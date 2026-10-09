# P0-07 — Consent and browser permissions

Prepared: 09 October 2026. **Status: PLAN ONLY — NOT RUN.** Priority: P0.

## Quick reference — logs and database

Run shell commands from the repository root. If `docker compose up` is already running in one terminal, open another terminal for these commands.

```bash
# Check container status
docker compose ps

# Follow M2 and M3 activity together
docker compose logs -f --tail=50 --timestamps backend face-recognition

# Or follow each service in a separate terminal tab
docker compose logs -f --tail=50 --timestamps backend
docker compose logs -f --tail=50 --timestamps face-recognition

# Retrieve recent activity without continuously following it
docker compose logs --since=10m --timestamps backend face-recognition

# Inspect other services when troubleshooting
docker compose logs --tail=50 --timestamps frontend dashboard postgres

# Open the PostgreSQL client
docker compose exec postgres psql -U saiv -d saiv
```

Press **Ctrl+C** to stop following logs; the containers keep running. In M1, also open browser **DevTools → Network**, enable **Preserve log**, and use the Console for browser errors. Do not export tokens, photos, or frames in shared evidence.

Inside `psql`, use these commands to inspect tables:

```text
\dt
\d users
\d checkins
\d motion_challenges
\x auto
```

Replace the placeholder IDs and compare these reads before and after each negative attempt:

```sql
SELECT id, camera_consent, geolocation_consent, face_enrolled,
       (face_embedding_hash IS NOT NULL) AS has_template
FROM users WHERE id = '<STUDENT_ID>';

SELECT id, session_id, state, expires_at, (result IS NOT NULL) AS has_result
FROM motion_challenges WHERE user_id = '<STUDENT_ID>';

SELECT id, status, latitude, longitude, location_accuracy_meters,
       liveness_passed, face_match_passed
FROM checkins
WHERE student_id = '<STUDENT_ID>' AND session_id = '<SESSION_ID>';

SELECT COUNT(*) AS attendance_count
FROM checkins
WHERE student_id = '<STUDENT_ID>' AND session_id = '<SESSION_ID>';
```

Type `\q` to exit `psql`. For a database GUI, connect to host `localhost`, port `5434`, database `saiv`, user `saiv`, password `saiv_password` (local Compose configuration).

Continuous log watching is optional. Keep targeted Network/API and SQL evidence for this case, and inspect per-attempt M3 activity where the plan requires proving that a rejected request caused no biometric processing. A quiet log alone is insufficient unless the relevant route is logged and the attempt is isolated.

## Objective

Verify that refusing or withdrawing camera/location permission prevents the affected capture or submission, stored consent is enforced by the backend, and granting consent again allows a fresh attempt. Record the legacy photo API consent gap as a defect, even if the browser workflow correctly blocks capture.

Sources: [test-case list](test-cases-list.md), [P0-02 setup and happy path](P0-02-test-plan.md), [API specification](../../docs/API-SPECIFICATION.md), [database schema](../../docs/DATABASE-SCHEMA.md), and [motion contracts](../MOTION-VERIFICATION.md). This plan also follows the active M1 camera/location hooks, M2 enrollment/check-in/motion endpoints, M3 enrollment consent check, and M4 attendance reads.

## Preparation

**People:** a student tester and a test operator with an API client, browser developer tools, database read access, and an instructor account for M4. One person can perform both roles. Use separate browser profiles for M1 and M4 to avoid their shared localhost refresh cookie restoring the wrong identity.

1. Start the real M1–M4 stack using [P0-02 preparation](P0-02-test-plan.md#environment-people-and-preparation). Confirm M2 database connectivity, M3 native-model readiness, M1 login/session discovery, and M4 authenticated attendance reads. Use localhost or HTTPS. Do not use demo mode.
2. Record run ID, code revision, browser/version, operating system, application origins, test identities, session IDs, and initial attendance counts. Test browser site permission separately from any operating-system restriction; leave OS camera/location access enabled for the site-permission cases.
3. Use a fresh student with active enrollment and initially `camera_consent=false`, `geolocation_consent=false`, `face_enrolled=false`. Prepare active lectures whose check-in windows remain open throughout their steps. Recheck the window before each API negative test so a time or duplicate error cannot mask a consent error.
4. Prepare these fixtures using P0-02's staff/admin setup. Use a new eligible student/session pair whenever an earlier variant creates attendance unexpectedly; preserve that row as defect evidence.

| Fixture | Session policy | Purpose |
| --- | --- | --- |
| `S_MOTION` | `require_motion_check=true`, `require_liveness_check=true`, `require_face_match=true` | Browser permission checks and camera-consent enforcement |
| `S_GEO` | Same as `S_MOTION`; no existing attendance | Stored location-consent check using a fresh verified motion proof |
| `S_PHOTO_*` | `require_motion_check=false`, `require_liveness_check=true`, `require_face_match=true` | One isolated session per legacy photo variant |
| `S_RECOVERY` | Same as `S_MOTION`; no existing attendance | Final successful retry |

5. Configure venue coordinates/radius and a browser **DevTools geolocation override** at the venue with good accuracy, for example synthetic coordinates `1.3483,103.6831`, radius 100 m, accuracy 10 m. Label this synthetic evidence. **Leave `NEXT_PUBLIC_INTEGRATION_TEST_GEOLOCATION` unset in the M1 build used for this case:** that application fixture bypasses browser permission checks and would invalidate location-denial/revocation results. If it was used for P0-02, rebuild/redeploy M1 without it before starting. DevTools coordinates must still go through the browser permission gate; verify that denying the site permission actually denies the request.
6. Reset the M1 origin's camera and location permissions to **Ask** using the browser site-settings panel. Open Network logs. Track requests to `/users/me`, `/users/me/face/enroll`, `/motion/challenges`, challenge verification, and `/checkins/`. Keep photos/frames and bearer tokens only in the local test tool's temporary memory; do not export them in HAR files or shared evidence.

**Important distinction:** the M1 checkboxes, browser/OS permissions, and stored M2 consent flags are separate states. Revoking a browser permission does not automatically update the database. M1 has no dedicated stored-consent withdrawal screen; use student-authenticated `PUT /api/v1/users/me` to test withdrawal. Do not click M1 enrollment, **Start challenge**, or **Submit check-in** during a direct API withdrawal test: those actions can write consent back to true and conceal the rejection being tested.

## Steps and expected results

### Step 1 — Verify the starting identity and consent state

**Student:** Sign in to M1 with the fresh test student. Select `S_MOTION`. Leave both consent boxes unchecked.

**Operator:** Call `GET /api/v1/users/me` with this student's token and take the database baseline described below.

**Check:** The header and API identify the intended student; both stored consents are false, face enrollment is false, no template is present, and this student/session has zero attendance. The session is active, within its check-in window, and requires motion. Record existing challenge IDs/counts, if any. An instructor identity or closed session blocks the case until corrected.

### Step 2 — Refuse the application camera consent

**Student:** On **Camera access**, leave **I consent to camera verification** unchecked and try to activate the camera button. Then check and uncheck the box without requesting camera access.

**Check:** **Allow camera access** (or **Start camera** if already permitted) is disabled while unchecked. No browser permission prompt, live preview, enrollment request, motion request, or attendance write occurs. Stored flags remain false. Checking the box alone does not start capture or store consent.

### Step 3 — Deny browser camera permission, then retry while blocked

**Student:** Check the camera consent box, click **Allow camera access**, and select **Block/Don't Allow** in the browser prompt. Click **Retry camera** while site permission is still blocked.

**Check:** M1 stays at the camera step and displays **“Camera access is blocked. Allow it in your browser site settings, then retry.”** No usable live preview or advancement to location occurs; repeat retry remains blocked. No face enrollment, sequence verification, or check-in is submitted, and attendance stays zero. A missing prompt with a pre-existing denied permission is acceptable if the site setting confirms the denial; reset to Ask if necessary to exercise the prompt itself.

### Step 4 — Restore camera permission and refuse application location consent

**Student:** Open the origin's site settings, change camera permission to **Allow** (or Ask and allow the next prompt), return to M1, and click **Retry camera/Start camera**. If the browser requires reload, reload, confirm student/session, check camera consent again, and start the camera. At **Confirm your location**, leave **I consent to location verification** unchecked.

**Check:** A live camera preview appears and the workflow advances to location. **Share precise location/Use current location** is disabled while unchecked; there is no location prompt or advancement to face verification. No attendance is written. Browser camera permission alone must not cause stored camera consent to become true at this stage; record the API flags independently.

### Step 5 — Deny browser location permission and recover

**Student:** Check location consent, click **Share precise location**, and deny the browser prompt. Click **Retry location** while still blocked. Then set the site's location permission to Allow, return, and retry; if a reload is required, repeat the camera and location checkbox steps.

**Check after denial:** M1 displays **“Location access is blocked. Allow precise location in site settings, then retry.”** It stays at location, offers retry, and does not obtain coordinates, reach verification, or write attendance. A timeout is a different result and does not prove permission denial.

**Check after recovery:** The browser supplies the synthetic venue point and accuracy, and M1 reaches face verification. No check-in exists yet. Merely checking location consent/capturing location currently does not persist `geolocation_consent=true`; M1 normally writes it at final submission. Record this timing rather than treating the checkbox as database evidence.

### Step 6 — Revoke camera permission after evidence has been prepared

**Student:** Enroll if prompted: **Capture image → Confirm enrollment**. Complete **Start challenge → blink naturally twice → Verify this sequence**, reaching **Ready to check in**, but do not submit. Revoke camera permission in the browser's site-settings panel, then return to M1 and try **Submit check-in**.

**Check:** Enrollment calls M2/M3 successfully and the proof is server-verified before revocation. Once the browser reports revocation or ends the stream, preview/capture stops; local photo/proof evidence is cleared. Review should show **Camera stopped** and **Capture cleared — repeat verification**, with submission disabled. No new `/checkins/` request or attendance row may result from the cleared evidence. A previously verified server challenge may remain in SQL; clearing browser evidence does not automatically cancel it.

**Retry:** Restore camera permission. Use **Retake / repeat verification**, then **Restart camera** if shown, and complete a new challenge. Confirm a new verification ID is obtained before proceeding; do not submit yet.

**Browser caveat:** Opening another tab/window may itself stop M1's camera because it pauses capture when hidden. Record whether the trigger was a permission event, track termination, or tab hiding. To establish revocation specifically, also verify the blocked site setting and that restarting while blocked fails. If only tab hiding was exercised, mark live revocation unverified rather than claiming it passed. On browsers without permission-change events, record actual track behavior and repeat a fresh denied request after reload.

### Step 7 — Revoke location permission after coordinates have been captured

**Student:** With a fresh verified proof at **Ready to check in**, revoke the site's location permission. Return to M1 and attempt submission. If camera evidence was cleared by tab hiding, restart capture/verification while keeping location blocked before attempting submission. Do not restore location yet.

**Check:** Previously captured coordinates must not be submitted after location revocation; no attendance row is created. In browsers supporting location permission-change events, the current hook clears the stored point. A clear recovery message and a way to request location again are required for a usable retry.

**Current behavior to examine:** The review screen may retain **Location captured** and an enabled submission button even after the point is cleared. Submission then silently returns without a request. Record this as a recovery/UI defect, not a successful user-facing retry. If coordinates remain usable and a request creates attendance while permission is revoked, record a consent/cached-location defect. Backend rejection based on stored consent cannot prove browser revocation detection.

**Retry:** Restore site location permission, reload M1 if needed, reconfirm identity/session, and repeat camera/location capture and fresh motion verification. Stop before submission. Verify the location request is new and succeeds; do not rely on the old point.

### Step 8 — Withdraw stored camera consent and test enrollment directly

**Operator, using the student token:** Send `PUT /api/v1/users/me` with `{"camera_consent":false}`. Read `/users/me` again and confirm false in SQL. Record enrollment/template state without copying the template into the report. Send `POST /api/v1/users/me/face/enroll` with `{"image":"<VALID_TEST_PHOTO_BASE64>"}` directly from the API client.

**Check:** Consent update and read return 200 with camera consent false. Enrollment returns **400**, detail **“Camera consent is required before face enrollment”**. M2 must not call M3 enrollment; `face_enrolled` and template state remain unchanged, and attendance remains zero. An existing template need not be deleted by withdrawing consent; deletion/retention is covered separately by P2-03.

**Operator:** Also call M3 `POST /face/enroll` with `{"user_id":"<STUDENT_ID>","image":"<VALID_TEST_PHOTO_BASE64>","camera_consent":false}`.

**Check:** M3 independently returns **400**, detail **“Camera consent is required for face enrollment”**, with no successful enrollment result. This call tests M3's own contract; it does not replace the M2 gate check.

### Step 9 — Verify stored camera withdrawal blocks all motion stages

**Operator:** Keep camera consent false and attempt `POST /api/v1/motion/challenges` with `{"session_id":"<S_MOTION>"}`.

**Check:** **400**, **“Camera consent and face enrollment are required”**; no new challenge or attendance is created.

**Operator:** Restore camera consent with `PUT /users/me`, start a fresh challenge, and prepare a valid timestamped sequence without submitting it. Withdraw camera consent again, then submit that sequence to `POST /motion/challenges/<CHALLENGE_ID>/verify`. Use valid frame counts/timestamps/images so validation does not mask the consent check.

**Check:** **400**, **“Camera consent and face enrollment are required”**; no M3 sequence call, no usable verification ID, and the issued challenge is not promoted to verified/consumed.

**Operator:** Restore camera consent, obtain a fresh successful motion proof while the window is open, then withdraw camera consent again. Directly submit the valid check-in payload below, including that proof, to `POST /checkins/`.

**Check:** **400**, **“Camera consent is required”**; attendance remains zero and the proof remains unconsumed. Confirm the proof was verified/unexpired immediately before the attempt. A 409 expiry error or 422 payload error does not establish the consent gate.

### Step 10 — Withdraw stored location consent and test motion submission

**Operator:** On `S_GEO`, keep camera consent true and obtain a fresh successful proof. Send `PUT /users/me` with `{"geolocation_consent":false}`, verify it by API/SQL, and directly submit the valid payload below using the proof and synthetic venue point. Do not submit through M1, which would restore its checked consent flags first.

**Required result:** M2 rejects the request for missing stored location consent, creates no attendance row, and leaves the proof unconsumed. The rejection must identify consent rather than an unrelated fixture error; no exact consent error status/message is implemented for this path yet.

**Current implementation expectation:** M2 does not check stored location consent in check-in creation or motion consumption. It may return **201**, persist coordinates, and consume the proof despite `geolocation_consent=false`. Record any such write as a **FAIL / consent enforcement defect**, including actual attendance status and proof state. Even flagged/rejected attendance is a write and does not satisfy the no-write requirement.

### Step 11 — Expose the legacy photo API consent gap

**Operator:** Use an enrolled student, a valid temporary photo, correct venue point, and a fresh `S_PHOTO_*` for each variant. Set and read back these flags, then directly post the photo payload below without a motion verification ID:

| Variant | Stored camera consent | Stored location consent | Required result |
| --- | --- | --- | --- |
| A | false | true | Reject before biometric processing or attendance write |
| B | true | false | Reject before processing supplied location or attendance write |
| C | false | false | Reject; no biometric processing or attendance write |

**Check:** For every variant, compare M2 response, M3 call activity, consent flags, and SQL attendance count. Current legacy check-in code has neither stored consent gate and may call passive liveness/face matching and persist attendance with **201**. At the venue, the decision may be approved, flagged, or rejected depending on real biometrics; any processing/write while its required consent is false is a defect. Do not count a photo-path success as consent enforcement. Keep M3 healthy so this case isolates consent rather than P0-13 outage fallback.

### Step 12 — Grant consent again and complete a fresh successful check-in

**Student:** Use untouched `S_RECOVERY`. Set browser camera/location permissions to Allow, reload M1, confirm the student identity, check both consent boxes, and repeat capture/location verification. Enroll if necessary. Complete a new two-blink sequence, verify it, and click **Submit check-in** once.

**Check:** M1 shows **Attendance confirmed**. Network shows successful consent update, challenge issuance (201), verification (200 with `passed=true` and a non-null ID), and check-in (201 with `status=approved`). Both stored consent flags are true; exactly one attendance row belongs to this student/session, with expected synthetic coordinates and passing biometric flags. Only the submitted fresh proof is consumed. If biometrics genuinely fail, retry with a fresh proof within the window; do not weaken policy to obtain a pass.

**Staff:** Refresh M4's session attendance view using the actual instructor account. Verify the one recovery row matches the student/session/check-in ID and approved status. Negative attempts should contribute no attendance; any rows from Steps 10–11 must be identifiable as recorded defects, not mixed into successful recovery. M4 fallback biometric values are not evidence; verify saved scores through SQL and the creation response.

## Direct API payloads and persistence checks

All M2 paths above use base `http://localhost:8000/api/v1` (replace for deployment), `Authorization: Bearer <STUDENT_TOKEN>`, and JSON content type. Use the same authenticated student whose consent was updated.

Motion check-in:

```json
{
  "session_id": "<TARGET_SESSION_ID>",
  "latitude": 1.3483,
  "longitude": 103.6831,
  "location_accuracy_meters": 10,
  "device_fingerprint": "it09-test-device",
  "motion_verification_id": "<FRESH_VERIFICATION_ID>"
}
```

Photo check-in: use the same fields, **omit** `motion_verification_id`, and add `"liveness_challenge_response":"<VALID_TEST_PHOTO_BASE64>"`. The camera must already have captured this participant-approved test photo while consent was granted; the API tests reuse that temporary input to check the server gate. No new capture is needed while permission is denied.

For each negative attempt, compare before/after reads. Use `GET /users/me`, `GET /checkins/my-checkins`, and instructor `GET /checkins/session/<SESSION_ID>`, plus independent database reads. Example SQL (replace IDs):

```sql
SELECT id, camera_consent, geolocation_consent, face_enrolled,
       (face_embedding_hash IS NOT NULL) AS has_template
FROM users WHERE id = '<STUDENT_ID>';

SELECT id, session_id, state, expires_at, (result IS NOT NULL) AS has_result
FROM motion_challenges WHERE user_id = '<STUDENT_ID>';

SELECT id, session_id, status, latitude, longitude,
       location_accuracy_meters, liveness_passed, face_match_passed
FROM checkins
WHERE student_id = '<STUDENT_ID>' AND session_id = '<TARGET_SESSION_ID>';
```

Use per-attempt service activity to confirm M3 was not invoked after a rejected M2 consent gate; unrelated counters in a shared environment cannot establish this. Record sanitized route/status/timing evidence without request bodies.

## Result recording and completion

For each step/variant, record **PASS, FAIL, or BLOCKED**, student/session/challenge/check-in IDs, actual browser message, permission settings, stored consent before/after, HTTP status/detail, attendance count change, and defect reference. Keep browser recovery results separate from backend enforcement results.

**P0-07 passes only when** checkbox and browser denial gates work, revoked access cannot reuse cleared capture/location, all tested backend consent gates reject without processing/writes, and renewed consent completes one fresh recovery attendance. Expected current gaps in Steps 7, 10, and 11 must remain failures when reproduced; observing a known defect does not make the complete case pass. Unsupported live permission events or an active application geolocation bypass must be reported as coverage limitations/blocked portions.

After evidence capture, sign out of both apps, close test sessions using the admin API, stop camera capture, restore browser permissions to the tester's preferred state, and discard temporary photo/frame/token inputs. Preserve dedicated fixture records and defect rows for review; do not delete attendance to make counts appear clean.

Related automated coverage: `tests/public/test_privacy_basic.py` checks consent field tracking/update, and `new-tests/backend_motion_cases.py::test_consent_and_enrollment_are_required` checks motion issuance eligibility. These do not establish live browser revocation, verify/consume withdrawal, or photo/location consent enforcement. This document adds a manual test plan only; no application changes or tests were executed for it.
