# SAIV — Product Requirements Document

**Product:** SAIV — Secure Attendance & Identity Verification
**Version:** 1.0
**Status:** Baseline requirements derived from the project specifications
**Sources:** `README.md`, `docs/Briefing.md`, `docs/API-SPECIFICATION.md`, `docs/DATABASE-SCHEMA.md`, `docs/SECURITY-REQUIREMENTS.md`, `docs/INTEGRATION-GUIDE.md`, `docs/module1.md`–`docs/module4.md`, `tests/public/*`

---

## 1. Product Overview

### 1.1 Problem

Classroom attendance systems based on sign-in sheets, codes, or plain selfies are trivially defeated: a student can pass their phone to a friend, share a code from off-campus, hold a printed photo to the camera, or spoof GPS. SAIV is an attendance verification system that treats every check-in as a claim to be verified against multiple independent signals rather than a fact to be recorded.

### 1.2 Product Goal

Allow a student to prove — quickly, from their own phone browser — that *this specific person* is *physically present* at *this specific class session*, while storing as little personal data as practically possible, and give instructors the tooling to monitor, adjudicate, and export the result.

### 1.3 Users

| User | Role code | What they do with SAIV |
|------|-----------|------------------------|
| Student | `student` | Registers, enrolls face, registers device, checks in to sessions, views own attendance history, appeals rejected check-ins |
| Teaching Assistant | `ta` | Everything a student can do, plus views check-ins for assisted courses and reviews flagged check-ins |
| Instructor | `instructor` | TA capabilities plus session lifecycle management, course analytics, enrollment management, data export |
| Administrator | `admin` | Full system access: user management, course creation, audit log access, test/state fixtures |

### 1.4 Threat Model — attacks the product must resist

| Attack | Defense feature |
|--------|-----------------|
| Proxy sign-in (friend checks in for you) | Face verification against enrolled template; device binding |
| Printed photo held to camera | Liveness detection — 3D depth cues, flat-image rejection |
| Screen replay (photo/video played on a phone) | Liveness detection — texture/moiré and flat z-coordinate analysis |
| Deepfake / synthetic face | Liveness detection — face-mesh completeness, colour distribution, texture variance |
| Remote check-in from off-campus | Geofencing with Haversine distance; GPS accuracy signals |
| GPS spoofing | Impossible-travel detection, geolocation accuracy signals, distance-based hard rejection |
| VPN / proxy / Tor to fake network origin | Network signal analysis in risk scoring |
| Replay of a captured check-in payload | Device signature/attestation, one-time QR secrets, rapid-succession detection |
| Emulator / rooted device farms | Device attestation flags (`is_emulator`, `is_rooted_jailbroken`) |
| Brute-force credential attack | Rate limiting, bcrypt cost factor, account deactivation |

### 1.5 Non-Goals

- HTTPS/TLS termination — the system runs over HTTP in all environments for this project.
- 1:N face identification ("who is this?"). SAIV performs only 1:1 verification ("is this the enrolled person?").
- Native mobile applications. The student client is a Progressive Web App running in a mobile browser.
- Push notifications (optional PWA capability, not required).

---

## 2. System Composition

SAIV consists of four independently deployable services that communicate over HTTP:

| Module | Service | Port | Responsibility |
|--------|---------|------|----------------|
| Module 1 | Student Frontend PWA | 3000 | Student-facing check-in experience |
| Module 2 | Backend API | 8000 | All business logic, persistence, authorization, orchestration |
| Module 3 | Face Recognition & Risk Service | 8001 | Face enrollment, verification, liveness, risk scoring |
| Module 4 | Observability & Instructor Dashboard | 8501 | Instructor portal, analytics, export, monitoring |

All client traffic goes through the Backend API. The Backend orchestrates calls to the Face Recognition service; the frontend never calls it directly for a check-in decision.

---

## 3. Feature Requirements

Requirements are identified `F-<AREA>-<n>`. Each feature states the behaviour observable through the HTTP interface, since the system is validated by black-box HTTP tests.

---

### 3.1 Authentication (F-AUTH)

#### F-AUTH-1 — User Registration
`POST /api/v1/auth/register`

**Behaviour**
- Accepts `email`, `password`, `full_name`, and optional `role` (`student` | `ta` | `instructor` | `admin`). Role is accepted at face value at registration — no privilege restriction is applied.
- On success returns **201 Created** with `id`, `email`, `full_name`, `role`, `is_active`, `created_at`. The password (plain or hashed) must never appear in the response.
- Password is stored only as a bcrypt hash with cost factor ≥ 10 (~100 ms per hash).
- New accounts default to `is_active: true`, `camera_consent: false`, `geolocation_consent: false`, `face_enrolled: false`.

**Validation and errors**
- Password shorter than 8 characters → **422**.
- Malformed email (RFC 5322 non-compliant) → **422**.
- Email already registered → **400** with a `detail` field.
- A 422 body lists every invalid field with its location and reason.

*Verified by:* `test_user_registration`, `test_duplicate_registration_fails`, `test_weak_password_rejected`, `test_invalid_email_rejected`, `test_registration_response_format`, `test_422_validation_error_format`, `test_400_error_format`

---

#### F-AUTH-2 — Login and Token Issuance
`POST /api/v1/auth/login`

**Behaviour**
- Accepts `email` and `password`; on success returns **200** with `access_token`, `refresh_token`, `token_type: "bearer"`, and a nested `user` object containing at minimum `id`, `email`, `role`.
- Access tokens are HS256-signed JWTs expiring in 1 hour; refresh tokens expire in 7 days. The signing key comes from the `SECRET_KEY` environment variable and is never hardcoded.
- Token payload carries `sub` (user id), `email`, `role`, `exp`, `iat` — and no sensitive data such as password hashes or biometric material.
- A successful login updates `last_login_at` and writes a `login_success` audit entry; a failure writes `login_failed`.

**Validation and errors**
- Wrong password or unknown email → **401**.
- Deactivated account (`is_active: false`) → **403**, even when the password is correct.
- The submitted password must not appear anywhere in the response body.

*Verified by:* `test_user_login_success`, `test_login_wrong_password_fails`, `test_password_not_in_response`, `test_inactive_user_cannot_login`, `test_login_response_format`, `test_auth_endpoint_latency`

---

#### F-AUTH-3 — Token Refresh
`POST /api/v1/auth/refresh`

**Behaviour**
- Accepts `refresh_token`, returns **200** with a fresh `access_token` *and* a `refresh_token` plus `token_type`.
- An expired, malformed, or invalidly signed refresh token is rejected.

*Verified by:* `test_token_refresh`, `test_token_refresh_format`

---

#### F-AUTH-4 — Token Enforcement on Protected Endpoints

**Behaviour**
- Every protected endpoint requires `Authorization: Bearer <access_token>`.
- Missing token → **401** or **403**, with a `detail` field in the body.
- Structurally invalid token (e.g. `"invalid_token_12345"`) → **401**/**403**.
- Expired token, or a token whose signature does not verify → **401**/**403**. Signature verification is mandatory; the payload alone must never be trusted.

*Verified by:* `test_unauthorized_access_fails`, `test_invalid_token_rejected`, `test_expired_token_rejected`, `test_401_error_format`

---

#### F-AUTH-5 — Logout
`POST /api/v1/auth/logout`

**Behaviour**
- Ends the client session and writes a `logout` audit entry.

---

### 3.2 Role-Based Access Control (F-RBAC)

#### F-RBAC-1 — Role Hierarchy

**Behaviour**
- Four roles, ordered `admin` (4) > `instructor` (3) > `ta` (2) > `student` (1).
- Authorization is enforced server-side on every request from the JWT `role` claim. Hiding UI controls is never a substitute — a hidden button must still map to a protected endpoint.
- A caller who is authenticated but insufficiently privileged receives **403**, distinct from the **401** returned to an unauthenticated caller.

#### F-RBAC-2 — Endpoint Permission Matrix

| Endpoint | student | ta | instructor | admin |
|----------|:-------:|:--:|:----------:|:-----:|
| `GET /users/me`, `PUT /users/me` | ✔ | ✔ | ✔ | ✔ |
| `GET /users/`, `PATCH /users/{id}` | ✘ | ✘ | ✘ | ✔ |
| `POST /courses/`, `DELETE /courses/{id}` | ✘ | ✘ | ✘ | ✔ |
| `GET /courses/`, `GET /courses/{id}` | ✔ | ✔ | ✔ | ✔ |
| `PUT /courses/{id}` | ✘ | ✘ | ✔ (own course) | ✔ |
| `POST /checkins/` | ✔ | ✘ | ✘ | ✘ |
| `GET /checkins/my-checkins` | ✔ | ✔ | ✔ | ✔ |
| `GET /checkins/session/{id}`, `GET /checkins/`, `GET /checkins/flagged` | ✘ | ✔ | ✔ | ✔ |
| `POST /checkins/{id}/review` | ✘ | ✔ | ✔ | ✔ |
| `POST /checkins/{id}/appeal` | ✔ (own) | — | — | — |
| `POST /sessions/`, `PATCH /sessions/{id}`, `DELETE /sessions/{id}` | ✘ | ✘ | ✔ (own) | ✔ |
| `GET /sessions/active` | public — no auth required | | | |
| `GET /stats/*` | ✘ | ✔ (scoped) | ✔ | ✔ |
| `GET /export/*` | ✘ | ✘ | ✔ (own course) | ✔ |
| `GET /audit/`, `GET /audit/summary` | ✘ | ✘ | ✘ | ✔ |
| `GET /devices/` (all devices) | ✘ | ✘ | ✘ | ✔ |
| `/admin/**` | ✘ | ✘ | ✘ | ✔ |

**Explicitly required negative behaviours**
- A student requesting `GET /checkins/session/{id}` → **403**.
- A student requesting `GET /audit/` → **403**.
- An instructor requesting `GET /users/` → **401**/**403**.
- An instructor requesting `POST /courses/` → **401**/**403** (course creation is admin-only).

*Verified by:* `test_student_cannot_access_instructor_endpoints`, `test_instructor_can_view_session_checkins`, `test_non_admin_cannot_access_audit_logs`, `test_list_users_forbidden_for_instructor`, `test_create_course_forbidden_for_instructor`

---

### 3.3 User & Profile Management (F-USER)

#### F-USER-1 — Own Profile Retrieval
`GET /api/v1/users/me`

**Behaviour**
- Returns `id`, `email`, `full_name`, `role`, `camera_consent`, `geolocation_consent`, `face_enrolled`, `created_at`.
- `role` is always one of `student`, `instructor`, `ta`, `admin` — the dashboard uses it for permission gating.
- Must **not** contain `password` or `hashed_password` under any circumstance.

*Verified by:* `test_get_current_user`, `test_passwords_not_in_user_response`, `test_user_profile_format`, `test_camera_consent_required`, `test_geolocation_consent_required`, `test_user_has_scheduled_deletion_field`

---

#### F-USER-2 — Own Profile Update
`PUT /api/v1/users/me`

**Behaviour**
- Accepts partial updates of `full_name`, `camera_consent`, `geolocation_consent`; returns **200** with the updated user object reflecting the new values exactly.
- Consent flags are freely togglable in both directions — a user may withdraw consent at any time.
- User-supplied text is sanitized. Submitting `<script>alert('XSS')</script>` as `full_name` must either be rejected or stored/returned with the raw `<script>` tag removed or escaped — it must never round-trip verbatim.

*Verified by:* `test_update_user_profile`, `test_consent_can_be_updated`, `test_xss_payload_sanitized`

---

#### F-USER-3 — User Directory (Admin)
`GET /api/v1/users/`

**Behaviour**
- Admin-only. Returns a paginated envelope `{items, total, limit, offset}`.
- Supports filters: `role`, `is_active`, `search` (matches name or email), `limit` (default 50, max 100), `offset` (default 0).

*Verified by:* `test_list_users_admin`, `test_list_users_forbidden_for_instructor`

---

#### F-USER-4 — User Detail & Administrative Update
`GET /api/v1/users/{user_id}` · `PATCH /api/v1/users/{user_id}`

**Behaviour**
- `GET` is available to admins, and to instructors for students enrolled in their courses.
- `PATCH` is admin-only and may change `role` and `is_active`.

---

#### F-USER-5 — Face Enrollment via Backend
`POST /api/v1/users/me/face/enroll`

**Behaviour**
- Accepts a base64-encoded image (no `data:` URL prefix) and forwards it to the Face Recognition service.
- Requires `camera_consent: true` on the calling user; otherwise **400**.
- On success returns `{success: true, message, face_enrolled: true, quality_score}`, persists the returned template hash into `users.face_embedding_hash`, sets `face_enrolled = true`, and writes a `face_enrolled` audit entry.
- No face detected in the image → **400**.
- Face service unreachable → **503**.
- The raw image is never persisted at any layer.

---

### 3.4 Course Management (F-COURSE)

#### F-COURSE-1 — Course Listing
`GET /api/v1/courses/`

**Behaviour**
- Available to any authenticated user. Returns either a bare list or a `{items, total, limit, offset}` envelope; each course carries `id`, `code`, `name`, `semester` at minimum, plus venue coordinates, geofence radius, risk threshold, and `is_active`.
- Filters: `is_active` (default true), `semester`, `instructor_id` (admin only), `limit`, `offset`.

*Verified by:* `test_list_courses`, `test_courses_list_format`, `test_list_endpoint_latency`, `test_pagination_support`

---

#### F-COURSE-2 — Course Detail
`GET /api/v1/courses/{course_id}`

**Behaviour**
- Returns the full course object: metadata, default venue coordinates and name, `geofence_radius_meters`, `require_face_recognition`, `require_device_binding`, `risk_threshold`.

*Verified by:* `test_get_course_details`

---

#### F-COURSE-3 — Course Creation
`POST /api/v1/courses/`

**Behaviour**
- **Admin only.** Accepts `code` (unique), `name`, `semester`, and optionally `instructor_id`, `venue_name`, `venue_latitude`, `venue_longitude`, `geofence_radius_meters` (default 100.0), `risk_threshold` (default 0.5), `require_device_binding` (default true).
- Returns **201** with the created course. Duplicate `code` is rejected.
- An instructor attempting creation receives **401**/**403**.

*Verified by:* `test_create_course_admin`, `test_create_course_forbidden_for_instructor`

---

#### F-COURSE-4 — Course Update and Soft Delete
`PUT /api/v1/courses/{course_id}` · `DELETE /api/v1/courses/{course_id}`

**Behaviour**
- `PUT` supports partial update by an admin or the course's own instructor.
- `DELETE` is admin-only and performs a **soft delete** (`is_active = false`), returning **204**. Records are preserved for the audit trail.

---

### 3.5 Enrollment Management (F-ENROLL)

#### F-ENROLL-1 — Student's Own Enrollments
`GET /api/v1/enrollments/my-enrollments`

**Behaviour**
- Returns a list; each entry carries `id`, `course_id`, `course_code`, `course_name`, `semester`, `instructor_name`, `enrolled_at`, `is_active`.

*Verified by:* `test_my_enrollments`

---

#### F-ENROLL-2 — Course Roster
`GET /api/v1/enrollments/course/{course_id}`

**Behaviour**
- Available to the course's instructor/TA. Returns `{course_id, course_code, total_enrolled, students: [...]}` where each student carries `id`, `student_id`, `student_email`, `student_name`, `enrolled_at`, `is_active`, `face_enrolled`.
- Filters: `is_active` (default true), `search` by name or email.

*Verified by:* `test_list_course_enrollments`

---

#### F-ENROLL-3 — Single Enrollment
`POST /api/v1/enrollments/`

**Behaviour**
- Instructor (for their own course) or admin. Accepts `student_id`, `course_id`; returns **201**.
- Duplicate enrollment → **400**; unknown student or course → **404**.
- The `(student_id, course_id)` pair is unique — the database enforces this.

---

#### F-ENROLL-4 — Bulk Enrollment by Email
`POST /api/v1/enrollments/bulk`

**Behaviour**
- Accepts `course_id`, `student_emails[]`, and `create_accounts` (boolean). Returns counts of `enrolled`, `already_enrolled`, `not_found`, `created`, plus a per-email `details` array.
- When `create_accounts` is true, unknown emails produce new student accounts.

---

#### F-ENROLL-5 — Enrollment Removal
`DELETE /api/v1/enrollments/{enrollment_id}`

**Behaviour**
- Instructor for the course, or admin. Returns **204** and records `dropped_at`.

---

### 3.6 Session Management (F-SESSION)

#### F-SESSION-1 — Session Creation
`POST /api/v1/sessions/`

**Behaviour**
- **Instructor role.** Accepts `course_id`, `name`, `session_type` (`lecture` | `tutorial` | `lab` | `exam`, default `lecture`), `scheduled_start`, `scheduled_end`, and optional `checkin_opens_at`, `checkin_closes_at`, venue overrides, `geofence_radius_meters`, `require_liveness_check` (default true), `require_face_match` (default false), `risk_threshold`.
- `checkin_opens_at` defaults to 15 minutes before `scheduled_start`; `checkin_closes_at` defaults to 30 minutes after.
- Returns **201** with the created session; a newly created session always starts in status **`scheduled`**.
- Validation: the course must be one the instructor teaches; `scheduled_end` after `scheduled_start`; `checkin_closes_at` after `checkin_opens_at`.
- Writes a `session_created` audit entry.

*Verified by:* `test_create_session`

---

#### F-SESSION-2 — Session Lifecycle
`PATCH /api/v1/sessions/{session_id}`

**Behaviour**
- Partial update by the owning instructor; returns **200** with the updated object.
- Legal status transitions: `scheduled → active` (opens the check-in window), `active → closed` (closes check-in and finalizes attendance), and any status → `cancelled`.
- **Check-ins are accepted only while the session is `active`.** A session left in `scheduled` rejects all check-ins.

*Verified by:* `test_update_session`

---

#### F-SESSION-3 — Session Deletion
`DELETE /api/v1/sessions/{session_id}`

**Behaviour**
- Owning instructor only. Only `scheduled` sessions may be deleted; `active`/`closed` sessions must be cancelled instead. Returns **204**.

---

#### F-SESSION-4 — Session Listing (Instructor/Admin)
`GET /api/v1/sessions/`

**Behaviour**
- Returns a paginated envelope `{items, total, limit, offset}` — the bare-list form is not acceptable here.
- Filters: `status`, `course_id`, `instructor_id`, `start_date`, `end_date`, `limit`, `offset`.
- Each item is enriched with `course_code`, `course_name`, `total_enrolled`, `checked_in_count`.

*Verified by:* `test_list_sessions_with_filters`

---

#### F-SESSION-5 — Active Session Discovery
`GET /api/v1/sessions/active`

**Behaviour**
- **Public — no authentication.** Returns a bare JSON array of sessions whose check-in window is currently open.
- Each entry carries `id`, `name`, `status`, `scheduled_start`, `scheduled_end`, and typically `course_id`, `course_code`, `checkin_opens_at`, `checkin_closes_at`, `venue_name`.

*Verified by:* `test_list_active_sessions`, `test_active_sessions_format`

---

#### F-SESSION-6 — Personal Session Feed
`GET /api/v1/sessions/my-sessions`

**Behaviour**
- For students, sessions belonging to enrolled courses; for instructors, sessions they teach. Filters: `status`, `upcoming`, `limit`.

---

#### F-SESSION-7 — Session Detail
`GET /api/v1/sessions/{session_id}`

**Behaviour**
- Available to any authenticated user. Must include `id`, `course_id`, `name`, `status`, `scheduled_start`, `scheduled_end`, `checkin_opens_at`, `checkin_closes_at` — the dashboard depends on all eight.
- Also returns venue coordinates and name, `geofence_radius_meters`, `require_liveness_check`, `require_face_match`, `risk_threshold`, `qr_code_enabled`.
- `status` is always one of `scheduled`, `active`, `closed`, `cancelled`.

*Verified by:* `test_get_session_details`, `test_session_details_format`

---

#### F-SESSION-8 — QR Code Challenge (Optional)

**Behaviour**
- A session may carry a one-time `qr_code_secret` with `qr_code_expires_at`. When enabled, a check-in must present a matching `qr_code`, and the result is recorded in `checkins.qr_code_verified`.

---

### 3.7 Check-In (F-CHECKIN) — the core flow

#### F-CHECKIN-1 — Check-In Submission
`POST /api/v1/checkins/`

**Behaviour**
- **Student role only.** Request body: `session_id`, `latitude`, `longitude`, `location_accuracy_meters` (optional), `device_fingerprint`, `liveness_challenge_response` (optional base64 image), `qr_code` (optional). Optional fields explicitly sent as `null` must be accepted without error.
- On success returns **201** with at minimum `id`, `session_id`, `student_id`, `status`, `checked_in_at`, `risk_score`, and where applicable `latitude`, `longitude`, `distance_from_venue_meters`, `liveness_passed`, `liveness_score`, `risk_factors`.
- `status` is always one of `pending`, `approved`, `flagged`, `rejected`.
- Must complete in **under 2 seconds** end to end, including the face-service round trip.

**Processing pipeline (in order)**
1. Validate the session exists and is `active`; reject otherwise.
2. Validate the current time falls inside `[checkin_opens_at, checkin_closes_at]`.
3. Validate the student is actively enrolled in the session's course.
4. Reject a duplicate check-in for the same `(session_id, student_id)`.
5. Resolve or register the device from `device_fingerprint`; compute device trust.
6. If an image was supplied and the session requires it, call the Face service for liveness and/or face match.
7. Compute Haversine distance from the effective venue coordinates (session override, else course default).
8. Fuse all signals into a `risk_score` in [0, 1], persisting each contributing signal as a `risk_signals` row.
9. Apply the status decision rules below.
10. Persist the check-in, increment the device's `total_checkins`, set `scheduled_deletion_at` to 30 days out, and write a `checkin_attempted` audit entry followed by `checkin_approved` / `checkin_flagged` / `checkin_rejected`.

**Status decision rules**

| Condition | Resulting status |
|-----------|------------------|
| `risk_score` < effective threshold, no critical signal | `approved` |
| `risk_score` ≥ effective threshold, no critical signal | `flagged` (queued for human review) |
| Liveness check failed | `rejected` |
| GPS distance > 2× geofence radius | `rejected` |

The effective threshold is the session's `risk_threshold` when set, otherwise the course's, otherwise the system default 0.5.

**Errors**
- Session not active, check-in window closed, or already checked in → **400**.
- Session not found → **404**.
- Not enrolled → **400**/**403**.

*Verified by:* `test_successful_checkin`, `test_duplicate_checkin_fails`, `test_checkin_request_format`, `test_checkin_response_format`, `test_checkin_endpoint_latency`, `test_complete_student_checkin_flow`

---

#### F-CHECKIN-2 — Duplicate Prevention

**Behaviour**
- Exactly one check-in per student per session, enforced by a unique database constraint on `(session_id, student_id)` — not by an application-level check alone, so that concurrent submissions cannot both succeed.
- The second attempt returns **400**.

*Verified by:* `test_duplicate_checkin_fails`

---

#### F-CHECKIN-3 — Student Check-In History
`GET /api/v1/checkins/my-checkins`

**Behaviour**
- Returns a bare JSON array (not a paginated envelope) of the caller's own check-ins, each with `id`, `session_id`, `session_name`, `course_code`, `status`, `checked_in_at`, `risk_score`.
- Filters: `course_id`, `limit`. Returns an empty array — never an error — when the student has no check-ins.

*Verified by:* `test_list_my_checkins`, `test_my_checkins_list_format`

---

#### F-CHECKIN-4 — Session Check-In Roster
`GET /api/v1/checkins/session/{session_id}`

**Behaviour**
- Instructor/TA for the session's course. Returns a bare JSON array; each row carries `id`, `student_id`, `student_name`, `student_email`, `status`, `checked_in_at`, `distance_from_venue_meters`, `risk_score`, `risk_factors`, `liveness_passed`, `device_trusted`.
- Must respond in under 1 second — the join to users and devices must be eager-loaded to avoid N+1 queries.
- Students receive **403**.

*Verified by:* `test_session_checkins_format`, `test_instructor_can_view_session_checkins`, `test_student_cannot_access_instructor_endpoints`, `test_no_n_plus_one_queries`

---

#### F-CHECKIN-5 — Global Check-In Query
`GET /api/v1/checkins/`

**Behaviour**
- Instructor/admin. Returns a paginated envelope `{items, total, limit, offset}`.
- Filters: `session_id`, `course_id`, `student_id`, `status`, `min_risk_score`, `max_risk_score`, `start_date`, `end_date`, `limit`, `offset`.

*Verified by:* `test_list_all_checkins`

---

#### F-CHECKIN-6 — Flagged Review Queue
`GET /api/v1/checkins/flagged`

**Behaviour**
- Instructor/TA. Returns a paginated envelope `{items, total, ...}`.
- **Every returned item has `status` of `flagged` or `appealed`** — no other status may appear in this queue.
- Each item includes the risk detail an instructor needs to adjudicate: `risk_score`, `risk_factors` (each with `type`, `severity`, `weight`), `student_name`, `session_name`, and `appeal_reason` / `appealed_at` when the student has appealed.
- Filters: `course_id`, `session_id`, `limit`.

*Verified by:* `test_flagged_checkins_queue`

---

#### F-CHECKIN-7 — Check-In Detail
`GET /api/v1/checkins/{checkin_id}`

**Behaviour**
- Accessible to the owning student, or an instructor/TA for the session's course. Returns the full record including all associated risk signals.

---

#### F-CHECKIN-8 — Student Appeal
`POST /api/v1/checkins/{id}/appeal`

**Behaviour**
- Owning student only. Accepts `appeal_reason`; sets status to `appealed`, records `appealed_at`, returns **200**.
- Only `rejected` or `flagged` check-ins may be appealed, at most once, within 7 days of `checked_in_at`.
- Writes a `checkin_appealed` audit entry.

---

#### F-CHECKIN-9 — Instructor Review
`POST /api/v1/checkins/{id}/review`

**Behaviour**
- Instructor/TA for the session's course. Accepts `status` (`approved` | `rejected`) and `review_notes`.
- Sets the final status, records `reviewed_by_id`, `reviewed_at`, `review_notes`; returns **200**.
- Writes a `checkin_reviewed` audit entry.

---

### 3.8 Geofencing & Location (F-GEO)

#### F-GEO-1 — Haversine Distance Calculation

**Behaviour**
- Distance between the submitted GPS coordinates and the effective venue coordinates is computed with the Haversine great-circle formula and stored in `checkins.distance_from_venue_meters`.
- The effective venue is the session's `venue_latitude`/`venue_longitude` when present, otherwise the course's.

#### F-GEO-2 — Geofence Enforcement

**Behaviour**
- Within `geofence_radius_meters` (default 100 m): no geo risk contribution.
- Beyond the radius but within 2×: a `geo_out_of_bounds` risk signal is raised, pushing the check-in toward `flagged`.
- Beyond 2× the radius: the check-in is **rejected** outright, regardless of every other signal.

#### F-GEO-3 — Coordinate Validation

**Behaviour**
- Latitude must be in [−90, 90] and longitude in [−180, 180]; out-of-range values are rejected as validation errors.

#### F-GEO-4 — Location Quality and Anomaly Signals

**Behaviour**
- Poor GPS accuracy raises `geo_accuracy_low`.
- Two check-ins by the same student that are geographically irreconcilable given the elapsed time raise `impossible_travel` — the primary GPS-spoofing defense.
- Location data is used **only** for the geofence decision and is stored with limited precision.

---

### 3.9 Device Binding & Trust (F-DEVICE)

#### F-DEVICE-1 — Device Registration
`POST /api/v1/devices/register` (and `POST /api/v1/devices/`)

**Behaviour**
- Any authenticated user. Accepts `device_fingerprint` (unique across the system), `device_name`, `platform` (`ios` | `android` | `web` | `desktop`), `browser`, and `public_key` (RSA/ECDSA, PEM).
- Returns **201** with `id`, `device_fingerprint`, `device_name`, `platform`, `is_trusted` (false initially), `trust_score` (`low` initially), `is_active`, `first_seen_at`.
- Both `/devices/` and `/devices/register` must accept the registration payload.
- Writes a `device_registered` audit entry.

*Verified by:* `test_device` fixture (exercised throughout), `test_list_my_devices`

---

#### F-DEVICE-2 — Own Device List
`GET /api/v1/devices/my-devices`

**Behaviour**
- Returns a bare JSON array of the caller's devices with `id`, `device_name`, `platform`, `is_trusted`, `trust_score`, `is_active`, `first_seen_at`, `last_seen_at`, `total_checkins`. Empty array when none are registered.

*Verified by:* `test_list_my_devices`, `test_my_devices`

---

#### F-DEVICE-3 — Device Directory (Admin)
`GET /api/v1/devices/`

**Behaviour**
- Admin-only. Returns a paginated envelope `{items, total, ...}`.

*Verified by:* `test_list_all_devices_admin`

---

#### F-DEVICE-4 — Device Update and Revocation
`PATCH /api/v1/devices/{device_id}` · `DELETE /api/v1/devices/{device_id}`

**Behaviour**
- The owner may rename a device or deactivate it; only an admin may set `is_trusted`.
- `DELETE` returns **204** and records `revoked_at` with a `revocation_reason`.

---

#### F-DEVICE-5 — Public Key Rotation

**Behaviour**
- Each device holds a `public_key` with `public_key_created_at` and an optional `public_key_expires_at`, supporting periodic rotation without re-registering the device.

---

#### F-DEVICE-6 — Device Trust Signals

**Behaviour**
- A check-in from a fingerprint not previously bound to the student raises `device_unknown`.
- Emulator detection raises `device_emulator`; root/jailbreak detection raises `device_rooted`; a failed attestation raises `attestation_failed`.
- `trust_score` (`low` | `medium` | `high`) rises with successful check-in history and passing attestation, and feeds the device component of the risk score.
- When a course sets `require_device_binding: true`, an unbound device materially increases risk.

---

### 3.10 Face Recognition Service (F-FACE) — Module 3, port 8001

The service is called internally by the Backend and requires no authentication of its own.

#### F-FACE-1 — Service Health
`GET /health`

**Behaviour**
- Returns **200** with `status: "healthy"` and a `service` field naming the service.

*Verified by:* `test_health_check`

---

#### F-FACE-2 — Endpoint Discovery
`GET /`

**Behaviour**
- Returns service identity, version, and an `endpoints` list that names the implemented routes — at minimum including `/face/enroll` or `/liveness/check`.

*Verified by:* `test_root_endpoint_lists_endpoints`

---

#### F-FACE-3 — Face Enrollment
`POST /face/enroll`

**Behaviour**
- Accepts `user_id`, `image` (base64 PNG/JPEG), `camera_consent`. Returns **200**/**201** with `enrollment_successful` (boolean), `face_template_hash` (non-empty string, SHA-256 hex by default), `quality_score` (float in [0, 1]), and a `details` object reporting `face_detected`, `face_detection_confidence`, `image_quality`.
- A clear frontal face image (e.g. the provided `sample_images/obama.jpg`) must enroll successfully with `quality_score` ≥ 0.5. Success criteria: face detection confidence ≥ 0.7 and quality ≥ 0.5.
- The returned hash is stored by the Backend in `users.face_embedding_hash`.

**Rejection behaviour**
- An image with no detectable face (a solid colour block, a landscape) must **not** enroll: either **400**, or **200** with `enrollment_successful: false`.
- `camera_consent: false` must **not** enroll: either **400**, or **200** with `enrollment_successful: false`.
- The endpoint must exist — **404** is a failure.

*Verified by:* `test_enroll_face_success`, `test_enroll_response_format`, `test_enroll_no_face_rejected`, `test_enroll_requires_consent`

---

#### F-FACE-4 — Face Verification (1:1)
`POST /face/verify`

**Behaviour**
- Accepts `image` and `reference_template_hash`. Returns **200** with `match_passed` (boolean), `match_score` (float in [0, 1]), `match_threshold`, `face_detected`, and `current_template_hash`.
- `match_passed` is true exactly when `match_score ≥ 0.70`.
- **Same person must match:** verifying with the same person's face against their enrolled hash yields `match_passed: true` and `match_score ≥ 0.7`.
- **Different person must not match:** a different individual's face yields `match_passed: false`, and their `current_template_hash` differs from the enrolled hash.
- An image with no detectable face yields `match_passed: false` (or `face_detected: false`), or **400** — never a crash.

**Implementation freedom.** Any of these satisfies the contract, provided raw images are never persisted:
1. ML embeddings (FaceNet/ArcFace) compared by cosine similarity;
2. Geometric comparison of facial landmarks;
3. Perceptual hashing (pHash/dHash) with Hamming distance;
4. **SimHash / locality-sensitive hashing** over embeddings — the privacy-preferred approach, since a plain SHA-256 of an embedding is unusable for matching (the avalanche effect destroys similarity) while SimHash preserves a measurable relationship between Hamming distance and cosine similarity without allowing reconstruction. A starting point for 128-d embeddings is 64 bits with a Hamming threshold around 10–15.

Threshold selection is a false-accept/false-reject trade-off: ~0.70 balances security against usability for attendance, and uncertain matches should be flagged for manual review rather than silently accepted.

*Verified by:* `test_face_verify_same_image`, `test_face_verify_different_person`, `test_face_verify_response_format`, `test_face_verify_no_face`

---

#### F-FACE-5 — Legacy Face Match
`POST /face/match`

**Behaviour**
- Backward-compatible alias for `/face/verify`, taking `image` and `reference_hash`, returning `match_passed`, `match_score`, `face_embedding_hash`. Same 0.7 threshold. Implementing either `/face/verify` or `/face/match` satisfies the verification tests, but implementing both is safest.

---

#### F-FACE-6 — Liveness Detection *(bonus)*
`POST /liveness/check`

**Behaviour**
- Accepts `challenge_response` (base64 image) and `challenge_type` (`passive` — recommended default, `blink`, or `head_turn`).
- Returns **200** with `liveness_passed`, `liveness_score`, `liveness_threshold`, `challenge_type`, `face_embedding_hash`, and a `details` object carrying `face_detection_confidence`, `face_mesh_complete`, `depth_detected`, `texture_analysis_score`, `threshold`.
- `liveness_passed` is true exactly when `liveness_score ≥ 0.60`.

**Anti-spoofing targets**
- Printed photos fail (no depth cues).
- Screen replays fail (flat z-coordinates, moiré artefacts).
- Synthetic / uniform-texture faces score below 0.5.

**Recommended scoring composition** (MediaPipe Face Mesh, 468 3D landmarks): depth detection 30 % (real faces show nose-tip z < −0.05), mesh completeness 25 %, texture analysis 25 %, colour distribution 20 %.

Active challenge types resist replay by demanding an unpredictable action: `blink` compares eye-aspect ratios across frames, `head_turn` tracks mesh landmark rotation.

---

#### F-FACE-7 — Risk Assessment
`POST /risk/assess`

**Behaviour**
- Accepts any subset of `liveness_score`, `face_match_score`, `device_signature`, `device_public_key`, `user_agent`, `ip_address`, `geolocation` `{latitude, longitude, accuracy}`.
- Returns **200** with `risk_score` (float in [0, 1]), `risk_level` (exactly one of `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `pass_threshold` (boolean), `risk_threshold`, `signal_breakdown` (per-signal contributions), and `recommendations` (array of strings).

**Signal weights**

| Signal | Weight | Conversion |
|--------|--------|-----------|
| Liveness | 25 % | risk = 1 − liveness_score |
| Face match | 25 % | risk = 1 − face_match_score |
| Device attestation | 20 % | signature validity |
| Network | 15 % | VPN / proxy / Tor detection |
| Geolocation | 15 % | accuracy and plausibility |

**Risk level mapping:** LOW < 0.3 ≤ MEDIUM < 0.5 ≤ HIGH < 0.7 ≤ CRITICAL.

**Required monotonic behaviour**
- Strong signals (liveness 0.95, face match 0.95, public IP, ordinary user agent, accurate geolocation) → `risk_score` < 0.5 and `pass_threshold: true`.
- Weak signals (liveness 0.2, face match 0.3, private IP such as `10.0.0.1`, user agent containing `vpn`) → `risk_score` ≥ 0.5 and `pass_threshold: false`.

**Network detection heuristics.** Private ranges (`10.`, `192.168.`, `172.16–19.`) indicate a tunnel with ~0.7 confidence; user-agent strings containing `vpn`, `proxy`, `tunnel`, or `tor` indicate one with ~0.8 confidence.

**Recommendations.** Any high-risk signal produces a plain-language remedy: low liveness → "Improve lighting and face visibility"; low face match → "Re-enroll face or improve image quality"; VPN detected → "Disable VPN for check-in"; poor geolocation → "Enable precise location services".

*Verified by:* `test_risk_assess_response_format`, `test_high_scores_produce_low_risk`, `test_low_scores_produce_high_risk`

---

#### F-FACE-8 — Device Attestation *(optional, untested)*
`POST /device/attest`

**Behaviour**
- Accepts `device_public_key`, `device_signature`, `challenge`, `device_info`; returns `attestation_passed`, `attestation_score`, `device_trusted`, `device_fingerprint`, `issues[]`.

---

#### F-FACE-9 — Face Service Privacy Guarantees

**Behaviour**
- Images are decoded, processed, and discarded **in memory**. No raw image is written to disk, to the database, to a cache, or to a log.
- No response body may contain a `data:image` URI or any fragment of the submitted image. This holds for enrollment, verification, and liveness responses alike.
- Only hashes cross the service boundary.

*Verified by:* `test_no_raw_image_in_response`, `test_face_embedding_hash_format`

---

### 3.11 Risk Signals (F-RISK)

#### F-RISK-1 — Signal Persistence

**Behaviour**
- Every risk indicator raised during a check-in is written as a `risk_signals` row carrying `signal_type`, `severity` (`low` | `medium` | `high` | `critical`), `confidence` (0–1), `weight`, `details` (JSON), and `detected_at`, linked to the check-in.

#### F-RISK-2 — Recognized Signal Taxonomy

| Group | Signal types |
|-------|-------------|
| Geo | `geo_out_of_bounds`, `impossible_travel`, `geo_accuracy_low` |
| Network | `vpn_detected`, `proxy_detected`, `tor_detected`, `suspicious_ip` |
| Device | `device_unknown`, `device_emulator`, `device_rooted`, `attestation_failed` |
| Behavioural | `rapid_succession`, `unusual_time`, `pattern_anomaly` |
| Liveness | `liveness_failed`, `liveness_low_confidence`, `deepfake_suspected`, `replay_suspected` |
| Face | `face_match_failed`, `face_match_low_confidence` |

#### F-RISK-3 — Signal Fusion and Exposure

**Behaviour**
- Signals combine into the check-in's `risk_score` by weight and confidence.
- The check-in response and review queue expose `risk_factors` as an array of `{type, severity, weight}` so an instructor can see *why* something was flagged, never as an opaque number alone.

#### F-RISK-4 — Configurable Thresholds

**Behaviour**
- Risk threshold resolution order: session override → course setting → system default (0.5), configurable through `RISK_SCORE_THRESHOLD`.
- Liveness threshold 0.6, face match threshold 0.7, geofence radius 100 m by default.

---

### 3.12 Statistics & Analytics (F-STATS)

#### F-STATS-1 — System Overview
`GET /api/v1/stats/overview`

**Behaviour**
- Instructor/admin. Returns **200** with, at minimum: `total_sessions`, `active_sessions`, `total_courses`, `total_students`, `today_checkins`, `flagged_pending`, `approval_rate`.
- All counts are non-negative; `approval_rate` is non-negative.
- Also supplies trend data — check-ins per day and attendance rate per day over a `days` window (default 7) — and may be filtered by `course_id`.

*Verified by:* `test_stats_overview`

---

#### F-STATS-2 — Session Statistics
`GET /api/v1/stats/sessions/{session_id}`

**Behaviour**
- Instructor/TA for the session's course. Returns **200** with, at minimum: `session_id`, `session_name`, `total_enrolled`, `checked_in_count`, `approved_count`, `flagged_count`, `attendance_rate`, `average_risk_score`.
- Additionally supplies a status breakdown, average distance, average check-in time, a low/medium/high risk distribution, and a check-in timeline bucketed by minute.

*Verified by:* `test_stats_session`

---

#### F-STATS-3 — Course Statistics
`GET /api/v1/stats/courses/{course_id}`

**Behaviour**
- Instructor for the course, or admin. Returns **200** with, at minimum: `course_id`, `course_code`, `total_enrolled`, `total_sessions`, `average_attendance_rate`, `flagged_checkins`.
- Additionally supplies per-session attendance, per-student attendance rates, and low-attendance alerts. Accepts `start_date` / `end_date`.

*Verified by:* `test_stats_course`

---

#### F-STATS-4 — Student Statistics
`GET /api/v1/stats/students/{student_id}`

**Behaviour**
- Instructor for the student's courses, or admin. Returns **200** with, at minimum: `student_id`, `student_name`, `total_enrolled_courses`, `total_sessions`, `attended_sessions`, `attendance_rate`, `recent_sessions`.

*Verified by:* `test_stats_student`

---

### 3.13 Data Export (F-EXPORT)

#### F-EXPORT-1 — Session Export
`GET /api/v1/export/session/{session_id}`

**Behaviour**
- Instructor for the session. Accepts `format` = `csv` (default) or `json`.
- JSON form returns **200** with `session_id`, a `summary` object containing at least `total_enrolled` and `attendance_rate`, and a `records` array.
- CSV form returns a downloadable UTF-8 file with a header row, correctly quoting values containing commas or quotes.
- Writes a `data_exported` audit entry.

*Verified by:* `test_export_session_attendance_json`

---

#### F-EXPORT-2 — Course Attendance Export
`GET /api/v1/export/attendance/{course_id}`

**Behaviour**
- Instructor for the course. Accepts `format` (`csv` | `json`), `start_date`, `end_date`.
- CSV columns: `student_id, student_name, student_email, session_date, session_name, status, checked_in_at, risk_score` — gradebook-ready.

---

### 3.14 Audit Logging (F-AUDIT)

#### F-AUDIT-1 — Immutable Audit Trail

**Behaviour**
- Every security-relevant event is appended to `audit_logs` with `user_id`, `action`, `resource_type`, `resource_id`, `ip_address`, `user_agent`, `device_id`, `details` (JSON), `success`, and `timestamp`.
- The table is **append-only**: it has no `updated_at` column, and no code path modifies or deletes a row once written. Audit logs are exempt from the 30-day retention policy and are retained indefinitely.

#### F-AUDIT-2 — Tracked Actions (18 types)

`login_success`, `login_failed`, `logout`, `user_created`, `user_updated`, `checkin_attempted`, `checkin_approved`, `checkin_flagged`, `checkin_rejected`, `checkin_appealed`, `checkin_reviewed`, `session_created`, `session_updated`, `session_deleted`, `enrollment_added`, `enrollment_removed`, `device_registered`, `face_enrolled` — plus `data_exported` and `security_violation` for compliance and security events.

#### F-AUDIT-3 — Audit Log Query
`GET /api/v1/audit/`

**Behaviour**
- **Admin only** — every other role receives **403**.
- Returns a paginated envelope `{items, total, limit, offset}`; `limit` defaults to 100, max 1000.
- Filters: `user_id`, `action`, `resource_type`, `resource_id`, `success`, `start_date`, `end_date`.
- Each entry carries a `timestamp` (or `created_at`).

*Verified by:* `test_audit_logs_with_filters`, `test_non_admin_cannot_access_audit_logs`, `test_audit_log_endpoint_exists`

---

#### F-AUDIT-4 — Audit Summary
`GET /api/v1/audit/summary`

**Behaviour**
- Admin only. Accepts `days` (default 7). Returns **200** with `period_days`, `total_logs`, and `by_action` — a per-action-type breakdown for the period.

*Verified by:* `test_audit_summary`

---

### 3.15 Privacy & Compliance (F-PRIVACY)

#### F-PRIVACY-1 — Consent Tracking

**Behaviour**
- `camera_consent` and `geolocation_consent` are stored per user as booleans, both defaulting to **false**, both exposed on `GET /users/me` and updatable via `PUT /users/me`.
- Camera consent is required before any face image is captured or processed; geolocation consent is required before GPS is captured.
- Both must be true before a full check-in can proceed. Withdrawal is honoured immediately.

*Verified by:* `test_camera_consent_required`, `test_geolocation_consent_required`, `test_consent_can_be_updated`, `test_enroll_requires_consent`

---

#### F-PRIVACY-2 — No Raw Biometric Storage

**Behaviour**
- No raw face image is ever persisted — not in the database, not on the filesystem, not in a cache, not in a log. Images exist only in process memory for the duration of a single request.
- Only a fixed-length hash (64 hex characters for SHA-256) is stored, in `users.face_embedding_hash` and `checkins.face_embedding_hash`.
- No BLOB or binary columns exist in the `users` or `checkins` tables.
- Storing embeddings directly is insufficient: tools such as Arc2Face and IdDecoder can reconstruct recognizable faces from raw embeddings, so the persisted form must be non-invertible.

*Verified by:* `test_no_raw_face_images_in_checkin_response`, `test_only_face_embedding_hash_stored`, `test_no_raw_image_in_response`, `test_face_embedding_hash_format`

---

#### F-PRIVACY-3 — Response Data Minimization

**Behaviour**
- A check-in response must not contain any of the fields `face_image`, `image_data`, `photo`, `face_data`, or `raw_image`.
- A user response must not contain `password` or `hashed_password`.
- No response may embed a `data:image` URI or a fragment of a submitted image.

*Verified by:* `test_no_raw_face_images_in_checkin_response`, `test_passwords_not_in_user_response`, `test_password_not_in_response`

---

#### F-PRIVACY-4 — Data Retention

**Behaviour**
- Check-in records carry `scheduled_deletion_at` set to 30 days after creation; user PII carries `scheduled_deletion_at` for deletion 30 days after a deletion request.
- A scheduled cleanup job removes records whose deletion time has passed.
- Audit logs are exempt and retained indefinitely.

*Verified by:* `test_user_has_scheduled_deletion_field`

---

#### F-PRIVACY-5 — GDPR-like Principles

**Behaviour**
- **Data minimization** — only data necessary for attendance verification is collected; location is stored with limited precision and used solely for the geofence decision.
- **Purpose limitation** — data collected for attendance verification is used for nothing else.
- **Explicit consent** — opt-in, never opt-out, with a stated reason before each permission request.
- **Right to deletion** — a user may request removal of their data, honoured through the retention mechanism.

---

### 3.16 Security Controls (F-SEC)

#### F-SEC-1 — Password Storage

**Behaviour**
- Bcrypt hashing with cost ≥ 10 (12 recommended). Plaintext passwords are never stored, logged, or returned.

#### F-SEC-2 — Rate Limiting (Redis-backed)

| Category | Limit | Window | Key |
|----------|-------|--------|-----|
| Login attempts | 60 | 1 hour | IP address |
| API requests | 1000 | 1 hour | User ID |
| Check-in attempts | 10 | 1 minute | User ID |
| Registration | 10 | 1 hour | IP address |

**Behaviour**
- Counters live in Redis under `rate_limit:{identifier}:{window}` keys with TTL equal to the window.
- Exceeding a limit returns **429** with a `detail` message and, where possible, a `Retry-After` header.
- Repeated failed logins must eventually be throttled rather than accepted indefinitely.

*Verified by:* `test_login_rate_limiting`

---

#### F-SEC-3 — SQL Injection Prevention

**Behaviour**
- All database access goes through an ORM with parameterized queries. Raw SQL is never constructed from user input.
- Injection payloads such as `1' OR '1'='1` supplied in query parameters are treated as inert data — the endpoint returns a normal **200**, or **400**/**422**, and never executes injected SQL.

*Verified by:* `test_sql_injection_prevented`

---

#### F-SEC-4 — XSS Prevention

**Behaviour**
- User-provided content is HTML-escaped or stripped before being echoed back. `Content-Type` headers are set correctly, and no user data is emitted as inline JavaScript.

*Verified by:* `test_xss_payload_sanitized`

---

#### F-SEC-5 — Input Validation

**Behaviour**
- Email addresses validated to RFC 5322; IDs validated as UUIDs; latitude/longitude range-checked; timestamps validated as ISO 8601; enum fields strictly validated against their allowed values.
- Validation failures return **422** listing every offending field.

*Verified by:* `test_invalid_email_rejected`, `test_weak_password_rejected`, `test_422_validation_error_format`

---

#### F-SEC-6 — CORS Policy

**Behaviour**
- Allowed origins in development: `http://localhost:3000` (frontend) and `http://localhost:8501` (dashboard), configurable via `CORS_ORIGINS`.
- Exact-domain matching only — no wildcard origins in production configuration. Misconfigured CORS blocks the frontend entirely and is a known failure mode.

#### F-SEC-7 — Secret Management

**Behaviour**
- `SECRET_KEY` (32+ characters), `DATABASE_URL`, and `REDIS_URL` come from environment variables and are never committed to source.
- Optional overrides: `ACCESS_TOKEN_EXPIRE_MINUTES` (60), `REFRESH_TOKEN_EXPIRE_DAYS` (7), `BCRYPT_ROUNDS` (10), `RISK_SCORE_THRESHOLD` (0.5).

#### F-SEC-8 — Error Message Hygiene

**Behaviour**
- Error responses use a consistent `{"detail": "..."}` shape and never leak internal details such as SQL text, stack traces, or file paths. Full diagnostics are logged server-side with a correlation ID.

*Verified by:* `test_401_error_format`, `test_400_error_format`

---

### 3.17 Administrative Endpoints (F-ADMIN)

These endpoints let the automated test suite and operators manipulate state without direct database access. All are admin-only.

#### F-ADMIN-1 — Deactivate User
`PATCH /api/v1/admin/users/{user_id}/deactivate`

**Behaviour**
- Sets `is_active: false`; returns **200**/**204** with `id`, `email`, `is_active: false`, `message`. The user can no longer log in (**403** on attempt).

*Verified by:* `deactivated_student` fixture, `test_inactive_user_cannot_login`

---

#### F-ADMIN-2 — Activate User
`PATCH /api/v1/admin/users/{user_id}/activate`

**Behaviour**
- Sets `is_active: true`; returns **200** with the user summary and a confirmation message.

---

#### F-ADMIN-3 — Bulk User Creation
`POST /api/v1/admin/users/bulk`

**Behaviour**
- Accepts `{users: [{email, password, full_name, role}, ...]}`; returns **201** with `created`, `failed`, `users[]` (each with `id`, `email`, `full_name`, `role`), and `errors[]`.
- Must remain performant enough to provision the participants of a 100-concurrent-user stress scenario.

*Verified by:* `create_bulk_users` fixture

---

#### F-ADMIN-4 — Force Session Status
`PATCH /api/v1/admin/sessions/{session_id}/status`

**Behaviour**
- Accepts `{status}` (any of `scheduled` | `active` | `closed` | `cancelled`) and applies it directly, bypassing normal transition rules so closed/cancelled edge cases can be exercised.
- Returns **200** with `id`, `name`, the new `status`, and a message naming the old and new status.
- **This is the endpoint that makes check-in testable at all** — a session must be `active` before any check-in succeeds.

*Verified by:* `test_session` fixture, `test_complete_student_checkin_flow`

---

#### F-ADMIN-5 — Admin Enrollment
`POST /api/v1/admin/enrollments/`

**Behaviour**
- Accepts `{student_id, course_id}` and creates the enrollment while bypassing the instructor-ownership check. Returns **201** with `id`, `student_id`, `course_id`, `is_active`, `enrolled_at`.

*Verified by:* `test_enrollment` fixture, `test_complete_student_checkin_flow`

---

### 3.18 Student Frontend PWA (F-FE) — Module 1, port 3000

#### F-FE-1 — Progressive Web App Shell

**Behaviour**
- Ships a service worker and a web app manifest, making the app installable to a mobile home screen.
- Caching strategy: static assets and the app shell are cached; **authentication responses and check-in submissions are never cached** — a check-in must be real-time.
- Structured offline data uses IndexedDB.

#### F-FE-2 — Authentication UI

**Behaviour**
- Registration and login forms calling `POST /auth/register` and `POST /auth/login`, with clear error surfaces for duplicate email, weak password, wrong credentials, and disabled account.
- Access tokens are held in memory or `sessionStorage`; refresh tokens in an HttpOnly cookie where possible. Tokens never appear in URLs or logs and are cleared on logout.
- A **401** triggers a transparent refresh-and-retry; a second failure returns the user to login.

#### F-FE-3 — Camera Capture (WebRTC)

**Behaviour**
- Uses `navigator.mediaDevices.getUserMedia()` with `facingMode: 'user'` and an explicit resolution constraint, attaches the stream to a `<video>` element, draws a frame to `<canvas>`, and exports base64 JPEG with the `data:` prefix stripped before submission.
- Every track is stopped (`track.stop()`) once capture completes — the camera indicator must not stay lit.

#### F-FE-4 — Liveness Challenge UI

**Behaviour**
- Presents the challenge (blink, head turn) with clear on-screen instructions and captures the response for submission as `liveness_challenge_response`.

#### F-FE-5 — Geolocation Capture

**Behaviour**
- Uses `navigator.geolocation.getCurrentPosition()` to obtain latitude, longitude, and accuracy, submitted with the check-in.

#### F-FE-6 — Consent & Permission Handling

**Behaviour**
- Checks `navigator.permissions.query()` before requesting, explains *why* a permission is needed before prompting, requests permissions one at a time rather than all at once, and degrades gracefully with a fallback UI when denied. Dark patterns that trick users into granting permission are prohibited.
- Consent decisions are recorded server-side through `PUT /users/me`.

#### F-FE-7 — Device Fingerprinting

**Behaviour**
- Generates a stable device fingerprint, registers it via `POST /devices/register`, and includes it as `device_fingerprint` on every check-in.

#### F-FE-8 — Check-In Workflow

**Behaviour**
- The flow is: select active session → capture camera/liveness → capture location → submit → display outcome.
- The result screen shows the returned `status`, `risk_score`, and, when flagged or rejected, an explanation and the option to appeal.

#### F-FE-9 — Mobile Browser Support

**Behaviour**
- The app must work in mobile browsers; camera and geolocation APIs require a secure context, satisfied by `localhost` in this deployment.

#### F-FE-10 — Error and Rate-Limit Handling

**Behaviour**
- Handles **429** by showing a wait message driven by `Retry-After`, and surfaces network failures without losing entered state.

---

### 3.19 Instructor Dashboard (F-DASH) — Module 4, port 8501

#### F-DASH-1 — Instructor Login

**Behaviour**
- Authenticates against the same `POST /auth/login` endpoint and stores the JWT for subsequent calls, holding all API traffic to the same authorization rules as any other client.

#### F-DASH-2 — Session Management Interface

**Behaviour**
- Create, activate, and close sessions through the sessions API, with prominent activation controls — an un-activated session silently accepts no check-ins.

#### F-DASH-3 — Live Attendance Monitoring

**Behaviour**
- Displays check-ins for a selected session with student identity, timestamp, status, distance from venue, and risk score.

#### F-DASH-4 — Flagged Review Workflow

**Behaviour**
- Presents the flagged/appealed queue with each check-in's risk factors and appeal text, and offers approve/reject actions that call the review endpoint with notes.

#### F-DASH-5 — Analytics and Charts

**Behaviour**
- Renders attendance rates, risk distribution, and check-in timelines. Chart type follows the data: line for trends, bar for category comparison, table for precise values. Y-axes start at zero, colour carries meaning (red = bad, green = good), everything is labelled, and tables scroll horizontally on mobile.

#### F-DASH-6 — Information Hierarchy

**Behaviour**
- Highest-value information first: today's sessions, check-in rate, and items needing action, with progressive disclosure from summary to detail. Instructors get actionable items, not raw technical metrics.

#### F-DASH-7 — Export to Gradebook

**Behaviour**
- Downloads attendance as CSV or JSON via the export endpoints, with headers, UTF-8 encoding, and proper escaping of commas and quotes.

#### F-DASH-8 — Role-Scoped Views

**Behaviour**
- Students see only their own history; TAs see sessions for assisted courses; instructors see full course analytics; admins see system-wide data. UI hiding is a convenience only — the backend enforces every boundary.

#### F-DASH-9 — Real-Time Updates

**Behaviour**
- Polling on an interval (~30 s) is sufficient and preferred for simplicity; WebSockets or SSE are optional upgrades for sub-second refresh.

#### F-DASH-10 — Audit Log Explorer

**Behaviour**
- For admin users, provides a filterable view of the audit trail over the audit endpoints.

---

### 3.20 Observability & Operations (F-OPS)

#### F-OPS-1 — Health Endpoints

**Behaviour**
- Backend `GET /health` returns **200** when healthy, or **503** when a dependency (database, Redis) is down; the body contains an `api` or `status` field.
- Face service `GET /health` returns **200** with `status: "healthy"` and a `service` field.
- Health checks respond in **under 0.5 s** — they must not perform expensive work.
- Every service (frontend and dashboard included) exposes a reachable health surface.

*Verified by:* `test_health_endpoint_format`, `test_health_check_latency`, `test_health_check`

---

#### F-OPS-2 — Prometheus Metrics

**Behaviour**
- Backend (`:8000/metrics`) and Face service (`:8001/metrics`) expose Prometheus-format metrics, scraped every 15 s.
- Metrics cover technical health (request duration histograms enabling `histogram_quantile(0.95, ...)`, error rates) and business outcomes (`checkin_attempts_total`, `checkin_success_total`, risk score distribution, flagged-versus-approved ratio).

#### F-OPS-3 — Distributed Tracing

**Behaviour**
- Backend and Face service export OpenTelemetry traces to the collector at `OTEL_EXPORTER_OTLP_ENDPOINT`, making a check-in traceable across the service boundary.

#### F-OPS-4 — Grafana Dashboards

**Behaviour**
- Grafana (`:3001`, admin/admin) is provisioned with the Prometheus datasource and dashboards for latency, error rate, check-in throughput, and risk distribution.

#### F-OPS-5 — Alerting Signals

**Behaviour**
- A sharply elevated flagged rate indicates a systemic problem; a spike in failed logins indicates a possible attack. Both are visible in the metrics stack.

#### F-OPS-6 — Docker Deployment

**Behaviour**
- The whole system starts with `docker-compose up -d`: PostgreSQL (5434→5432), Redis (6380→6379), backend (8000), face service (8001), frontend (3000), dashboard (8501), Prometheus (9090), Grafana (3001), OTel collector (4317/4318).
- Application services wait on healthy database and Redis health checks. Postgres, Prometheus, and Grafana data live in named volumes.
- The final deliverable is a working, Docker-deployable system.

#### F-OPS-7 — Database Migrations

**Behaviour**
- Schema changes are managed by versioned migrations (Alembic) supporting `upgrade head` and `downgrade -1`.

---

### 3.21 Performance & Scalability (F-PERF)

#### F-PERF-1 — Latency Budgets

| Operation | Budget |
|-----------|--------|
| `POST /auth/login` | < 2.0 s |
| `POST /checkins/` | < 2.0 s |
| `GET /courses/` | < 1.0 s |
| `GET /checkins/session/{id}` | < 1.0 s |
| `GET /health` | < 0.5 s |

Note that the login budget must hold *despite* bcrypt's deliberate ~100 ms cost.

*Verified by:* `test_auth_endpoint_latency`, `test_checkin_endpoint_latency`, `test_list_endpoint_latency`, `test_health_check_latency`, `test_no_n_plus_one_queries`

---

#### F-PERF-2 — Concurrency

**Behaviour**
- 10 simultaneous logins for the same account: ≥ 80 % succeed.
- 10 simultaneous register-then-login flows for distinct users: ≥ 80 % succeed.
- 20 simultaneous check-ins from distinct students to one session: ≥ 90 % succeed.
- The hidden stress target is **100 concurrent users**.

*Verified by:* `test_concurrent_logins` (both variants), `test_concurrent_checkins`

---

#### F-PERF-3 — Query Efficiency

**Behaviour**
- List endpoints that join related entities use eager loading — no N+1 query patterns. Listing a session's check-ins with its student and device joins stays under 1 s.
- Indexes cover every foreign key and every frequently filtered column (see §4).
- Connection pooling is configured (pool size 10, max overflow 20).

*Verified by:* `test_no_n_plus_one_queries`

---

#### F-PERF-4 — Pagination

**Behaviour**
- Every list endpoint accepts `limit` and `offset`, and paginated endpoints return the uniform `{items, total, limit, offset}` envelope. Default page size is 50 (100 for audit logs), capped at 100 (1000 for audit logs).

*Verified by:* `test_pagination_support`, `test_list_sessions_with_filters`, `test_list_all_checkins`, `test_list_users_admin`

---

### 3.22 API Conventions (F-API)

#### F-API-1 — REST Conventions

**Behaviour**
- Resources are plural nouns (`/users`, not `/getUsers`), hierarchical where nested, with filtering through query parameters.
- Methods: `GET` read, `POST` create, `PUT` full update, `PATCH` partial update, `DELETE` remove.
- All endpoints live under the `/api/v1` prefix (except `/health`).

#### F-API-2 — Status Code Discipline

| Code | Meaning in SAIV |
|------|-----------------|
| 200 | Successful read or update |
| 201 | Resource created (register, check-in, session, course, enrollment, device) |
| 204 | Successful delete, no body |
| 400 | Business-rule violation (duplicate email, duplicate check-in, session inactive, consent missing) |
| 401 | Missing, malformed, or expired credentials |
| 403 | Authenticated but insufficient role, or disabled account |
| 404 | Resource does not exist |
| 422 | Schema/validation failure (short password, malformed email) |
| 429 | Rate limit exceeded |
| 500 | Internal error — generic message only |
| 503 | Downstream dependency unavailable (face service, database) |

#### F-API-3 — Response Shape Consistency

**Behaviour**
- Two shapes exist and their use is not interchangeable. **Bare arrays**: `/sessions/active`, `/checkins/my-checkins`, `/checkins/session/{id}`, `/devices/my-devices`, `/enrollments/my-enrollments`. **Paginated envelopes**: `/sessions/`, `/checkins/`, `/checkins/flagged`, `/users/`, `/devices/`, `/audit/`.
- Errors always use `{"detail": ...}`.

#### F-API-4 — Implementation Agnosticism

**Behaviour**
- Conformance is defined entirely by HTTP behaviour. Any language or framework capable of serving HTTP satisfies the contract; internal design is unconstrained.

---

## 4. Data Requirements

Eight tables. Primary keys are `VARCHAR(36)` UUIDs throughout.

| Table | Purpose | Key constraints and indexes |
|-------|---------|------------------------------|
| `users` | Accounts, roles, consent flags, face hash, retention timestamp | `email` unique; indexed on `email`, `role`, `is_active`. Holds `face_embedding_hash` — never a raw embedding |
| `courses` | Course metadata, venue, geofence radius, risk threshold, security toggles | `code` unique; indexed on `code`, `semester`, `is_active` |
| `enrollments` | Student ↔ course membership | Indexed on `student_id`, `course_id`; **unique** `(student_id, course_id)` |
| `sessions` | Class meetings, check-in windows, per-session security overrides, QR secret | Indexed on `course_id`, `status`, `scheduled_start`, `(checkin_opens_at, checkin_closes_at)` |
| `devices` | Bound devices, public keys, attestation and trust state | `device_fingerprint` unique; indexed on `user_id`, `device_fingerprint`, `is_active`, `is_trusted` |
| `checkins` | Attendance records with location, liveness, face match, risk, review, appeal | Indexed on `session_id`, `student_id`, `status`, `checked_in_at`, `risk_score`; **unique** `(session_id, student_id)` |
| `risk_signals` | Individual risk indicators per check-in | Indexed on `checkin_id`, `signal_type`, `severity`, `detected_at` |
| `audit_logs` | Immutable event trail | Indexed on `user_id`, `action`, `timestamp`, `(resource_type, resource_id)`, `ip_address`. **No `updated_at` column** |

**Enumerations.** `users.role`: student/instructor/ta/admin · `sessions.status`: scheduled/active/closed/cancelled · `sessions.session_type`: lecture/tutorial/lab/exam · `checkins.status`: pending/approved/flagged/rejected/appealed · `risk_signals.severity`: low/medium/high/critical · `devices.trust_score`: low/medium/high · `devices.platform`: ios/android/web/desktop.

**Schema-level privacy invariants**
1. Only SHA-256-length hashes for face data — never raw images or raw embeddings.
2. No BLOB columns in `users` or `checkins`.
3. `scheduled_deletion_at` present on `users` and `checkins` for the 30-day policy.
4. All sensitive actions logged.
5. Consent flags present and default false.

---

## 5. Acceptance Criteria

The system is validated exclusively through black-box HTTP tests against running services — no source inspection, so any implementation language qualifies. Tests create their own data through the API, which is why the admin endpoints in §3.17 are mandatory.

### 5.1 Public Test Suite — 90 points

| Test file | Points | Coverage |
|-----------|-------:|----------|
| `test_api_functional.py` | 26 | Authentication (5), user management (5), courses (4), sessions (4), check-ins (8), devices (2) |
| `test_face_recognition.py` | 15 | Service health (2), enrollment (4), matching (4), privacy (2), risk assessment (3) |
| `test_security_basic.py` | 12 | Auth security (4), authorization (4), input validation (3), rate limiting (1) |
| `test_observability.py` | 12 | Stats (4), session CRUD (3), enrollments (2), check-in filtering (2), export (1) |
| `test_privacy_basic.py` | 8 | Consent (3), data minimization (3), retention (2) |
| `test_frontend_dashboard.py` | 8 | Frontend auth/check-in contracts, dashboard session/metrics contracts |
| `test_performance.py` | 5 | Latency (3), concurrency (1), query optimization (1) |
| `test_integration.py` | 4 | End-to-end check-in flow (2), latency and concurrency (2) |

### 5.2 Hidden Test Suite — 40 points

| Category | Points | Coverage |
|----------|-------:|----------|
| Advanced Security | 12 | GPS spoofing detection, replay attack prevention, VPN/network security |
| Privacy Auditing | 8 | Direct database inspection for raw images, encryption validation |
| Face Recognition Advanced | 10 | Anti-spoofing against real print and screen attack images |
| Liveness Bonus | 3 | Advanced liveness features |
| Stress Testing | 7 | 100 concurrent users, edge cases |

### 5.3 The End-to-End Acceptance Scenario

The integration test defines the canonical happy path; every step must succeed in order:

1. Student registers → **201**
2. Student logs in → **200** with tokens
3. Student grants camera and geolocation consent via `PUT /users/me` → **200**
4. Admin enrolls the student in a course → **200/201**
5. Instructor creates a session with an open check-in window → **200/201**
6. Admin activates the session → **200**
7. Student lists active sessions → **200**
8. Student submits a check-in → **201** with status in {pending, approved, flagged}
9. Student retrieves their check-in history → **200**, non-empty

*Verified by:* `test_complete_student_checkin_flow`

### 5.4 Known Failure Modes to Design Against

- Storing raw face images — an automatic privacy failure.
- Storing plaintext passwords.
- Omitting the admin endpoints, which blocks the entire test suite from setting up data.
- Forgetting session activation — check-ins silently fail against a `scheduled` session.
- N+1 query patterns that blow the latency budget.
- Missing geofence validation, making remote check-in trivial.
- Misconfigured CORS, which severs the frontend from the backend.
- Poor error handling that crashes services under concurrent load.
