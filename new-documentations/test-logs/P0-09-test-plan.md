# P0-09 — Failed liveness or identity: step-by-step test plan

Prepared: 09 October 2026. Status: **plan only; not executed**.

This plan covers the failed-liveness/identity case in [the case list](test-cases-list.md).

**Priority:** P0. **Objective:** insufficient blinks, incomplete reopening, another person's face, multiple faces, and abrupt movement must never produce usable motion proof or attendance for a motion-required session. Each scenario must also permit a fresh, valid retry.

## People, environment, and prerequisites

- Student A: the account owner whose face is enrolled.
- Participant B: a different person who agrees to take part in identity and multiple-face checks. B must not replace A's enrollment.
- Operator: uses Swagger/Postman and read-only SQL to inspect server outcomes. Staff uses an actual instructor/admin account in M4, in a separate browser profile.
- Run the real M1, M2, M3, and PostgreSQL services in an isolated test environment. Default browser addresses are M1 `http://localhost:3000`, M2 Swagger `http://localhost:8000/docs`, and M4 `http://localhost:8501`. Use localhost or HTTPS for camera access. No demo mode or mocked biometric responses.
- Use a functioning webcam, good lighting, and a foreground browser tab. Grant camera and location permissions. Keep the same declared location fixture inside the venue radius throughout so location failure cannot explain rejection.
- Use [P0-02 setup steps 1–8](P0-02-test-plan.md) to create/authenticate A, enroll A in the course, create and activate the session, configure permissions, and enroll A's face. Use a fresh session with no existing check-in for A. Do not complete P0-02 attendance on this session.
- Confirm with `GET /api/v1/sessions/{SESSION_ID}` that the session is active, the current time is inside its check-in window, and `require_motion_check`, `require_liveness_check`, and `require_face_match` are all true. SQL must show `session_motion_policies.required=true`. Extend the window through the authorized session PATCH API if necessary before testing.
- Confirm A's `GET /api/v1/users/me` reports camera consent and face enrollment. Keep the enrollment unchanged throughout. Verify M3's native face/landmark models work using the control below; service health alone is insufficient.
- Confirm M4 can log in and read this session through M2. A CORS failure blocks the M4 checks and must be recorded separately.

Record the run ID, revision, settings, A's student ID, session ID, challenge IDs, and per-step results. Record response status and scalar outcomes only in shared evidence. Keep tokens, raw frames, enrollment templates, and full HAR payloads out of the test log.

## Step 1 — Establish the empty baseline

**Student action:** Sign in to M1 as A, select the test session, allow the camera and location, and reach **Blink twice**. Keep only A visible.

**Operator checks:** Verify `GET /api/v1/checkins/my-checkins` as A and `GET /api/v1/checkins/session/{SESSION_ID}` as staff contain no row for A and this session. Run the SQL checks below. Record the count as zero. In M4, select/filter to the test session and confirm A has no recorded attendance.

**Success:** The correct account/session is selected; motion is mandatory; the photo alternative is unavailable; no attendance exists.

## Step 2 — Prove a valid capture works without checking in

1. **A:** Wait for **“Face centred. Keep looking at the camera.”** Click **Start challenge**. Begin with eyes open, blink naturally twice, and reopen fully after each blink while keeping the head steady.
2. **A:** When the preview and **2 / 2 blinks detected** appear, click **Verify this sequence**.
3. **Operator:** Confirm challenge creation returns 201 and verification returns 200 with `passed=true`, `blink_count >= 2`, and a non-null `verification_id` equal to the challenge ID. SQL must show `state='verified'`.
4. **A:** On **Ready to check in**, do **not** click **Submit check-in**. Click **Retake / repeat verification** instead.
5. **Operator:** Confirm attendance count remains zero. The next challenge creation must replace the previous challenge for this user/session. Confirm the control ID is no longer present after that creation.

**Success:** Real server verification can pass in this environment, and proof issuance alone does not create attendance. If the control fails, investigate first; mark biometric scenarios BLOCKED rather than interpreting every failure as correct rejection.

## Step 3 — Test insufficient blinks

Repeat the following as separate attempts, creating a fresh challenge each time:

| Attempt | What A does after clicking Start challenge | What to check |
| --- | --- | --- |
| 3A: zero blinks | Start with eyes open and hold them open throughout capture. | Counter does not reach two; capture eventually stops with a retry error. |
| 3B: one blink | Start open, make one natural blink, reopen, then keep eyes open until capture stops. | Counter never reaches two; capture eventually stops with a retry error. |

**For each attempt:** Check that no ready sequence or review screen is offered, no verification request is sent, and no check-in POST occurs. The browser currently reports **“Two complete blinks were not captured. Please retry.”** when it reaches its duration/frame limit. Timing may hit the 120-frame limit before eight seconds; do not require exactly eight seconds.

**Server check:** Repeat both patterns with the direct server procedure in Step 8. Expect a valid verification response with `passed=false`, `verification_id=null`, and `blink_count < 2`.

**Success:** Both browser attempts block progression and both server attempts reject incomplete blink evidence. A browser-only result does not complete the server check.

## Step 4 — Test incomplete reopening

1. **A:** Start a fresh challenge with eyes open.
2. **A:** Complete one natural blink and reopen fully.
3. **A:** Close both eyes for the second blink and keep them closed until capture ends. Do not reopen during this attempt.
4. **Operator:** Confirm the browser does not count the unfinished closure as a completed second blink, does not expose a usable sequence, and displays a retry error. There must be no review screen or check-in request.
5. **Operator/A:** Repeat through Step 8, keeping eyes closed through the final captured frame. Confirm `passed=false`, `verification_id=null`, and `blink_count < 2`.
6. **Operator/A:** Add a server-only variant: complete two valid blinks, then close the eyes again and finish the sequence closed. It must still return `passed=false` and no verification ID, even if `blink_count >= 2`.

**Success:** A closure must include reopening to count as a blink, and the server must require an open final state. Do not demand a zero liveness score: identity/passive scores may still be positive on a failed sequence.

## Step 5 — Test a different person's face

1. **A:** Keep A's authenticated account, enrollment, and selected session unchanged. Move out of view.
2. **B:** Sit alone in front of the camera. Wait for centred guidance, click **Start challenge**, and perform two complete natural blinks while remaining steady.
3. **B:** If the browser presents the captured sequence, click **Verify this sequence**.
4. **Operator:** Confirm the submitted frames are assessed against A's enrollment. The real verification response must be 200 with `passed=false` and `verification_id=null`; SQL must show `state='failed'`.
5. **A/operator:** Confirm M1 reports **“The server could not verify your face and two blinks. Please retry.”**, remains in verification, and never shows **Motion verified by server** or approved attendance.

**Success:** Browser-local blink completion does not allow B to authenticate as A. Any passing proof is a FAIL. If browser capture cannot complete, record its block and use Step 8 with B alone to finish the identity check. The server may stop at an early identity sample, so a server blink count below two does not invalidate this attempt. If passive liveness or detection fails first, record that rejection but repeat with suitable lighting/framing to establish identity-specific coverage.

## Step 6 — Test multiple faces

1. **A:** Start a fresh browser challenge alone, with the face centred.
2. **B:** Enter the camera view beside A during capture; keep both faces clearly visible.
3. **Operator:** Check that guidance reports **“Only one person should be visible.”** and capture stops with **“Capture interrupted. Keep one face centred and retry.”** No usable sequence, review screen, or check-in request is permitted.
4. **Operator/A/B:** Repeat using Step 8: begin with A alone, have B enter after approximately one second, then keep both faces visible for the remainder. Keep the frames valid and within timing limits.
5. **Operator:** Confirm M2 returns `passed=false`, `verification_id=null`, and records a failed challenge. Also repeat with both faces visible from the beginning using direct capture.

**Success:** Both initial and mid-sequence multiple-face evidence are rejected by the server. If the second face is too small/occluded to be detected, reposition and repeat; do not report that attempt as verified multiple-face coverage.

## Step 7 — Test abrupt movement

1. **A:** Start a fresh browser challenge with eyes open and face centred.
2. **A:** During capture, move the head quickly sideways, then return and attempt two blinks. Avoid moving the camera itself.
3. **Operator:** If A leaves the central capture region, check for the browser interruption error and cleared frames. If capture remains available, click **Verify this sequence** and inspect the server result.
4. **Operator/A:** Use Step 8 for a controlled server attempt. Start steady for about one second, then move sideways sharply between consecutive frames while keeping one face visible. The movement should exceed approximately 15% of the frame width between adjacent samples. Continue looking at the camera and complete two blinks if possible.
5. **Operator:** Expect `passed=false`, `verification_id=null`, and a failed challenge. The current server compares adjacent nose positions and rejects displacement greater than 0.15 in normalized image coordinates.

**Success:** A qualifying abrupt-motion sequence produces no proof. A slow movement or a movement below the threshold is not evidence for this scenario. If the face disappears instead, record face-loss rejection and repeat to obtain movement-specific coverage. The response has no detailed failure-reason field, so do not infer the precise rejection cause from scores alone.

## Step 8 — Submit negative sequences directly to the server

Use this procedure for browser-blocked scenarios to prove server enforcement. It leaves the application code unchanged and uses the real camera and real M3 service.

1. **A/operator:** Leave M1 on the live camera at **Blink twice**, idle rather than capturing. Clear earlier evidence with **Retry** or **Retake / repeat verification** as available. For identity/multiple-face scenarios, position participants as described above.
2. **Operator:** As A in Swagger/Postman, send `POST /api/v1/motion/challenges` with `{"session_id":"<SESSION_ID>"}`. Expect 201; record `challenge_id` and expiry. This replaces earlier proof for A/session. Submit the capture before expiry and session closing.
3. **Operator:** In M1's browser developer console, run this local helper. Have the participant perform the scenario during its approximately five-second capture. Supply A's current bearer token privately when prompted; do not include it in saved console commands or evidence.

```javascript
(async () => {
  const video = document.querySelector('video');
  if (!video || video.readyState < 2 || !video.videoWidth) {
    throw new Error('Start the live M1 camera first.');
  }
  const challengeId = prompt('Fresh challenge ID');
  const token = prompt('Student A bearer token (keep private)');
  if (!challengeId || !token) throw new Error('Challenge ID and token required.');
  const canvas = document.createElement('canvas');
  const scale = Math.min(1, 480 / Math.max(video.videoWidth, video.videoHeight));
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const context = canvas.getContext('2d');
  const frames = [];
  const start = performance.now();
  for (let i = 0; i < 60; i++) {
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    frames.push({
      image: canvas.toDataURL('image/jpeg', 0.7).split(',')[1],
      timestamp_ms: Math.round(performance.now() - start),
    });
    await new Promise(resolve => setTimeout(resolve, 80));
  }
  if (frames[0].timestamp_ms > 250 || frames.at(-1).timestamp_ms > 8000 ||
      frames.at(-1).timestamp_ms - frames[0].timestamp_ms < 1000 ||
      frames.some((f, i) => f.image.length > 100000 || (i > 0 &&
        (f.timestamp_ms <= frames[i-1].timestamp_ms ||
         f.timestamp_ms - frames[i-1].timestamp_ms > 250))) ||
      frames.reduce((sum, f) => sum + f.image.length, 0) > 6000000) {
    throw new Error('Invalid capture timing/size; create a fresh challenge and retry.');
  }
  // Replace this base URL with the effective M1 API URL if different.
  const response = await fetch(
    `http://localhost:8000/api/v1/motion/challenges/${encodeURIComponent(challengeId)}/verify`,
    { method: 'POST', headers: {
        Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
      }, body: JSON.stringify({ frames }) },
  );
  frames.length = 0;
  console.log('Verification HTTP status:', response.status);
  console.log('Verification scalar response:', await response.json());
})().catch(error => console.error(error.message));
```

4. **Operator:** Check HTTP 200, `passed=false`, `verification_id=null`, and scores in `[0,1]`. Check the SQL state/result before issuing another challenge, since replacement deletes the previous row. Verify real M2 → M3 `/liveness/sequence` activity using sanitized service telemetry/logs where available.
5. **Operator:** Run the same helper once with A alone, steady, eyes open at the beginning/end, and two complete blinks. Expect `passed=true` and a verification ID; do not check in. Replace this control challenge before further negative attempts.

**Success:** Negative evidence reaches the real server and is rejected while the same capture method can pass valid evidence. HTTP 422/413 means invalid request/timing/size; retry with valid capture rather than counting it as biometric rejection. HTTP 503 means service/model failure; mark the biometric assertion BLOCKED pending recovery. HTTP 409 means expired/replaced/already submitted challenge; create a fresh one. Do not resubmit the same challenge.

## Step 9 — Prove failure cannot be used to submit attendance

Perform these checks **after each server-rejected scenario, before starting another challenge**. Use A's credentials and the same session, in-window location, and device fingerprint.

1. **Operator:** POST `/api/v1/checkins/` with the body below, omitting `motion_verification_id`.
2. **Check:** HTTP 400, `detail="Complete the motion challenge before checking in"`. No attendance is inserted.
3. **Operator:** Add `"motion_verification_id":"<FAILED_CHALLENGE_ID>"` and repeat.
4. **Check:** HTTP 409, `detail="Verification expired or already used; repeat the challenge"`. The current message also covers failed proof; the challenge must remain failed, not consumed.
5. **Operator:** Omit the verification ID again and add `liveness_challenge_response` containing a valid test photo, supplied locally through the API client.
6. **Check:** HTTP 400 with the mandatory-motion message. A photo must not bypass the policy. No photo-based fallback may produce attendance.

```json
{
  "session_id": "<SESSION_ID>",
  "latitude": 1.3483,
  "longitude": 103.6831,
  "location_accuracy_meters": 10,
  "device_fingerprint": "it09-test-browser"
}
```

Replace coordinates with the declared in-range fixture configured for this session. Keep unrelated eligibility checks passing. A 400 caused by a closed session, existing attendance, or enrollment failure is not proof of motion enforcement.

**Success:** All bypass attempts fail without any check-in row, including flagged/rejected/pending rows. Never invent a verification ID: use the actual rejected challenge ID to exercise its failed state.

## Step 10 — Check persistence and dashboard after every scenario

**Operator:** Run these read-only queries in a new PostgreSQL connection, substituting recorded IDs:

```sql
SELECT COUNT(*) AS attendance_count
FROM checkins
WHERE student_id = '<STUDENT_ID>' AND session_id = '<SESSION_ID>';

SELECT id, user_id, session_id, state, expires_at, result
FROM motion_challenges
WHERE id = '<CHALLENGE_ID>';
```

**Expected:** attendance count is zero. A browser-blocked, never-submitted challenge remains `issued` with no result; this is expected and does not represent usable proof. A server-evaluated negative is `failed`, with scalar result containing `passed=false`. A failed challenge must never become verified/consumed. No images, landmarks, or embeddings belong in `result`. Inspect before the next issuance, which removes previous challenges for A/session and prunes expired rows.

**A/staff:** Refresh personal attendance and M4's session attendance view. Independently repeat `GET /api/v1/checkins/my-checkins` and `GET /api/v1/checkins/session/{SESSION_ID}`. Confirm no A/session attendance row and no increase in the isolated session's recorded attendance total. Dashboard absence alone is insufficient; SQL/API reads are required. M4 substitutes missing biometric scores with zero, so its score cells do not establish rejection.

**Success:** Every negative scenario leaves persisted attendance and dashboard attendance unchanged.

## Step 11 — Verify recovery with a fresh valid attempt

1. **A:** Return alone, centre the face, and use **Start challenge** to obtain a new ID. Perform two natural blinks with complete reopening, then click **Verify this sequence**.
2. **Operator:** Expect 201 on issuance, 200 with `passed=true` and non-null proof on verification, and `state='verified'`. Confirm all prior negative cases still have recorded evidence even though their challenge rows may now be replaced.
3. **A:** Confirm the review screen says **Motion verified by server**, then click **Submit check-in** once.
4. **Operator:** Expect 201 with `status='approved'`, `liveness_passed=true`, and `face_match_passed=true`. SQL must now show exactly one check-in for A/session, and this new challenge must be `consumed`.
5. **A/staff:** Refresh personal and session attendance views. Confirm the same check-in ID appears and only this final valid attempt changed attendance.

**Success:** Failures do not permanently prevent a valid retry, and only fresh passing proof creates approved attendance. A flagged/rejected final control is a recovery failure to investigate, even if the negative-case rejection checks passed.

## Recording and acceptance

For every row, record PASS / FAIL / BLOCKED, actual UI behavior, HTTP status/scalar response, challenge ID, attendance count, and defect/evidence reference.

| Scenario | Browser capture check | Real server rejection | Failed/missing-proof bypass checks | SQL/API/M4 no attendance | Result |
| --- | --- | --- | --- | --- | --- |
| Zero blinks | | | | | |
| One blink | | | | | |
| Incomplete second reopening | | | | | |
| Two blinks but closed final eyes | Server-only variant | | | | |
| Different person's face | | | | | |
| Multiple faces entering mid-capture | | | | | |
| Multiple faces from first frame | Server-only variant | | | | |
| Abrupt movement | | | | | |

Record the initial positive control, direct-helper positive control, and final recovery separately. Overall PASS requires every scenario's applicable checks, real server rejection, zero attendance during all negative attempts, and successful recovery. A usable proof or any attendance created by a negative attempt is FAIL. Browser rejection without server coverage is incomplete; unavailable native models or invalid fixtures are BLOCKED, not PASS.

After recording results, close the test session through the authorized API and sign out. Preserve test records for investigation. Use a new session for another run because the final recovery creates attendance.

## Implementation references

This plan follows the current [M1 verification UI](../../module1-frontend/components/check-in/FaceVerification.tsx), [browser capture logic](../../module1-frontend/features/camera/useFaceGuidance.ts), [M2 challenge/proof lifecycle](../../module2-backend/app/motion.py), [M2 check-in enforcement](../../module2-backend/app/main.py), [M3 sequence analyzer](../../module3-face-recognition/app/motion.py), and [M4 attendance reads](../../module4-observability/src/lib/attendance.ts). Contracts are in the [API specification](../../docs/API-SPECIFICATION.md), [database schema](../../docs/DATABASE-SCHEMA.md), [integration guide](../../docs/INTEGRATION-GUIDE.md), and [motion verification documentation](../MOTION-VERIFICATION.md).

Existing automated supplements include [blink/sequence logic](../../new-tests/test_motion_sequence.py), [backend proof contracts](../../new-tests/test_motion_backend.py), and [native landmarker checks](../../new-tests/test_motion_landmarker.py). Mocked tests supplement but do not replace these real browser/service/database steps. This documentation change does not claim any test execution or result.
