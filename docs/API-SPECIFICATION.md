# SAIV API Specification

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication

All protected endpoints require JWT bearer token:
```
Authorization: Bearer <access_token>
```

### Role-Based Access Control

| Role | Description | Permissions |
|------|-------------|-------------|
| `student` | Students checking into classes | Check-in, view own records, manage own devices |
| `ta` | Teaching assistants | View session check-ins and review flagged check-ins for assigned courses |
| `instructor` | Course instructors | Manage assigned courses and sessions, review check-ins, view course analytics, manage enrollments |
| `admin` | System administrators | System-wide management access; student-only endpoints remain restricted to students |

Endpoint-specific role restrictions take precedence; roles do not automatically inherit student-only permissions.

---

## Endpoints

### Authentication

#### POST /auth/register
Register a new user.

**Request:**
```json
{
  "email": "student@example.com",
  "password": "securepass123",  // min 8 chars
  "full_name": "John Doe",
  "role": "student"  // student|instructor|ta|admin
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "email": "student@example.com",
  "full_name": "John Doe",
  "role": "student",
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Email already registered, password too weak
- `422 Validation Error`: Invalid email format, missing fields

#### POST /auth/login
Login to receive JWT tokens.

**Request:**
```json
{
  "email": "student@example.com",
  "password": "securepass123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",  // Expires in 1 hour
  "refresh_token": "eyJ...",  // Expires in 7 days
  "token_type": "bearer",
  "user": { /* UserResponse */ }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials
- `403 Forbidden`: Account disabled

#### POST /auth/refresh
Refresh access token.

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### Users

#### GET /users/me
Get current user information. **Requires auth.**

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "student@example.com",
  "full_name": "John Doe",
  "role": "student",
  "camera_consent": true,
  "geolocation_consent": true,
  "face_enrolled": false,
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### PUT /users/me
Update current user profile. **Requires auth.**

**Request:**
```json
{
  "full_name": "John Smith",
  "camera_consent": true,
  "geolocation_consent": false
}
```

**Response:** `200 OK` - Returns updated user object

#### GET /users/
List all users with pagination and filters. **Requires auth (admin only).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role` | string | - | Filter by role (student\|instructor\|ta\|admin) |
| `is_active` | boolean | - | Filter by active status |
| `search` | string | - | Search by name or email |
| `limit` | int | 50 | Results per page (max 100) |
| `offset` | int | 0 | Pagination offset |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "student@example.com",
      "full_name": "John Doe",
      "role": "student",
      "is_active": true,
      "face_enrolled": true,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

#### GET /users/{user_id}
Get specific user details. **Requires auth (admin, or instructor for enrolled students).**

**Response:** `200 OK` - Returns user object

#### PATCH /users/{user_id}
Update user details. **Requires auth (admin only).**

**Request:**
```json
{
  "role": "ta",
  "is_active": false
}
```

**Response:** `200 OK` - Returns updated user object

#### POST /users/me/face/enroll
Enroll the current user's face for identity verification. **Requires auth.**

This endpoint calls the face recognition service and updates the user's `face_enrolled` status.

**Prerequisites:**
- User must have `camera_consent: true`

**Request:**
```json
{
  "image": "base64_encoded_face_image"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | string | Yes | Base64-encoded face image (PNG/JPEG), without data URL prefix |

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Face enrolled successfully",
  "face_enrolled": true,
  "quality_score": 0.85
}
```

**Error Responses:**
- `400 Bad Request`: Camera consent not given, or no face detected
- `503 Service Unavailable`: Face recognition service unavailable

**Example Usage:**
```javascript
// Capture photo from video element
const canvas = document.createElement('canvas')
canvas.width = video.videoWidth
canvas.height = video.videoHeight
canvas.getContext('2d').drawImage(video, 0, 0)
const dataUrl = canvas.toDataURL('image/jpeg')

// Remove data URL prefix
const base64Image = dataUrl.replace(/^data:image\/\w+;base64,/, '')

// Call API
const response = await fetch('/api/v1/users/me/face/enroll', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ image: base64Image })
})
```

---

### Courses

#### GET /courses/
List courses with optional filters. **Requires auth.**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `is_active` | boolean | true | Filter by active status |
| `semester` | string | - | Filter by semester |
| `instructor_id` | uuid | - | Filter by instructor (admin only) |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "uuid",
      "code": "CS6101",
      "name": "Advanced Topics in CS",
      "semester": "AY2024-25 Sem 1",
      "instructor_id": "uuid",
      "instructor_name": "Dr. Smith",
      "venue_name": "LT1",
      "venue_latitude": 1.3483,
      "venue_longitude": 103.6831,
      "geofence_radius_meters": 100.0,
      "risk_threshold": 0.5,
      "is_active": true,
      "created_at": "2024-01-10T10:00:00Z"
    }
  ],
  "total": 25,
  "limit": 50,
  "offset": 0
}
```

#### GET /courses/{course_id}
Get course details. **Requires auth.**

**Response:** `200 OK` - Returns full course object including:
- Course metadata
- Default venue coordinates
- Security settings (risk threshold, geofence)

#### POST /courses/
Create a new course. **Requires auth (admin only).**

**Request:**
```json
{
  "code": "CS6101",
  "name": "Advanced Topics in CS",
  "semester": "AY2024-25 Sem 1",
  "instructor_id": "uuid",
  "venue_name": "LT1",
  "venue_latitude": 1.3483,
  "venue_longitude": 103.6831,
  "geofence_radius_meters": 100.0,
  "risk_threshold": 0.5
}
```

**Response:** `201 Created` - Returns created course object

#### PUT /courses/{course_id}
Update a course. **Requires auth (admin or course instructor).**

**Request:** (partial update supported)
```json
{
  "name": "Updated Course Name",
  "venue_name": "LT2",
  "risk_threshold": 0.6
}
```

**Response:** `200 OK` - Returns updated course object

#### DELETE /courses/{course_id}
Soft-delete a course (sets is_active=false). **Requires auth (admin only).**

**Response:** `204 No Content`

---

### Course TA assignments

All endpoints below require **admin authentication** and use the `/api/v1` base.

| Method | Endpoint | Behavior |
|--------|----------|----------|
| GET | `/admin/courses/{course_id}/tas` | List assignments: `200`, `{course_id, items, total}` |
| POST | `/admin/courses/{course_id}/tas` | Assign an active TA using exactly one of `{"user_id":"uuid"}` or `{"email":"ta@example.edu"}`; returns assignment with `201` |
| DELETE | `/admin/courses/{course_id}/tas/{user_id}` | Remove assignment; returns `204` |

Assignment fields: `id`, `course_id`, `user_id`, `email`, `full_name`, `is_active`, `assigned_at`.
Assignments grant TA access to the course's sessions/check-ins and enrollment roster;
multiple TAs per course and multiple courses per TA are supported. Session-level
TA assignments are not implemented. Errors: `400` for inactive/non-TA users,
`404` for missing resources, `409` for duplicate assignment, `422` for invalid input.
Assignment/removal is audited as `user_updated` with resource type `course_assistant`.

### Sessions

Sessions represent class meetings where students check in.

#### GET /sessions/
List all sessions with filters. **Requires auth (TA/instructor/admin).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status (scheduled\|active\|closed\|cancelled) |
| `course_id` | uuid | - | Filter by course |
| `instructor_id` | uuid | - | Filter by instructor |
| `start_date` | ISO8601 | - | Sessions starting after this date |
| `end_date` | ISO8601 | - | Sessions starting before this date |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "uuid",
      "course_id": "uuid",
      "course_code": "CS6101",
      "course_name": "Advanced Topics in CS",
      "instructor_id": "uuid",
      "name": "Lecture 5: Neural Networks",
      "session_type": "lecture",
      "status": "active",
      "scheduled_start": "2024-01-15T14:00:00Z",
      "scheduled_end": "2024-01-15T16:00:00Z",
      "checkin_opens_at": "2024-01-15T13:45:00Z",
      "checkin_closes_at": "2024-01-15T14:30:00Z",
      "venue_name": "NTU LT1",
      "total_enrolled": 50,
      "checked_in_count": 45
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### GET /sessions/active
List all currently active check-in sessions. **Public endpoint (no auth required).**

This endpoint returns sessions where check-in is currently open, useful for students to see available sessions.

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "course_id": "uuid",
    "course_code": "CS6101",
    "name": "Lecture 5: Neural Networks",
    "status": "active",
    "scheduled_start": "2024-01-15T14:00:00Z",
    "scheduled_end": "2024-01-15T16:00:00Z",
    "checkin_opens_at": "2024-01-15T13:45:00Z",
    "checkin_closes_at": "2024-01-15T14:30:00Z",
    "venue_name": "NTU LT1"
  }
]
```

#### GET /sessions/my-sessions
List sessions for courses the current user is enrolled in (students) or teaches (instructors). **Requires auth.**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status |
| `upcoming` | boolean | false | Only show future sessions |
| `course_id` | uuid | - | Student: one of the caller's authorised courses; staff: filter by course |
| `start_date` | datetime | - | Return sessions whose scheduled interval overlaps this instant |
| `end_date` | datetime | - | Return sessions whose scheduled interval overlaps this instant |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Number of matching sessions to skip |

**Response:** `200 OK` - Returns a list of sessions relevant to the user. The response remains an array; pagination is applied with `limit` and `offset`.

For students, identity is derived from the JWT. Sessions are restricted to the
student's authorised course enrollments, including historical enrollment
eligibility at `scheduled_start` using the existing enrollment audit policy.
When `start_date` and/or `end_date` is supplied, sessions overlap the visible
range using `scheduled_start < end_date AND scheduled_end > start_date`.
Student session results include sessions without check-ins. Attendance outcomes
are obtained separately from `GET /checkins/my-checkins` and matched by
`session_id`.

#### GET /sessions/{session_id}
Get session details. **Requires auth.** Students may access only sessions for
which their enrollment was eligible at `scheduled_start`; instructors may access
sessions they own or manage.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "course_id": "uuid",
  "instructor_id": "uuid",
  "name": "Lecture 5: Neural Networks",
  "session_type": "lecture",
  "status": "active",
  "scheduled_start": "2024-01-15T14:00:00Z",
  "scheduled_end": "2024-01-15T16:00:00Z",
  "checkin_opens_at": "2024-01-15T13:45:00Z",
  "checkin_closes_at": "2024-01-15T14:30:00Z",
  "venue_latitude": 1.3483,
  "venue_longitude": 103.6831,
  "venue_name": "NTU LT1",
  "geofence_radius_meters": 100.0,
  "require_liveness_check": true,
  "require_face_match": false,
  "risk_threshold": 0.5,
  "qr_code_enabled": false,
  "created_at": "2024-01-14T10:00:00Z"
}
```

#### POST /sessions/
Create a new session. **Requires auth (instructor or admin).**

**Request:**
```json
{
  "course_id": "uuid",
  "session_name": "Lecture 5: Neural Networks",
  "session_type": "lecture",  // lecture|tutorial|lab|exam
  "scheduled_start": "2024-01-15T14:00:00Z",
  "scheduled_end": "2024-01-15T16:00:00Z",
  "checkin_opens_at": "2024-01-15T13:45:00Z",  // Optional, defaults to 15min before start
  "checkin_closes_at": "2024-01-15T14:30:00Z", // Optional, defaults to 30min after start
  "venue_latitude": 1.3483,  // Optional, uses course default
  "venue_longitude": 103.6831,
  "venue_name": "NTU LT1",
  "geofence_radius_meters": 100.0,
  "require_liveness_check": true,
  "require_face_match": false,
  "risk_threshold": 0.5
}
```

**Response:** `201 Created` - Returns created session object

**Validation:**
- An instructor can create sessions only for a course they teach; an admin can create a session for any course
- `scheduled_start` must be in the future
- `scheduled_end` must be after `scheduled_start`
- `checkin_closes_at` must be after `checkin_opens_at`

#### PATCH /sessions/{session_id}
Update a session. **Requires auth (admin, or session-owning instructor still assigned to the course).**

**Request:** (partial update - any subset of fields)
```json
{
  "course_id": "uuid",
  "status": "closed",
  "name": "Updated Session Name",
  "checkin_closes_at": "2024-01-15T14:45:00Z"
}
```

**Response:** `200 OK` - Returns updated session object

Instructors may change `course_id` only to a course they teach, and only while the session
is scheduled and has no check-ins. `total_enrolled` / expected attendance is derived from
the course's active enrollments and is not an editable session field.

Timing fields can be changed only while Scheduled; otherwise PATCH returns 409.
The Sessions calendar reuses GET/POST/PATCH/DELETE sessions: 30-minute move slots,
duration and check-in windows preserved on moves, confirmation before saving,
and Scheduled/Active sessions only. Closed history remains in List/Check-ins.

Sessions automatically become `active` at `scheduled_start` and `closed` at
`scheduled_end`. The backend reconciles persisted schedules at startup, every
second, and before session mutations, check-ins and motion challenges.
Session-list and detail reads use read-only connections and do not run scheduler
updates; they display the last persisted status. Missed transitions after downtime are applied in order. Cancelled
and manually closed sessions stay terminal. Automatic transitions append
`session_updated` audit entries and use scheduled times for actual start/end.
Manual status endpoints remain available for compatibility and early closing.
Custom check-in windows remain independent; a closed session never accepts
check-ins. Dashboard-created sessions explicitly use the entire scheduled
interval as their check-in window and accept a duration in minutes.

**Status Transitions:**
- `scheduled` → `active`: Opens check-in window
- `active` → `closed`: Closes check-in, finalizes attendance
- Any status → `cancelled`: Cancels session

#### DELETE /sessions/{session_id}
Permanently delete a session. **Requires auth (owning instructor or admin).**

Only sessions with status `scheduled` can be deleted. Active or closed sessions should be cancelled instead.

Sessions with check-ins cannot be deleted. Related motion policies/challenges are removed,
and a `session_deleted` audit entry is retained in the same transaction.

**Error Responses:**
- `403 Forbidden`: Not an instructor/admin, or instructor does not own the session
- `404 Not Found`: Session not found
- `400 Bad Request`: Session is not scheduled
- `409 Conflict`: Session has check-ins

**Response:** `204 No Content`

---

#### GET /sessions/{session_id}/attendance (instructor roster)

Requires JWT authentication with instructor, TA, or admin role. Instructors
must own the course/session, or the course must have no assigned instructor,
matching check-in details/review and session export. Unrelated instructors
receive 403; missing sessions receive 404. TAs must have an explicit course
assignment through the course TA assignment endpoints; unassigned TAs receive 403.

Returns a complete, unpaginated session roster for local search/filter/pagination:
`{session_id, course_id, session_status, expected, items, summary, policy}`.
Each item is `{student_id, student_name, student_email, checkin_id, checked_in_at,
attendance, status, risk_score}`; risk_score uses the 0–1 scale. Missing check-ins have null checkin_id/time/status/risk_score.
Attendance is `present` or `absent`; verification
retains the five documented statuses. Times have an explicit UTC `Z` suffix.
Summary contains counts for both attendance categories, `attendance_rate`
as a fraction in [0,1], and `verification` counts for all five statuses.
These totals are independent of UI filters and pagination.

Timing policy for this tab: Present requires a check-in at or after scheduled_start
and strictly before closure (the earlier of scheduled_end and recorded actual_end).
Absent means no qualifying check-in yet, including while the session is active.
Stored early/out-of-window records remain visible with their verification status,
but do not count as Present. Verification does not determine presence: pending,
rejected, flagged, appealed and approved all count when within this interval.
Review changes verification only. The instructor Check-ins selector lists only
Active and Closed sessions; Scheduled and Cancelled sessions are excluded.
Lifecycle includes schedule-based transitions between background scheduler ticks,
preserving explicit cancellation/closure. Policy includes `present_from`, `present_before`,
`all_verification_statuses_count`, and `roster_basis`.

The expected roster uses enrollment at scheduled_start (at current time for
future sessions), reconstructed from immutable enrollment_added/removed events
where available and the stored enrolled_at/dropped_at interval otherwise.
Recorded check-ins are always retained, including students who subsequently
dropped or re-enrolled. Current is_active alone never defines past absence.
Historical limitation: enrollment intervals overwritten before audit logging
existed cannot be reconstructed for students without a recorded check-in. No
new snapshot/history table is introduced or historical completeness promised.

The dashboard's verification multi-select allows individual statuses to be
selected together. Selecting only Flagged and/or Appealed consumes every page from
GET /checkins/flagged with course_id/session_id/limit/offset and filters this
same roster. Review notes remain optional per the existing request schema;
only approved/rejected decisions are accepted. The detail risk score remains
on the API's 0–1 scale; factor weights are shown as returned. The dashboard hides
the entire Risk factors section for approved check-ins.

Export session check-ins reuses GET /export/session/{session_id}?format=csv,
with the existing documented columns and instructor/admin permissions. It
exports all submitted records, including pending/rejected, rather than attempts
or absent students; search, filters, and pagination do not scope the export.

### Check-ins

Check-ins record student attendance at sessions.

#### POST /checkins/
Student check-in to a session. **Requires auth (student only).**

**Request:**
```json
{
  "session_id": "uuid",
  "latitude": 1.3483,
  "longitude": 103.6831,
  "location_accuracy_meters": 10.0,
  "device_fingerprint": "unique_device_id",
  "liveness_challenge_response": "base64_encoded_image",  // Optional
  "qr_code": "session_qr_code"  // Optional, if session requires QR
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "student_id": "uuid",
  "status": "approved",  // pending|approved|flagged|rejected
  "checked_in_at": "2024-01-15T14:05:00Z",
  "latitude": 1.3483,
  "longitude": 103.6831,
  "distance_from_venue_meters": 45.2,
  "liveness_passed": true,
  "liveness_score": 0.92,
  "risk_score": 0.15,
  "risk_factors": [
    {"type": "device_unknown", "weight": 0.15}
  ]
}
```

**Check-in Status Logic:**
| Risk Score | Critical Signals | Result |
|------------|------------------|--------|
| < threshold | None | `approved` |
| >= threshold | None | `flagged` (requires review) |
| Any | Liveness failed | `rejected` |
| Any | GPS > 2x geofence | `rejected` |

**Error Responses:**
- `400 Bad Request`: Session not active, check-in window closed, already checked in
- `404 Not Found`: Session not found

#### GET /checkins/
List all check-ins with filters. **Requires auth (instructor/admin).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_id` | uuid | - | Filter by session |
| `course_id` | uuid | - | Filter by course |
| `student_id` | uuid | - | Filter by student |
| `status` | string | - | Filter by status (pending\|approved\|flagged\|rejected\|appealed) |
| `min_risk_score` | float | - | Minimum risk score |
| `max_risk_score` | float | - | Maximum risk score |
| `start_date` | ISO8601 | - | Check-ins after this date |
| `end_date` | ISO8601 | - | Check-ins before this date |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "uuid",
      "session_id": "uuid",
      "session_name": "Lecture 5",
      "student_id": "uuid",
      "student_name": "John Doe",
      "student_email": "john@example.com",
      "status": "approved",
      "checked_in_at": "2024-01-15T14:05:00Z",
      "distance_from_venue_meters": 45.2,
      "risk_score": 0.15,
      "liveness_passed": true
    }
  ],
  "total": 500,
  "limit": 50,
  "offset": 0
}
```

#### GET /checkins/my-checkins
Get current student's check-in history. **Requires auth (student).**

Each record includes nullable `appealed_at`. A non-null value means its one
allowed appeal has already been used, even if review later changes its status
to `rejected`; the student dashboard must not offer another appeal.

Records also include `course_id` for course-scoped history queries. The student
history table displays course code, session name, check-in time, verification
status and risk score on the 0–1 scale. Session-name search/course changes reset the table
to its first page. The dashboard requests 50 results per page using `offset`;
the response remains an array, ordered newest first with an ID tie-breaker.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `course_id` | uuid | - | Filter by course |
| `session_id` | uuid | - | Filter by session before applying the result limit |
| `session_name` | string | - | Case-insensitive literal substring search; trimmed and applied before pagination |
| `status` | string | - | Comma-separated verification statuses, e.g. flagged,appealed; OR filter before pagination |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Matching records to skip, after course/session filtering |

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "session_id": "uuid",
    "session_name": "Lecture 5: Neural Networks",
    "course_code": "CS6101",
    "status": "approved",
    "checked_in_at": "2024-01-15T14:05:00Z",
    "risk_score": 0.15
  }
]
```

#### GET /checkins/session/{session_id}
Get all check-ins for a session. **Requires auth (instructor/TA).**

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "student_id": "uuid",
    "student_name": "John Doe",
    "student_email": "john@example.com",
    "status": "approved",
    "checked_in_at": "2024-01-15T14:05:00Z",
    "distance_from_venue_meters": 45.2,
    "risk_score": 0.15,
    "risk_factors": [],
    "liveness_passed": true,
    "device_trusted": true
  }
]
```

#### GET /checkins/flagged
Get check-ins requiring review (flagged or appealed). **Requires auth (instructor/TA).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `course_id` | uuid | - | Filter by course |
| `session_id` | uuid | - | Filter by session |
| `limit` | int | 50 | Results per page |

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "session_id": "uuid",
    "session_name": "Lecture 5",
    "student_id": "uuid",
    "student_name": "John Doe",
    "status": "flagged",  // or "appealed"
    "checked_in_at": "2024-01-15T14:05:00Z",
    "risk_score": 0.72,
    "risk_factors": [
      {"type": "geo_out_of_bounds", "severity": "high", "weight": 0.4},
      {"type": "device_unknown", "severity": "medium", "weight": 0.15}
    ],
    "appeal_reason": null,  // Set if status is "appealed"
    "appealed_at": null
  }
]
```

#### GET /checkins/{checkin_id}
Get specific check-in details. **Requires auth (owner student, or instructor/TA for session).**

**Response:** `200 OK` - Returns the check-in details and verification results. Risk factors are not included in this response.

#### POST /checkins/{id}/appeal
Appeal a rejected/flagged check-in. **Requires auth (student, must be owner).**

**Request:**
```json
{
  "appeal_reason": "I was actually in class, my phone GPS was inaccurate due to building interference."
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "status": "appealed",
  "appeal_reason": "...",
  "appealed_at": "2024-01-15T15:00:00Z"
}
```

**Validation:**
- Can only appeal `rejected` or `flagged` check-ins
- Cannot appeal more than once
- Appeal window: 7 days from check-in

#### POST /checkins/{id}/review
Review a flagged/appealed check-in. **Requires auth (instructor/TA for the session's course).**

**Request:**
```json
{
  "status": "approved",  // approved|rejected
  "review_notes": "GPS issue confirmed via student's explanation and nearby WiFi logs."
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "status": "approved",
  "reviewed_by_id": "uuid",
  "reviewed_at": "2024-01-15T16:00:00Z",
  "review_notes": "..."
}
```

---

### Statistics

#### GET /stats/my-overview (student Overview)

The student page uses these three cards at the top of its existing layout,
without additional tabs. View attendance applies a course to the existing
history table. Flagged's View records applies flagged/appealed filters to that
same table. Today's sessions displays counts without a navigation action.

JWT authentication, **student only**. Identity is derived from the token; no
student ID parameter is accepted for scoping. An optional `course_id` must be
one of the caller's current enrollments (otherwise 403). Existing staff
`/stats/students/{student_id}` permissions and calculations are unchanged.

Query `section=attendance|today|flagged|all` (default all). Independent frontend
queries use the first three values and poll every 30 seconds. `course_id`
affects attendance only; today and flagged always cover the student's courses.

Response fields (only requested sections are included):

```json
{
  "as_of": "2026-10-24T04:00:00Z",
  "courses": [{"id":"uuid","code":"SC4000","name":"Machine Learning","semester":"S1"}],
  "period": {"start":"2026-08-07T16:00:00Z","end":"2026-10-24T04:00:00Z","error":null},
  "attendance": {"course_id":"uuid","approved":9,"eligible":10,"percentage":90.0,"unresolved":0},
  "today": {"date":"2026-10-24","start":"2026-10-23T16:00:00Z","end":"2026-10-24T16:00:00Z","total":2,"active":1,"upcoming":1,"completed":0,"sessions":[]},
  "flagged": {"total":1,"flagged":0,"appealed":1}
}
```

Attendance uses `SEMESTER_START_DATE` at Singapore midnight through `as_of`.
Missing/invalid/future configuration produces `period.error`; it must not be
displayed as zero attendance. Course semester labels are free text, not a
calendar; operators must update this existing setting each semester.
The selected course defaults to the caller's first current enrollment by code.

The denominator is distinct eligible Closed sessions starting within this
period, including those without a check-in. Scheduled/Active/Cancelled
sessions are excluded; scheduled lifecycle transitions are resolved at read
time without writes, preserving explicit Closed/Cancelled states. Eligibility
is enrollment at scheduled start, using immutable enrollment_added/removed
events, or the stored enrolled_at/dropped_at interval when no prior event is
available. Overwritten pre-audit enrollment intervals cannot be reconstructed;
historical completeness is not promised. No schema changes are introduced.

The numerator counts only effective approved check-ins in that denominator;
unresolved counts pending/flagged/appealed separately. Unique(student,session)
prevents retries; latest checked_in_at then ID is a defensive legacy fallback.
`percentage` retains the backend calculation without rounding and is null with
zero eligible sessions. The UI rounds to the nearest integer; null displays
an empty ring and an em dash. No warning threshold is applied. This approved
attendance metric intentionally differs from the instructor roster's timing
based Present/Absent policy.

Attendance returns aggregate counts only; the unused completed-session detail
list is omitted. Missing check-ins still count in the denominator.
Today's sessions use Singapore [midnight,next midnight),
scheduled start and enrollment eligibility, excluding Cancelled sessions.
Each item has `id`, `course_id`, `course_code`, `name`, nullable `venue_name`,
UTC `scheduled_start`/`scheduled_end`, and `status`. Today counts sessions,
not check-ins. Flagged totals count distinct effective own records of flagged
or appealed status across courses, excluding resolved appeals and all other
statuses. The three cards expose separate loading/error states; course
requests use cancellation and distinct query keys without previous-course
placeholder metrics. Appeal submission invalidates these metrics; polling
reflects reviews, lifecycle changes, and enrollment changes.

View attendance scrolls to the existing history table with the selected course.
View records scrolls to that table across courses with both flagged and appealed
filters; records retain newest-first ordering. Today's sessions shows the
counts for the API's Singapore date without a details link. Selection uses
the dashboard's existing React view state; no tabs are added.

Analytics endpoints for the instructor dashboard.

#### GET /stats/overview
Get system-wide statistics. **Requires auth (instructor/admin).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `course_id` | uuid | - | Filter stats by course |
| `days` | int | 7 | Number of days for trends |

**Response:** `200 OK`
```json
{
  "total_sessions": 150,
  "active_sessions": 3,
  "total_checkins_today": 245,
  "total_checkins_week": 1203,
  "average_attendance_rate": 0.87,
  "flagged_pending_review": 12,
  "approval_rate": 0.94,
  "average_risk_score": 0.18,
  "high_risk_checkins_today": 5,
  "trends": {
    "checkins_by_day": [
      {"date": "2024-01-15", "count": 245},
      {"date": "2024-01-14", "count": 198}
    ],
    "attendance_rate_by_day": [
      {"date": "2024-01-15", "rate": 0.89},
      {"date": "2024-01-14", "rate": 0.85}
    ]
  }
}
```

#### GET /stats/sessions/{session_id}
Get statistics for a specific session. **Requires auth (instructor/TA for session's course).**

**Response:** `200 OK`
```json
{
  "session_id": "uuid",
  "session_name": "Lecture 5",
  "course_code": "CS6101",
  "scheduled_start": "2024-01-15T14:00:00Z",
  "status": "closed",
  "total_enrolled": 50,
  "checked_in": 45,
  "attendance_rate": 0.90,
  "by_status": {
    "approved": 42,
    "flagged": 2,
    "rejected": 1,
    "pending": 0
  },
  "average_risk_score": 0.18,
  "average_distance_meters": 23.5,
  "average_checkin_time_minutes": 3.2,
  "risk_distribution": {
    "low": 40,    // risk < 0.3
    "medium": 4,  // 0.3 <= risk < 0.5
    "high": 1     // risk >= 0.5
  },
  "checkin_timeline": [
    {"minute": 0, "count": 15},
    {"minute": 5, "count": 20},
    {"minute": 10, "count": 8},
    {"minute": 15, "count": 2}
  ]
}
```

#### GET /stats/courses/{course_id}
Get attendance statistics for a course. **Requires auth (instructor for course, or admin).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | ISO8601 | semester start | Start of date range |
| `end_date` | ISO8601 | today | End of date range |

**Response:** `200 OK`
```json
{
  "course_id": "uuid",
  "course_code": "CS6101",
  "course_name": "Advanced Topics in CS",
  "total_sessions": 12,
  "total_enrolled": 50,
  "overall_attendance_rate": 0.87,
  "sessions": [
    {
      "session_id": "uuid",
      "name": "Lecture 5",
      "date": "2024-01-15",
      "attendance_rate": 0.90,
      "checked_in": 45
    }
  ],
  "student_attendance": [
    {
      "student_id": "uuid",
      "student_name": "John Doe",
      "sessions_attended": 11,
      "attendance_rate": 0.92,
      "average_risk_score": 0.12
    }
  ],
  "low_attendance_alerts": [
    {
      "student_id": "uuid",
      "student_name": "Jane Smith",
      "attendance_rate": 0.50,
      "sessions_missed": 6
    }
  ]
}
```

#### GET /stats/courses/{course_id}/overview

**Added by: ishita.**

Full route: `GET /api/v1/stats/courses/{course_id}/overview`.
Get course-scoped aggregates for the instructor overview dashboard.
**Requires auth (instructor for course, or admin).**

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | ISO8601 datetime | None | Inclusive lower bound on session `scheduled_start` |
| `end_date` | ISO8601 datetime | None | Exclusive upper bound on session `scheduled_start` |

Pass both bounds for a selected reporting period. For October 2026 in Singapore,
use `start_date=2026-10-01T00:00:00+08:00` and
`end_date=2026-11-01T00:00:00+08:00`; URL-encode the values, including `+` as `%2B`.
When both bounds are supplied, `start_date` must be strictly before `end_date`.
Unlike `GET /stats/courses/{course_id}`, this endpoint's end bound is exclusive.
An omitted bound leaves that side of the session aggregation unrestricted.
If either bound is omitted, the trend instead starts at today's local midnight
and spans 31 days; supply both bounds to align the trend with the other aggregates.

**Response:** `200 OK`

Illustrative response for five currently enrolled students, one closed session,
and one active session. Datetime response fields are currently serialized as
UTC without a timezone suffix. Trend dates and `today.date` use `timezone`
(`APP_TIMEZONE`, default `Asia/Singapore`).

```json
{
  "course_id": "course-uuid",
  "course_code": "CS6101",
  "course_name": "Advanced Topics in CS",
  "timezone": "Asia/Singapore",
  "start_date": "2026-09-30T16:00:00",
  "end_date": "2026-10-31T16:00:00",
  "attendance": {
    "recorded": 7,
    "expected": 10,
    "rate": 0.7,
    "held_sessions": 2,
    "active_sessions": 1,
    "approval_rate": 0.7143,
    "status_counts": {
      "approved": 5,
      "flagged": 1,
      "appealed": 1,
      "rejected": 0,
      "pending": 0
    },
    "historical_enrollment_limited": true
  },
  "outstanding": {
    "flagged": 1,
    "appealed": 1
  },
  "today": {
    "date": "2026-10-28",
    "total": 1,
    "breakdown": {
      "scheduled": 0,
      "active": 1,
      "closed": 0,
      "cancelled": 0
    }
  },
  "low_participation": {
    "threshold": 0.4,
    "total": 1,
    "students": [
      {
        "student_id": "student-uuid",
        "student_name": "John Doe",
        "student_email": "john@example.com",
        "submitted_sessions": 0,
        "expected_sessions": 1,
        "participation_rate": 0
      }
    ]
  },
  "risk_distribution": {
    "scored_count": 7,
    "bins": [
      { "label": "0.0–<0.1", "min": 0, "max": 0.1, "count": 3 },
      { "label": "0.1–<0.2", "min": 0.1, "max": 0.2, "count": 1 },
      { "label": "0.2–<0.3", "min": 0.2, "max": 0.3, "count": 1 },
      { "label": "0.3–<0.4", "min": 0.3, "max": 0.4, "count": 1 },
      { "label": "0.4–<0.5", "min": 0.4, "max": 0.5, "count": 0 },
      { "label": "0.5–<0.6", "min": 0.5, "max": 0.6, "count": 1 },
      { "label": "0.6–<0.7", "min": 0.6, "max": 0.7, "count": 0 },
      { "label": "0.7–<0.8", "min": 0.7, "max": 0.8, "count": 0 },
      { "label": "0.8–<0.9", "min": 0.8, "max": 0.9, "count": 0 },
      { "label": "0.9–1.0", "min": 0.9, "max": 1, "count": 0 }
    ]
  },
  "trend": [
    {
      "start": "2026-10-01",
      "end": "2026-10-08",
      "recorded": 4,
      "expected": 5,
      "rate": 0.8,
      "provisional": false
    },
    {
      "start": "2026-10-08",
      "end": "2026-10-15",
      "recorded": 0,
      "expected": 0,
      "rate": null,
      "provisional": false
    },
    {
      "start": "2026-10-15",
      "end": "2026-10-22",
      "recorded": 0,
      "expected": 0,
      "rate": null,
      "provisional": false
    },
    {
      "start": "2026-10-22",
      "end": "2026-11-01",
      "recorded": 3,
      "expected": 5,
      "rate": 0.6,
      "provisional": true
    }
  ],
  "recent_sessions": [
    {
      "session_id": "session-uuid",
      "name": "Lecture 1",
      "status": "closed",
      "scheduled_start": "2026-10-05T06:00:00",
      "scheduled_end": "2026-10-05T08:00:00",
      "recorded": 4,
      "expected": 5,
      "rate": 0.8
    }
  ]
}
```

**Aggregation rules:**

- Attendance includes `active` and `closed` sessions in the selected period,
  counting check-ins regardless of verification status. `expected` is the current
  active enrollment count multiplied by held sessions. `rate` is recorded / expected,
  capped at `1` and rounded to four decimal places, or `0` when expected is zero.
  `approval_rate` is approved / all held-session
  check-ins, or `null` when there are none.
- `historical_enrollment_limited` is `true`: expected attendance uses current
  active enrollments rather than enrollment history at each session date.
- `outstanding` counts flagged and appealed check-ins across the whole course,
  independent of the selected period. `today` counts sessions by status for the
  current local day, also independent of the selected period.
- Low participation includes currently active enrollees with check-ins in
  **40% or fewer of the selected closed sessions**. Any check-in status counts
  as submitted. With no eligible closed sessions, the list is empty.
- Risk distribution includes only non-null scores from selected held sessions.
  The API returns ten width-0.1 bins; each is lower-inclusive and upper-exclusive,
  except the final bin includes `1.0`. The dashboard combines these into
  **Low `<0.3`**, **Medium `0.3–<0.5`**, and **High `≥0.5`**.
- With both bounds supplied, periods longer than seven days use four buckets:
  the first three span seven days each, and the fourth spans the remaining days.
  Periods up to seven days use daily buckets. Bucket ends are exclusive; rates
  use summed recorded / expected totals and are `null` when expected is zero.
  `provisional` indicates a bucket containing an active session.
- `recent_sessions` returns up to five selected closed sessions, ordered by
  scheduled end descending, then scheduled start descending.

**Errors:** `400` for `start_date >= end_date`, `403` for an authenticated user
without access, `404` for an unknown course, and `422` for invalid datetime input.

#### GET /stats/students/{student_id}
Get attendance statistics for a specific student. **Requires auth (instructor for student's courses, or admin).**

**Response:** `200 OK`
```json
{
  "student_id": "uuid",
  "student_name": "John Doe",
  "student_email": "john@example.com",
  "courses": [
    {
      "course_id": "uuid",
      "course_code": "CS6101",
      "attendance_rate": 0.92,
      "sessions_attended": 11,
      "total_sessions": 12,
      "average_risk_score": 0.12
    }
  ],
  "recent_checkins": [
    {
      "session_name": "Lecture 5",
      "course_code": "CS6101",
      "checked_in_at": "2024-01-15T14:05:00Z",
      "status": "approved"
    }
  ]
}
```

---

### Devices

Device management for security and trust scoring.

#### POST /devices/register
Register a new device. **Requires auth.**

**Request:**
```json
{
  "device_fingerprint": "unique_device_hash",
  "device_name": "John's iPhone",
  "platform": "ios",  // ios|android|web|desktop
  "public_key": "-----BEGIN PUBLIC KEY-----..."
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "device_fingerprint": "unique_device_hash",
  "device_name": "John's iPhone",
  "platform": "ios",
  "is_trusted": false,
  "trust_score": "low",
  "is_active": true,
  "first_seen_at": "2024-01-15T10:00:00Z"
}
```

#### GET /devices/my-devices
List current user's registered devices. **Requires auth.**

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "device_name": "John's iPhone",
    "platform": "ios",
    "is_trusted": true,
    "trust_score": "high",
    "is_active": true,
    "first_seen_at": "2024-01-01T10:00:00Z",
    "last_seen_at": "2024-01-15T14:05:00Z",
    "total_checkins": 25
  }
]
```

#### DELETE /devices/{device_id}
Remove a device. **Requires auth (owner or admin).**

**Response:** `204 No Content`

#### PATCH /devices/{device_id}
Update device properties. **Requires auth (owner for name, admin for trust).**

**Request:**
```json
{
  "device_name": "My Primary Phone",
  "is_trusted": true,  // Admin only
  "is_active": false   // Deactivate device
}
```

**Response:** `200 OK` - Returns updated device object

---

### Enrollments

Manage student course enrollments.

#### GET /enrollments/my-enrollments
Get current student's course enrollments. **Requires auth (student).**

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "course_id": "uuid",
    "course_code": "CS6101",
    "course_name": "Advanced Topics in CS",
    "semester": "AY2024-25 Sem 1",
    "instructor_name": "Dr. Smith",
    "enrolled_at": "2024-01-10T10:00:00Z",
    "is_active": true
  }
]
```

#### GET /enrollments/course/{course_id}
Get all students enrolled in a course. **Requires auth (instructor/TA for course).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `is_active` | boolean | true | Filter by enrollment status (`true`, `false`, or `all`) |
| `search` | string | - | Search by student name/email |

**Response:** `200 OK`
```json
{
  "course_id": "uuid",
  "course_code": "CS6101",
  "total_enrolled": 50,
  "total_records": 52,
  "active_count": 50,
  "inactive_count": 2,
  "matching_count": 50,
  "students": [
    {
      "id": "uuid",
      "student_id": "uuid",
      "student_email": "student@example.com",
      "student_name": "John Doe",
      "enrolled_at": "2024-01-10T10:00:00Z",
      "is_active": true,
      "face_enrolled": true
    }
  ]
}
```

`total_enrolled` and `active_count` count all active enrollments in the course.
`total_records` includes active and inactive records, and `matching_count` counts
the returned students after filtering. The roster is not paginated or truncated.
Search matches name/email case-insensitively and treats SQL wildcard characters
literally. Instructor access requires `course.instructor_id` to match the caller;
unassigned courses are admin-only for instructor access. TAs may read rosters
only for courses explicitly assigned through the course TA assignment endpoints;
otherwise requests fail closed (403).

#### POST /enrollments/
Enroll a student in a course. **Requires auth (instructor for course, or admin).**

**Request:**
```json
{
  "student_id": "uuid",
  "course_id": "uuid"
}
```

**Response:** `201 Created` - Returns enrollment object

**Error Responses:**
- `400 Bad Request`: Student already enrolled
- `404 Not Found`: Student or course not found

#### POST /enrollments/bulk
Bulk enroll students by email. **Requires auth (instructor for course, or admin).**

**Request:**
```json
{
  "course_id": "uuid",
  "student_emails": [
    "student1@example.com",
    "student2@example.com",
    "student3@example.com"
  ],
  "create_accounts": false  // If true, create accounts for unknown emails
}
```

**Response:** `200 OK`
```json
{
  "enrolled": 2,
  "already_enrolled": 1,
  "not_found": 0,
  "created": 0,
  "details": [
    {"email": "student1@example.com", "status": "enrolled"},
    {"email": "student2@example.com", "status": "already_enrolled"},
    {"email": "student3@example.com", "status": "enrolled"}
  ]
}
```

Repeated validated email addresses are processed once. Existing inactive
enrollments are reactivated. Non-student or disabled accounts are reported as
`not_found` with an explanatory per-email error. Missing accounts are reported
as `not_found` unless `create_accounts=true`. Successful entries and audit rows
commit together; concurrent unique-constraint conflicts roll back the batch
and return 409, so clients can retry. Single enrollment conflicts return 400.
New accounts receive a queued email invitation. Accounts and enrollments commit
before delivery; SMTP failure does not undo enrollment. New-account results add
`invitation_status: "queued"` and `invitation_pending: true`. Pending accounts
cannot log in until password setup completes. Existing usable accounts are not
sent setup invitations and their passwords cannot be reset through this flow.

#### DELETE /enrollments/{enrollment_id}
Deactivate an enrollment (`is_active=false`, with `dropped_at` recorded). Attendance history is retained. Re-enrollment reactivates the existing record. **Requires auth (instructor for course, or admin).**

**Response:** `204 No Content`

---

### Enrollment invitation setup (Added by ishita)

- `GET /enrollments/course/{course_id}/invitations`: owning instructor/admin;
  returns `items` containing email, invitation_status, invitation_pending and
  invitation_error (nullable). States: queued, sending, sent, failed, not_needed.
- `POST /enrollments/invitations/resend`: owning instructor/admin; body
  `{ "course_id": "uuid", "email": "student@example.edu" }`. Requires an
  active enrollment and pending account setup. Rotates the link and queues
  delivery; returns the invitation status. Returns 403 for an unrelated course,
  400 for no pending setup, and 429 with Retry-After for resends within 60 seconds.
- `POST /auth/invitations/validate`: public; body `{ "token": "..." }`;
  returns `{ "email": "..." }` for a valid invitation, otherwise 400.
- `POST /auth/invitations/complete`: public; body `{ "token": "...", "password": "..." }`;
  accepts 8-72 characters and at most 72 UTF-8 bytes. Atomically consumes the
  token and sets a bcrypt password. Returns email and a success message, 400
  for expired/used/tampered links, or sanitized 422 for invalid input. The
  frontend then uses the existing login endpoint and cookie flow.
- `POST /auth/invitations/request`: public; body `{ "email": "..." }`;
  returns the same generic message for unknown, completed, disabled and pending
  accounts. Only eligible pending accounts receive another invitation. Requests
  are limited to five per IP per minute per backend worker, and rotation has a
  persisted 60-second cooldown per account.

Links expire after 24 hours, are single-use and purpose-bound, and place their
token in the URL fragment (`/setup-account#token=...`) so HTTP request URLs do
not contain it. The page clears the fragment after loading. Tokens, passwords
and SMTP exceptions are excluded from audit details and invitation error output.
A durable outbox retries interrupted `sending` claims after two minutes. Failed
SMTP deliveries require resend; sent means accepted by SMTP, not that a user
has read the email. Delivery worker checks run every three seconds. Only newly
provisioned accounts use this flow; it is not a password-reset mechanism for
existing users.

---

### Audit Logs

Immutable audit trail for compliance and security.

#### GET /audit/
Get audit logs with comprehensive filtering. **Requires auth (admin only).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | uuid | - | Filter by user |
| `action` | string | - | Filter by action type |
| `resource_type` | string | - | Filter by resource (user\|session\|checkin\|course) |
| `resource_id` | uuid | - | Filter by specific resource |
| `success` | boolean | - | Filter by success status |
| `start_date` | ISO8601 | - | Logs after this date |
| `end_date` | ISO8601 | - | Logs before this date |
| `limit` | int | 100 | Results per page (max 1000) |
| `offset` | int | 0 | Pagination offset |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "user_email": "student@example.com",
      "action": "checkin_attempted",
      "severity": "info",
      "resource_type": "checkin",
      "resource_id": "uuid",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "device_id": "uuid",
      "details": {
        "session_id": "uuid",
        "risk_score": 0.15
      },
      "success": true,
      "timestamp": "2024-01-15T14:05:00Z"
    }
  ],
  "total": 5000,
  "limit": 100,
  "offset": 0
}
```

The dashboard and CSV export use `timestamp`, `user_email`, `action`,
`severity`, and `details`. `timestamp` is ISO 8601 UTC with a `Z` suffix;
`user_email` is null for system events or unknown users; `details` is a JSON
object or null. Severity is `info`, `warning`, or `critical`, derived from the
action and success flag. The response retains the documented metadata and
pagination fields. The former UI aliases `occurred_at`, `actor_email`,
`event_type`, and `detail` are not returned.

**Audit Actions:**
| Action | Description |
|--------|-------------|
| `login_success` | Successful login |
| `login_failed` | Failed login attempt |
| `logout` | User logout |
| `user_created` | New user registration |
| `user_updated` | Profile update |
| `checkin_attempted` | Check-in attempt |
| `checkin_approved` | Check-in auto-approved |
| `checkin_flagged` | Check-in flagged for review |
| `checkin_rejected` | Check-in rejected |
| `checkin_appealed` | Student appealed check-in |
| `checkin_reviewed` | Instructor reviewed check-in |
| `session_created` | New session created |
| `session_updated` | Session modified |
| `session_deleted` | Session deleted |
| `enrollment_added` | Student enrolled |
| `enrollment_removed` | Enrollment removed |
| `device_registered` | New device registered |
| `face_enrolled` | Face enrollment completed |

---

### Export

Data export endpoints for reporting.

#### GET /export/attendance/{course_id}
Export attendance data for a course. **Requires auth (assigned course instructor or admin).**
Unassigned courses are admin-only. TA and student access is forbidden.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | csv | Export format (csv\|json) |
| `start_date` | ISO8601 | semester start | Start date |
| `end_date` | ISO8601 | today | End date |

**Response:** `200 OK`
- `format=csv`: Returns CSV file download
- `format=json`: Returns JSON array

Date bounds are inclusive and filter the session's scheduled start, rather than
the check-in timestamp. Offset-aware timestamps are converted to UTC; naive
timestamps are treated as UTC. The dashboard submits midnight through
23:59:59.999999 with `+08:00` for the selected Singapore dates.
Omitted `start_date` uses `SEMESTER_START_DATE` at Singapore midnight; if not
configured, it has no lower bound. Omitted `end_date` uses the end of today in
Singapore. Invalid date/format parameters return 422; a reversed range returns 400.
The shared semester start is also returned as `semester_start_date` on courses.
JSON array items contain the same eight fields as CSV, with `risk_score` numeric
and `checked_in_at` a UTC ISO8601 timestamp. Empty JSON is `[]`; empty CSV has headers only.

**CSV Columns:**
```csv
student_id,student_name,student_email,session_date,session_name,status,checked_in_at,risk_score
```

#### GET /export/session/{session_id}
Export check-in data for a session. **Requires auth (instructor for session).**

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | csv | Export format (csv\|json) |

**Response:** `200 OK` - Returns downloadable file

---

## Face Recognition Service

**Base URL:** `http://localhost:8001`

This service handles face enrollment, face matching, liveness detection, and risk assessment.
It is called internally by the Backend API and does not require authentication.

> **Note:** Liveness detection (`/liveness/check`) is a **BONUS feature** due to its complexity.
> The core required features are face enrollment and face matching.

---

### POST /face/enroll
Enroll a user's face for future verification. This is a one-time registration per user.

**Request:**
```json
{
  "user_id": "uuid",
  "image": "base64_encoded_image",
  "camera_consent": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | UUID of the user being enrolled |
| `image` | string | Yes | Base64-encoded face image (PNG/JPEG) |
| `camera_consent` | boolean | Yes | Must be `true` to proceed with enrollment |

**Response:** `201 Created`
```json
{
  "enrollment_successful": true,
  "face_template_hash": "64_char_sha256_hex_string",
  "quality_score": 0.85,
  "details": {
    "face_detected": true,
    "face_detection_confidence": 0.95,
    "image_quality": "good"
  }
}
```

**Success Criteria:**
- Face detected with confidence >= 0.7
- Quality score >= 0.5
- Returns SHA-256 hash (64 hex chars) of face template
- Store `face_template_hash` in `users.face_embedding_hash`

**Error Responses:**
- `400 Bad Request`: No face detected, invalid image, or `camera_consent` is false
- `422 Validation Error`: Missing required fields

**Privacy Requirements:**
- Raw images MUST NOT be stored - only the hash is persisted
- All image processing must be in-memory only

---

### POST /face/verify
Verify that a face image matches a previously enrolled face.

**Request:**
```json
{
  "image": "base64_encoded_image",
  "reference_template_hash": "64_char_sha256_hex_string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | string | Yes | Base64-encoded face image to verify |
| `reference_template_hash` | string | Yes | Hash from enrollment (stored in `users.face_embedding_hash`) |

**Response:** `200 OK`
```json
{
  "match_passed": true,
  "match_score": 0.82,
  "match_threshold": 0.70,
  "face_detected": true,
  "current_template_hash": "64_char_sha256_hex_string"
}
```

**Matching Logic:**
- `match_passed = (match_score >= 0.70)`
- Same person should score >= 0.70
- Different person should score < 0.70

**Implementation Approaches (choose one):**
1. **ML-Based**: Use face embeddings (FaceNet, ArcFace) with cosine similarity
2. **Feature-Based**: Extract facial landmarks, compute geometric similarity
3. **Perceptual Hash**: Use pHash/dHash with Hamming distance (simpler but less robust)

---

### POST /face/match *(Legacy - use /face/verify instead)*
Match a face against a stored reference hash. Same as `/face/verify` for backward compatibility.

**Request:**
```json
{
  "image": "base64_encoded_image",
  "reference_hash": "sha256_64_char_hex_string"
}
```

**Response:** `200 OK`
```json
{
  "match_passed": true,
  "match_score": 0.85,
  "face_embedding_hash": "sha256_64_char_hex_string"
}
```

Note: `match_passed` is true when `match_score >= 0.7`

---

### POST /liveness/check *(BONUS FEATURE)*
Check face liveness from image using 3D cue analysis. **This is a bonus feature (3 points).**

Single-image liveness detection distinguishes real faces from:
- Printed photos (lack 3D depth)
- Screen displays (moire patterns, flat depth)
- Basic deepfakes (inconsistent face mesh)

**Request:**
```json
{
  "challenge_response": "base64_encoded_image",
  "challenge_type": "passive"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `challenge_response` | string | Yes | Base64-encoded face image (PNG/JPEG) |
| `challenge_type` | string | No | Detection mode (default: "passive") |

**Supported Challenge Types:**
| Type | Description | Implementation |
|------|-------------|----------------|
| `passive` | No user action required | Analyze depth cues from single image |
| `blink` | Detect eye blink | Compare eye aspect ratios |
| `head_turn` | Detect head rotation | Track face mesh landmarks |

> **Note:** The `passive` challenge type is recommended for simplicity - it analyzes 3D depth cues from a single image without requiring user interaction.

**Response:** `200 OK`
```json
{
  "liveness_passed": true,
  "liveness_score": 0.78,
  "liveness_threshold": 0.60,
  "challenge_type": "passive",
  "face_embedding_hash": "sha256_64_char_hex_string",
  "details": {
    "face_detection_confidence": 0.95,
    "face_mesh_complete": true,
    "depth_detected": true,
    "texture_analysis_score": 0.82,
    "threshold": 0.6
  }
}
```

**Liveness Detection Logic:**
- `liveness_passed = (liveness_score >= 0.60)`
- Uses MediaPipe Face Mesh for 3D analysis

**3D Cue Analysis (Recommended Implementation):**
1. **Depth Detection (30%)**: Check nose_tip_z coordinate from MediaPipe (real faces have z < -0.05)
2. **Face Mesh Completeness (25%)**: All 468 landmarks detected
3. **Texture Analysis (25%)**: Check for print/screen artifacts
4. **Color Distribution (20%)**: Natural skin color variance

**Anti-Spoofing Targets:**
- Printed photos: Should fail (no depth cues)
- Screen displays: Should fail (flat z-coordinates)
- Synthetic/uniform faces: Should score < 0.5

### POST /risk/assess
Comprehensive risk assessment combining multiple signals.

**Request:**
```json
{
  "liveness_score": 0.92,
  "face_match_score": 0.85,
  "device_signature": "device_hash",
  "device_public_key": "PEM_key_string",
  "user_agent": "Mozilla/5.0...",
  "ip_address": "192.168.1.1",
  "geolocation": {
    "latitude": 1.3483,
    "longitude": 103.6831,
    "accuracy": 10.0
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `liveness_score` | float | No | 0.0-1.0, from liveness check |
| `face_match_score` | float | No | 0.0-1.0, from face verification |
| `device_signature` | string | No | Device attestation signature |
| `device_public_key` | string | No | PEM-encoded public key |
| `user_agent` | string | No | Browser/client user agent |
| `ip_address` | string | No | Client IP address |
| `geolocation` | object | No | Location with lat, lng, accuracy |

**Response:** `200 OK`
```json
{
  "risk_score": 0.25,
  "risk_level": "LOW",
  "pass_threshold": true,
  "risk_threshold": 0.50,
  "signal_breakdown": {
    "liveness": 0.08,
    "face_match": 0.04,
    "device": 0.02,
    "network": 0.06,
    "geolocation": 0.05
  },
  "recommendations": []
}
```

| Field | Type | Description |
|-------|------|-------------|
ok | `risk_score` | float | 0.0-1.0, combined weighted risk |
| `risk_level` | string | LOW, MEDIUM, HIGH, or CRITICAL |
| `pass_threshold` | boolean | true if risk_score < risk_threshold |
| `risk_threshold` | float | Threshold used (default 0.50) |
| `signal_breakdown` | object | Per-signal risk contributions |
| `recommendations` | array | List of recommendation strings for low-scoring signals |

**Risk Level Mapping:**
- `LOW`: risk_score < 0.3
- `MEDIUM`: 0.3 <= risk_score < 0.5
- `HIGH`: 0.5 <= risk_score < 0.7
- `CRITICAL`: risk_score >= 0.7

**Signal Weights (for combining scores):**
| Signal | Weight | Notes |
|--------|--------|-------|
| Liveness | 25% | Invert: risk = 1 - liveness_score |
| Face Match | 25% | Invert: risk = 1 - face_match_score |
| Device | 20% | Check signature validity |
| Network | 15% | Detect VPN/proxy |
| Geolocation | 15% | Check accuracy and validity |

**Recommendations Logic:**
Generate recommendations for any signal that contributes high risk:
- Low liveness: "Improve lighting and face visibility"
- Low face match: "Re-enroll face or improve image quality"
- VPN detected: "Disable VPN for check-in"
- Bad geolocation: "Enable precise location services"

---

### POST /device/attest *(OPTIONAL - Not Tested)*
Verify device authenticity. This endpoint is optional and not included in public tests.

**Request:**
```json
{
  "device_public_key": "PEM_key_string",
  "device_signature": "signature_string",
  "challenge": "random_challenge_string",
  "device_info": {
    "platform": "ios",
    "os_version": "17.0"
  }
}
```

**Response:** `200 OK`
```json
{
  "attestation_passed": true,
  "attestation_score": 0.95,
  "device_trusted": true,
  "device_fingerprint": "sha256_hash",
  "issues": []
}
```

### GET /health
Health check endpoint.

**Response:** `200 OK`
```json
{
  "status": "healthy"
}
```

### GET /
Root endpoint - lists available API endpoints.

**Response:** `200 OK`
```json
{
  "service": "SAIV Face Recognition & Risk Service",
  "version": "1.0.0",
  "endpoints": [
    "GET /health - Health check",
    "POST /face/enroll - Enroll a face for verification",
    "POST /face/verify - Verify a face against enrolled template",
    "POST /face/match - Legacy face matching",
    "POST /liveness/check - Perform liveness detection (BONUS)",
    "POST /risk/assess - Multi-signal risk assessment"
  ]
}
```

---

### Admin Endpoints (Required for Automated Testing)

These endpoints are required for the automated test suite to work properly. They allow tests to set up test data and manipulate state without direct database access.

#### PATCH /admin/users/{user_id}/deactivate
Deactivate a user account. **Requires auth (admin only).**

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": false,
  "message": "User deactivated successfully"
}
```

#### PATCH /admin/users/{user_id}/activate
Reactivate a user account. **Requires auth (admin only).**

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "message": "User activated successfully"
}
```

#### POST /admin/users/bulk
Bulk create users. **Requires auth (admin only).**

Designed for stress testing scenarios where many users need to be created quickly.

**Request:**
```json
{
  "users": [
    {
      "email": "student1@example.com",
      "password": "securepass123",
      "full_name": "Student One",
      "role": "student"
    },
    {
      "email": "student2@example.com",
      "password": "securepass123",
      "full_name": "Student Two",
      "role": "student"
    }
  ]
}
```

**Response:** `201 Created`
```json
{
  "created": 2,
  "failed": 0,
  "users": [
    {"id": "uuid", "email": "student1@example.com", "full_name": "Student One", "role": "student"},
    {"id": "uuid", "email": "student2@example.com", "full_name": "Student Two", "role": "student"}
  ],
  "errors": []
}
```

#### PATCH /admin/sessions/{session_id}/status
Update session status. **Requires auth (admin only).**

Allows setting session status for testing edge cases like checking in to closed or cancelled sessions.

**Request:**
```json
{
  "status": "closed"  // scheduled|active|closed|cancelled
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "name": "Lecture 5",
  "status": "closed",
  "message": "Session status changed from 'active' to 'closed'"
}
```

#### POST /admin/enrollments/
Create enrollment as admin (bypasses instructor ownership check). **Requires auth (admin only).**

This endpoint is designed for test setup where an admin needs to enroll a student without being the course instructor.

**Request:**
```json
{
  "student_id": "uuid",
  "course_id": "uuid"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "student_id": "uuid",
  "course_id": "uuid",
  "is_active": true,
  "enrolled_at": "2024-01-15T10:00:00Z"
}
```

---

## Error Responses

All endpoints may return these error codes:

**400 Bad Request**
```json
{
  "detail": "Invalid input data"
}
```

**401 Unauthorized**
```json
{
  "detail": "Could not validate credentials"
}
```

**403 Forbidden**
```json
{
  "detail": "Insufficient permissions"
}
```

**404 Not Found**
```json
{
  "detail": "Resource not found"
}
```

**422 Validation Error**
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "Invalid email format",
      "type": "value_error.email"
    }
  ]
}
```

**429 Too Many Requests**
```json
{
  "detail": "Rate limit exceeded"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Login attempts | 60 | per hour per IP |
| API requests | 1000 | per hour per user |
| Check-in attempts | 10 | per minute per user |
| Registration | 10 | per hour per IP |

---

## CORS Policy

Allowed origins (configurable):
- http://localhost:3000 (Frontend)
- http://localhost:8501 (Dashboard)

---

## Security Requirements

1. **Password Hashing**: Bcrypt with cost factor >= 10
2. **JWT Signing**: HS256 algorithm, access token expires in 1 hour, refresh token expires in 7 days
3. **Input Validation**: Pydantic schemas
4. **SQL Injection Prevention**: ORM only (SQLAlchemy)
5. **XSS Prevention**: Output sanitization
6. **CSRF Protection**: Token-based
7. **Risk Threshold**: Default 0.5 (configurable per course/session)

> **Note**: This student project uses HTTP only. HTTPS/TLS is not required.

---

## Pagination

All list endpoints support consistent pagination:

```json
{
  "items": [...],
  "total": 100,   // Total matching records
  "limit": 50,    // Page size
  "offset": 0     // Current offset
}
```

**Query Parameters:**
- `limit`: Number of results per page (default varies, max 100)
- `offset`: Number of records to skip

---

## Testing Your Implementation

Run public tests:
```bash
pytest tests/public/ -v
```

Your implementation should pass 100% of public tests for full marks.

---

## Quick Start: Face Recognition Implementation

### Step 1: Install Dependencies

```bash
pip install mediapipe opencv-python pillow
```

### Step 2: Decode Base64 Images

```python
import base64
from io import BytesIO
from PIL import Image
import numpy as np

def decode_base64_image(base64_string: str) -> np.ndarray:
    """Convert base64 string to numpy array for MediaPipe."""
    try:
        image_data = base64.b64decode(base64_string)
        image = Image.open(BytesIO(image_data))
        return np.array(image.convert('RGB'))
    except Exception as e:
        raise ValueError(f"Invalid image: {e}")
```

### Step 3: Detect Faces with MediaPipe

```python
import mediapipe as mp

def detect_face(image_array: np.ndarray) -> dict:
    """Detect face and return detection info."""
    mp_face_detection = mp.solutions.face_detection

    with mp_face_detection.FaceDetection(
        min_detection_confidence=0.5
    ) as face_detection:
        results = face_detection.process(image_array)

        if not results.detections:
            return {"detected": False, "confidence": 0.0}

        # Take the first (most confident) detection
        detection = results.detections[0]
        confidence = detection.score[0]

        return {
            "detected": True,
            "confidence": confidence,
            "bounding_box": detection.location_data.relative_bounding_box
        }
```

### Step 4: Generate Face Hash

```python
import hashlib
import cv2

def generate_face_hash(image_array: np.ndarray, bbox) -> str:
    """Extract face region and generate SHA-256 hash."""
    h, w = image_array.shape[:2]

    # Crop face region
    x = int(bbox.xmin * w)
    y = int(bbox.ymin * h)
    width = int(bbox.width * w)
    height = int(bbox.height * h)

    # Ensure bounds are valid
    x = max(0, x)
    y = max(0, y)
    face_crop = image_array[y:y+height, x:x+width]

    # Resize to standard size for consistent hashing
    face_resized = cv2.resize(face_crop, (64, 64))

    # Generate hash
    return hashlib.sha256(face_resized.tobytes()).hexdigest()
```

### Step 5: Analyze Face Mesh for Liveness (BONUS)

```python
def analyze_face_mesh(image_array: np.ndarray) -> dict:
    """Analyze face mesh for 3D depth cues (BONUS)."""
    mp_face_mesh = mp.solutions.face_mesh

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        min_detection_confidence=0.5
    ) as face_mesh:
        results = face_mesh.process(image_array)

        if not results.multi_face_landmarks:
            return {
                "face_mesh_complete": False,
                "nose_tip_z": 0.0,
                "depth_quality": "poor"
            }

        landmarks = results.multi_face_landmarks[0]

        # Nose tip is landmark index 1
        nose_tip = landmarks.landmark[1]
        nose_tip_z = nose_tip.z

        # Determine depth quality
        if abs(nose_tip_z) > 0.03:
            depth_quality = "good"
        elif abs(nose_tip_z) > 0.01:
            depth_quality = "moderate"
        else:
            depth_quality = "poor"

        return {
            "face_mesh_complete": len(landmarks.landmark) >= 400,
            "landmark_count": len(landmarks.landmark),
            "nose_tip_z": nose_tip_z,
            "depth_quality": depth_quality
        }
```

### Step 6: VPN/Proxy Detection

```python
def detect_vpn_proxy(ip_address: str, user_agent: str) -> tuple:
    """Detect VPN/proxy usage. Returns (is_vpn, confidence)."""
    is_vpn = False
    confidence = 0.0

    if ip_address:
        # Private IP ranges (common VPN indicators)
        if (ip_address.startswith('10.') or
            ip_address.startswith('192.168.') or
            ip_address.startswith('172.16.') or
            ip_address.startswith('172.17.') or
            ip_address.startswith('172.18.') or
            ip_address.startswith('172.19.')):
            is_vpn = True
            confidence = 0.7

    if user_agent:
        vpn_keywords = ['vpn', 'proxy', 'tunnel', 'tor']
        if any(kw in user_agent.lower() for kw in vpn_keywords):
            is_vpn = True
            confidence = max(confidence, 0.8)

    return is_vpn, confidence
```

---

## Backend Integration

### Calling Face Service from Backend

The backend API should call the face recognition service during check-in:

```python
import httpx
import os

FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://localhost:8001")

async def enroll_face(user_id: str, image: str, consent: bool) -> dict:
    """Call face service to enroll a user's face."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FACE_SERVICE_URL}/face/enroll",
            json={
                "user_id": user_id,
                "image": image,
                "camera_consent": consent
            }
        )
        return response.json()

async def verify_face(image: str, reference_hash: str) -> dict:
    """Call face service to verify a face."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{FACE_SERVICE_URL}/face/verify",
            json={
                "image": image,
                "reference_template_hash": reference_hash
            }
        )
        return response.json()

async def assess_risk(signals: dict) -> dict:
    """Call face service for risk assessment."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            f"{FACE_SERVICE_URL}/risk/assess",
            json=signals
        )
        return response.json()
```

### Updating User Face Enrollment Status

After successful face enrollment, update the user's record:

```python
# In backend check-in or enrollment endpoint
face_result = await enroll_face(user.id, image_base64, user.camera_consent)

if face_result.get("enrollment_successful"):
    # Update user record with face hash
    user.face_embedding_hash = face_result["face_template_hash"]
    user.face_enrolled = True
    db.commit()
```

### Optional motion verification extension

Session create/update accepts `require_motion_check` (default false). When true,
check-in requires a server-issued `motion_verification_id`; omitting biometric
fields cannot bypass this policy. Existing image-based contracts remain valid
for sessions without this requirement. See
[Motion verification](../new-documentations/MOTION-VERIFICATION.md) for the
challenge, sequence-upload, expiry, limits, and response contracts.
