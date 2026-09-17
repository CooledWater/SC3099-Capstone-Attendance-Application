# Face enrollment and motion verification

Students enroll once through the existing `POST /api/v1/users/me/face/enroll` endpoint. The frontend reads `/users/me` before deciding whether enrollment is needed. Enrollment uses a manual photo, preview, and retake. It binds a face to the authenticated account; it does not establish school identity independently.

Check-in offers live blink guidance and temporary sequence capture. An optional photo-only path remains for sessions that do not mandate motion. Existing image APIs and session defaults are unchanged. To require motion, the instructor who owns a session (or an admin) sets `require_motion_check: true` through the existing session create/PATCH API. The dashboard has not been changed; configuring this new policy currently uses the API. Required motion includes an enrolled-face match, even if the legacy face-match flag is false.

## Additive API

- `POST /api/v1/motion/challenges` with `{session_id}`: requires authenticated student, enrollment in an open session, camera consent, and face enrollment. Returns `challenge_id`, `action: "blink_twice"`, `expires_at`, `max_duration_ms: 8000`, and `max_frames: 120`. Expiry is at most three minutes and never later than the attendance window. Starting again invalidates that student's previous attempt for the session.
- `POST /api/v1/motion/challenges/{id}/verify` with `{frames: [{image, timestamp_ms}]}`: one submission per challenge. Images are base64 JPEG/PNG. Returns `passed`, `blink_count`, scores, and `verification_id` only on success. Failure or transport timeout requires a fresh challenge.
- `POST /api/v1/checkins/` accepts optional `motion_verification_id`. Ownership, session, current enrolled reference, expiry, and one-time use are checked server-side. Consumption and attendance insertion share a transaction. Required-motion sessions cannot fall back to the legacy path.
- Internal Module 3 `POST /liveness/sequence` accepts the same frames plus `reference_template_hash`. It returns only scalar outcomes, never images/landmarks.

## Processing and limits

The browser serves the pinned MediaPipe Tasks Vision 0.10.32 WASM and Google's version-1 Face Landmarker model locally from `/mediapipe`. No camera frames go to Google or a CDN. Tracking runs sequentially at a bounded rate on the main thread; slower devices may need a future worker implementation. The captured frame is also the frame analysed for guidance. Frames are at most 480px on their longest side, JPEG quality 0.7, sampled with a 66ms delay between analyses. Actual frame gaps must not exceed 250ms; slow or interrupted captures ask for retry.

The server accepts 15–120 frames over 1–8 seconds, at most 100,000 base64 characters per frame and 6,000,000 total. Module 2 bounds actual request bytes before parsing, including chunked uploads. Capture timestamps establish ordering, not trusted wall-clock authenticity. The browser timeout for sequence verification is 55s; the internal request timeout is 45s, with a 40s analysis budget checked between frames. Final attendance submission does not repeat sequence processing.

Module 3 requires one face throughout, rejects abrupt position jumps, and counts complete open–closed–open cycles with hysteresis (EAR closed <0.19, open >=0.23; observed closure 40–700ms). It checks identity every eighth frame, at blink completion, and in the final frame, plus passive liveness on first and last frames. These thresholds require calibration with real cameras and diverse users. Intermediate-frame identity is sampled, not guaranteed. The fixed two-blink challenge, even with an expiring ID, does not prevent a prepared video replay or virtual-camera injection; do not describe this as production-grade anti-spoofing.

## Storage and rollout

Only two new metadata tables are introduced: `session_motion_policies` and `motion_challenges`. They use existing user/session UUIDs with cascading foreign keys. No existing table columns change, so the application's existing `Base.metadata.create_all()` creates these tables on startup for both new and existing databases. Deploy Module 3, then Module 2, then the frontend. Expired challenge metadata is pruned when a new challenge is issued. Challenge rows contain a reference hash and scores, never raw images, landmarks, or embeddings. Browser frames stay in component memory and are discarded on retry, completion, camera interruption, session change, or unmount. They are never added to IndexedDB.

## Validation

Run backend tests separately from native Module 3 tests (both modules name their Python package `app`). `new-tests/test_motion_backend.py` launches its isolated cases in a subprocess. The cases use temporary SQLite and a mocked Module 3 transport; they do not prove actual camera/model accuracy. `new-tests/test_motion_sequence.py` covers temporal logic and contract boundaries. Existing public HTTP tests should target an isolated running backend. Real model tests and real-camera trials remain necessary before enabling required motion for students.

### Validation performed for this change

- Existing backend/public contracts, integration, security, privacy, performance, and refresh-cookie tests: **65 passed, 1 skipped**, against a temporary SQLite backend.
- Existing public face-recognition HTTP tests: **15 passed**, against the real local Module 3 service.
- Existing additional Module 3 tests: **22 passed**, with native MediaPipe/dlib models.
- New checks: **13 backend cases + 15 temporal/sequence cases + 1 real-model static-photo rejection = 29 passed**. Backend cases mock the face-service transport; the native smoke test does not.
- Final frontend production compilation, TypeScript, and lint passed in a temporary clean copy. The pre-existing untracked `app/page 2.tsx` imports missing `localforage` and blocks normal workspace type-checking; duplicate `* 2` files were excluded from that validation copy and left untouched in the workspace.
- No interactive browser connection was available, so actual webcam capture, model loading in the browser, blink accuracy, and mobile-device performance still require manual validation. Tests do not certify production anti-spoofing or PostgreSQL concurrency behaviour.
