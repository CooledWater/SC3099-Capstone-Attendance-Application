# PRD feature implementation audit — 26 October 2026

Audited against [prd.md](prd.md), working-tree source at commit `357f8fc`, and the current read-only [docs](../docs). All four application modules, their integration/configuration, persistence models and relevant existing tests were checked. The older [2 October inventory](list-of-features-02OCT.md) was not used as proof of current implementation.

**Coverage: 124 uniquely identified PRD features.** 68 implemented; 49 partially implemented; 4 missing; 3 need additional runtime verification. Every feature appears once below with code evidence and a reference to its specification under `docs/`.

“Implemented” means the required application path exists and its source supports the behavior; it does not claim every security/privacy/performance property is proven. “Partial” means a material required behavior is absent or differs from the PRD, even if a public test passes. “Missing” permits inert columns/schemas but no working feature. “Verification pending” distinguishes insufficient runtime evidence from absent code. Optional and bonus requirements remain in scope and are identified by their original headings.

Default behavior is assessed with `STRICT_SECURITY_MODE=false`, as in Compose. Opt-in safeguards are credited where present but do not count as unconditional defaults. Current documentation occasionally differs from the PRD; these discrepancies are identified rather than silently resolved. No application code, service configuration or file in `docs/` was changed.

## Coverage by PRD area

| PRD area | Implemented | Partial | Missing | Verification pending | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| F-AUTH | 2 | 3 | 0 | 0 | 5 |
| F-RBAC | 1 | 1 | 0 | 0 | 2 |
| F-USER | 4 | 1 | 0 | 0 | 5 |
| F-COURSE | 2 | 2 | 0 | 0 | 4 |
| F-ENROLL | 5 | 0 | 0 | 0 | 5 |
| F-SESSION | 3 | 4 | 1 | 0 | 8 |
| F-CHECKIN | 6 | 3 | 0 | 0 | 9 |
| F-GEO | 2 | 2 | 0 | 0 | 4 |
| F-DEVICE | 3 | 2 | 1 | 0 | 6 |
| F-FACE | 7 | 2 | 0 | 0 | 9 |
| F-RISK | 0 | 3 | 1 | 0 | 4 |
| F-STATS | 4 | 0 | 0 | 0 | 4 |
| F-EXPORT | 2 | 0 | 0 | 0 | 2 |
| F-AUDIT | 3 | 1 | 0 | 0 | 4 |
| F-PRIVACY | 2 | 3 | 0 | 0 | 5 |
| F-SEC | 3 | 5 | 0 | 0 | 8 |
| F-ADMIN | 5 | 0 | 0 | 0 | 5 |
| F-FE | 4 | 5 | 0 | 1 | 10 |
| F-DASH | 5 | 5 | 0 | 0 | 10 |
| F-OPS | 2 | 4 | 1 | 0 | 7 |
| F-PERF | 0 | 2 | 0 | 2 | 4 |
| F-API | 3 | 1 | 0 | 0 | 4 |
| **Total** | **68** | **49** | **4** | **3** | **124** |

## Implemented features

#### F-AUTH-3 — Token Refresh

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Refresh verifies signature, expiry and token type, checks the account, and returns new access/refresh tokens. Browser cookie support and strict-mode rotation/reuse rejection are also present. Code: [module2-backend/app/main.py:301](../module2-backend/app/main.py#L301); [module2-backend/app/security.py:63](../module2-backend/app/security.py#L63) | [API-SPECIFICATION.md:84](../docs/API-SPECIFICATION.md#L84); [SECURITY-REQUIREMENTS.md:31](../docs/SECURITY-REQUIREMENTS.md#L31) |

#### F-AUTH-5 — Logout

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Logout expires the refresh cookie and records logout when a valid actor token is available; both clients clear their in-memory access token. Strict mode also revokes the cookie's refresh token. Code: [module2-backend/app/main.py:396](../module2-backend/app/main.py#L396); [module1-frontend/lib/api/auth.ts](../module1-frontend/lib/api/auth.ts); [module4-observability/src/lib/api.ts](../module4-observability/src/lib/api.ts) | [SECURITY-REQUIREMENTS.md:200](../docs/SECURITY-REQUIREMENTS.md#L200); [module1.md:65](../docs/module1.md#L65); [INTEGRATION-GUIDE.md:62](../docs/INTEGRATION-GUIDE.md#L62) |

#### F-RBAC-1 — Role Hierarchy

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Four roles and server-side role allowlists exist, with course ownership and explicit TA assignments. Authorization uses the current database account role after JWT verification, so role changes take effect immediately; see the claim-source discrepancy below. Code: [module2-backend/app/auth.py:157](../module2-backend/app/auth.py#L157); [module2-backend/app/permissions.py:16](../module2-backend/app/permissions.py#L16); [module2-backend/app/course_assistants.py:55](../module2-backend/app/course_assistants.py#L55) | [SECURITY-REQUIREMENTS.md:55](../docs/SECURITY-REQUIREMENTS.md#L55); [API-SPECIFICATION.md:15](../docs/API-SPECIFICATION.md#L15); [module4.md:93](../docs/module4.md#L93) |

#### F-USER-2 — Own Profile Update

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Partial full-name/consent updates are persisted and returned; flags can be enabled or withdrawn. Full-name updates are HTML-escaped and audited. Code: [module2-backend/app/main.py:452](../module2-backend/app/main.py#L452); [module2-backend/app/schemas.py:30](../module2-backend/app/schemas.py#L30) | [API-SPECIFICATION.md:124](../docs/API-SPECIFICATION.md#L124); [SECURITY-REQUIREMENTS.md:181](../docs/SECURITY-REQUIREMENTS.md#L181); [SECURITY-REQUIREMENTS.md:155](../docs/SECURITY-REQUIREMENTS.md#L155) |

#### F-USER-3 — User Directory (Admin)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin-only user directory supplies role/activity/search filters, total count and bounded limit/offset pagination, without password or template material. Code: [module2-backend/app/main.py:710](../module2-backend/app/main.py#L710) | [API-SPECIFICATION.md:138](../docs/API-SPECIFICATION.md#L138) |

#### F-USER-4 — User Detail & Administrative Update

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admins can read users and patch role/activity. Instructor detail reads require an active enrollment in an assigned course. Code: [module2-backend/app/main.py:747](../module2-backend/app/main.py#L747); [module2-backend/app/main.py:783](../module2-backend/app/main.py#L783) | [API-SPECIFICATION.md:170](../docs/API-SPECIFICATION.md#L170); [API-SPECIFICATION.md:175](../docs/API-SPECIFICATION.md#L175) |

#### F-USER-5 — Face Enrollment via Backend

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Backend face enrollment checks camera consent, calls Module 3, persists only the returned template and enrollment flag, audits success, and maps invalid images/unavailable service to 400/503. Code: [module2-backend/app/main.py:486](../module2-backend/app/main.py#L486); [module2-backend/app/face_service.py:258](../module2-backend/app/face_service.py#L258) | [API-SPECIFICATION.md:188](../docs/API-SPECIFICATION.md#L188); [API-SPECIFICATION.md:2200](../docs/API-SPECIFICATION.md#L2200) |

#### F-COURSE-3 — Course Creation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin-only course creation accepts documented metadata, venue and policy defaults, returns 201, rejects duplicate codes, and denies instructors. Code: [module2-backend/app/main.py:862](../module2-backend/app/main.py#L862); [module2-backend/app/schemas.py:42](../module2-backend/app/schemas.py#L42) | [API-SPECIFICATION.md:294](../docs/API-SPECIFICATION.md#L294); [DATABASE-SCHEMA.md:52](../docs/DATABASE-SCHEMA.md#L52) |

#### F-COURSE-4 — Course Update and Soft Delete

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Course owners/admins can partially update courses; admin DELETE sets is_active=false and returns 204, retaining associated history. Code: [module2-backend/app/main.py:1016](../module2-backend/app/main.py#L1016); [module2-backend/app/main.py:1048](../module2-backend/app/main.py#L1048) | [API-SPECIFICATION.md:314](../docs/API-SPECIFICATION.md#L314); [API-SPECIFICATION.md:328](../docs/API-SPECIFICATION.md#L328) |

#### F-ENROLL-1 — Student's Own Enrollments

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Student enrollment feed returns active memberships with course code/name, semester, instructor name, enrollment time and activity flag. Code: [module2-backend/app/main.py:1364](../module2-backend/app/main.py#L1364) | [API-SPECIFICATION.md:1143](../docs/API-SPECIFICATION.md#L1143); [DATABASE-SCHEMA.md:78](../docs/DATABASE-SCHEMA.md#L78) |

#### F-ENROLL-2 — Course Roster

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Roster is restricted to the assigned instructor, assigned TA or admin. It returns the documented envelope/student fields, active/all filters and name/email search. Code: [module2-backend/app/main.py:1396](../module2-backend/app/main.py#L1396) | [API-SPECIFICATION.md:1162](../docs/API-SPECIFICATION.md#L1162) |

#### F-ENROLL-3 — Single Enrollment

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Instructor ownership/admin checks, student/course existence validation, duplicate protection and 201 creation exist. A unique student/course index protects concurrent inserts; dropped memberships can be reactivated. Code: [module2-backend/app/main.py:1079](../module2-backend/app/main.py#L1079); [module2-backend/app/main.py:1153](../module2-backend/app/main.py#L1153); [module2-backend/app/models.py:218](../module2-backend/app/models.py#L218) | [API-SPECIFICATION.md:1203](../docs/API-SPECIFICATION.md#L1203); [DATABASE-SCHEMA.md:78](../docs/DATABASE-SCHEMA.md#L78) |

#### F-ENROLL-4 — Bulk Enrollment by Email

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Bulk email enrollment returns counts and per-email outcomes, creates missing student accounts when requested, and queues account-setup invitations with the enrollment transaction. Code: [module2-backend/app/main.py:1206](../module2-backend/app/main.py#L1206); [module2-backend/app/invitations.py](../module2-backend/app/invitations.py) | [API-SPECIFICATION.md:1220](../docs/API-SPECIFICATION.md#L1220); [API-SPECIFICATION.md:1270](../docs/API-SPECIFICATION.md#L1270); [DATABASE-SCHEMA.md:315](../docs/DATABASE-SCHEMA.md#L315) |

#### F-ENROLL-5 — Enrollment Removal

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Owning instructors/admins can remove an enrollment with 204; the record is deactivated, dropped_at is set, and enrollment_removed is audited. Code: [module2-backend/app/main.py:1307](../module2-backend/app/main.py#L1307) | [API-SPECIFICATION.md:1263](../docs/API-SPECIFICATION.md#L1263); [DATABASE-SCHEMA.md:78](../docs/DATABASE-SCHEMA.md#L78) |

#### F-SESSION-3 — Session Deletion

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Scheduled-only deletion enforces owning-instructor/admin access, rejects sessions with check-ins, removes motion metadata and writes an audit entry atomically. Returns 204. Admin access follows the current API specification and PRD permission matrix. Code: [module2-backend/app/main.py:2013](../module2-backend/app/main.py#L2013) | [API-SPECIFICATION.md:531](../docs/API-SPECIFICATION.md#L531) |

#### F-SESSION-4 — Session Listing (Instructor/Admin)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Scoped TA/instructor/admin listing supports all named filters, the required page envelope, course metadata, enrollment counts and batched checked-in counts. Code: [module2-backend/app/main.py:1698](../module2-backend/app/main.py#L1698); [module2-backend/app/main.py:1555](../module2-backend/app/main.py#L1555) | [API-SPECIFICATION.md:339](../docs/API-SPECIFICATION.md#L339) |

#### F-SESSION-6 — Personal Session Feed

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Personal session feed filters enrolled/teaching courses, status/upcoming/time range and pagination. Student historical eligibility is reconstructed from enrollment events. Code: [module2-backend/app/main.py:1758](../module2-backend/app/main.py#L1758); [module2-backend/app/student_overview.py:42](../module2-backend/app/student_overview.py#L42) | [API-SPECIFICATION.md:404](../docs/API-SPECIFICATION.md#L404) |

#### F-CHECKIN-2 — Duplicate Prevention

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Unique session/student index is authoritative. IntegrityError handling rolls back racing submissions and returns 400 for the duplicate; motion-proof consumption/audit changes share the transaction. Code: [module2-backend/app/models.py:500](../module2-backend/app/models.py#L500); [module2-backend/app/main.py:2514](../module2-backend/app/main.py#L2514) | [DATABASE-SCHEMA.md:165](../docs/DATABASE-SCHEMA.md#L165); [DATABASE-SCHEMA.md:284](../docs/DATABASE-SCHEMA.md#L284); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606) |

#### F-CHECKIN-3 — Student Check-In History

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Own student history is a bare array, includes session/course metadata and status/risk/time, supports course/session/status/search plus limit/offset, and returns [] when empty. Code: [module2-backend/app/main.py:2561](../module2-backend/app/main.py#L2561) | [API-SPECIFICATION.md:695](../docs/API-SPECIFICATION.md#L695) |

#### F-CHECKIN-5 — Global Check-In Query

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Instructor/admin check-in query supports every named filter, scoped joins and the required bounded paginated envelope. Code: [module2-backend/app/main.py:2679](../module2-backend/app/main.py#L2679); [module2-backend/app/main.py:2728](../module2-backend/app/main.py#L2728) | [API-SPECIFICATION.md:654](../docs/API-SPECIFICATION.md#L654) |

#### F-CHECKIN-6 — Flagged Review Queue

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Flagged queue restricts results to flagged/appealed, enforces course access, exposes stored risk factors and appeal text/time, and supports course/session filtering and pagination. Code: [module2-backend/app/main.py:2780](../module2-backend/app/main.py#L2780); [module2-backend/app/main.py:2679](../module2-backend/app/main.py#L2679) | [API-SPECIFICATION.md:755](../docs/API-SPECIFICATION.md#L755) |

#### F-CHECKIN-8 — Student Appeal

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Only the owning student can appeal flagged/rejected records, once, within seven days. Status/reason/time are saved under a row lock, text is escaped and checkin_appealed is audited. Code: [module2-backend/app/main.py:2877](../module2-backend/app/main.py#L2877); [module2-backend/app/schemas.py:134](../module2-backend/app/schemas.py#L134) | [API-SPECIFICATION.md:792](../docs/API-SPECIFICATION.md#L792) |

#### F-CHECKIN-9 — Instructor Review

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Assigned instructors/TAs/admins can approve/reject flagged or appealed records with notes; reviewer/time/decision are persisted under a lock and audited. Code: [module2-backend/app/main.py:2937](../module2-backend/app/main.py#L2937); [module2-backend/app/schemas.py:136](../module2-backend/app/schemas.py#L136) | [API-SPECIFICATION.md:817](../docs/API-SPECIFICATION.md#L817) |

#### F-GEO-1 — Haversine Distance Calculation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Haversine distance uses session venue overrides then course defaults and stores the result in meters on the check-in. Code: [module2-backend/app/main.py:1462](../module2-backend/app/main.py#L1462); [module2-backend/app/main.py:2090](../module2-backend/app/main.py#L2090); [module2-backend/app/main.py:2110](../module2-backend/app/main.py#L2110) | [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606); [DATABASE-SCHEMA.md:165](../docs/DATABASE-SCHEMA.md#L165); [SECURITY-REQUIREMENTS.md:109](../docs/SECURITY-REQUIREMENTS.md#L109) |

#### F-GEO-3 — Coordinate Validation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Pydantic enforces finite latitude/longitude in the valid ranges and rejects invalid coordinates with 422; course/session venue coordinates have equivalent bounds. Code: [module2-backend/app/schemas.py:42](../module2-backend/app/schemas.py#L42); [module2-backend/app/schemas.py:88](../module2-backend/app/schemas.py#L88); [module2-backend/app/schemas.py:125](../module2-backend/app/schemas.py#L125) | [SECURITY-REQUIREMENTS.md:141](../docs/SECURITY-REQUIREMENTS.md#L141); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606) |

#### F-DEVICE-1 — Device Registration

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Both POST device aliases accept metadata/key material, enforce fingerprint ownership, return 201 with initial low/untrusted state, and audit newly registered devices. PEM validation/key creation timestamps are gaps in the broader device contract, below. Code: [module2-backend/app/main.py:3012](../module2-backend/app/main.py#L3012); [module2-backend/app/schemas.py:143](../module2-backend/app/schemas.py#L143); [module2-backend/app/models.py:508](../module2-backend/app/models.py#L508) | [API-SPECIFICATION.md:1071](../docs/API-SPECIFICATION.md#L1071); [DATABASE-SCHEMA.md:130](../docs/DATABASE-SCHEMA.md#L130) |

#### F-DEVICE-2 — Own Device List

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Own devices are returned as a bare array with trust, activity, first/last seen and total_checkins, including [] for no devices. The counter is exposed but not updated by check-in processing. Code: [module2-backend/app/main.py:2995](../module2-backend/app/main.py#L2995); [module2-backend/app/main.py:3072](../module2-backend/app/main.py#L3072) | [API-SPECIFICATION.md:1098](../docs/API-SPECIFICATION.md#L1098) |

#### F-DEVICE-3 — Device Directory (Admin)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin-only directory has user/activity/trust filters, identity enrichment, pagination and total count. Code: [module2-backend/app/main.py:3084](../module2-backend/app/main.py#L3084) | [DATABASE-SCHEMA.md:130](../docs/DATABASE-SCHEMA.md#L130); [SECURITY-REQUIREMENTS.md:55](../docs/SECURITY-REQUIREMENTS.md#L55) |

#### F-FACE-1 — Service Health

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Face service health returns 200 with healthy status, service identity and version. Code: [module3-face-recognition/app/main.py:181](../module3-face-recognition/app/main.py#L181) | [API-SPECIFICATION.md:1727](../docs/API-SPECIFICATION.md#L1727) |

#### F-FACE-2 — Endpoint Discovery

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Root returns identity/version and endpoint discovery covering enrollment, verify, match, liveness, risk, attestation, health and metrics. Code: [module3-face-recognition/app/main.py:190](../module3-face-recognition/app/main.py#L190) | [API-SPECIFICATION.md:1737](../docs/API-SPECIFICATION.md#L1737) |

#### F-FACE-3 — Face Enrollment

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Enrollment checks explicit consent before decoding, detects exactly one face, enforces confidence/quality thresholds, and returns a 64-hex SimHash template and quality details. Native sample-image checks passed. Code: [module3-face-recognition/app/main.py:245](../module3-face-recognition/app/main.py#L245); [module3-face-recognition/app/embedding.py](../module3-face-recognition/app/embedding.py); [module3-face-recognition/app/quality.py](../module3-face-recognition/app/quality.py); [module3-face-recognition/app/template.py](../module3-face-recognition/app/template.py) | [API-SPECIFICATION.md:1445](../docs/API-SPECIFICATION.md#L1445); [module3.md:20](../docs/module3.md#L20) |

#### F-FACE-4 — Face Verification (1:1)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** 1:1 verification compares the current SimHash template to the reference, uses the configured 0.70 threshold and returns the documented score/detection/template fields. Native same-person/different-person cases passed. Code: [module3-face-recognition/app/main.py:332](../module3-face-recognition/app/main.py#L332); [module3-face-recognition/app/main.py:433](../module3-face-recognition/app/main.py#L433); [module3-face-recognition/app/template.py](../module3-face-recognition/app/template.py) | [API-SPECIFICATION.md:1493](../docs/API-SPECIFICATION.md#L1493); [module3.md:44](../docs/module3.md#L44) |

#### F-FACE-5 — Legacy Face Match

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Legacy /face/match shares the verification pipeline and maps reference_hash and response aliases while preserving the threshold and privacy behavior. Code: [module3-face-recognition/app/main.py:442](../module3-face-recognition/app/main.py#L442); [module3-face-recognition/app/schemas.py](../module3-face-recognition/app/schemas.py) | [API-SPECIFICATION.md:1532](../docs/API-SPECIFICATION.md#L1532) |

#### F-FACE-8 — Device Attestation *(optional, untested)*

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Optional attestation validates RSA/ECDSA/Ed25519 signatures over the supplied challenge and reports score/trust/fingerprint/issues, including emulator/root information. It is standalone; backend integration is missing under F-DEVICE-6. Code: [module3-face-recognition/app/main.py:605](../module3-face-recognition/app/main.py#L605); [module3-face-recognition/app/attestation.py](../module3-face-recognition/app/attestation.py) | [API-SPECIFICATION.md:1700](../docs/API-SPECIFICATION.md#L1700) |

#### F-FACE-9 — Face Service Privacy Guarantees

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Image decoding/model work stays in request memory, results expose templates/scalars, and privacy-safe logging/tracing excludes images/templates/signatures. There is no face-service persistence layer. Code: [module3-face-recognition/app/main.py](../module3-face-recognition/app/main.py); [module3-face-recognition/app/imaging.py](../module3-face-recognition/app/imaging.py); [module3-face-recognition/app/telemetry.py](../module3-face-recognition/app/telemetry.py) | [API-SPECIFICATION.md:1445](../docs/API-SPECIFICATION.md#L1445); [SECURITY-REQUIREMENTS.md:165](../docs/SECURITY-REQUIREMENTS.md#L165); [module3.md:97](../docs/module3.md#L97) |

#### F-STATS-1 — System Overview

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Scoped overview returns required counts, rates, risk summaries and daily check-in/attendance trends with days/course filters. Code: [module2-backend/app/stats.py:126](../module2-backend/app/stats.py#L126) | [API-SPECIFICATION.md:917](../docs/API-SPECIFICATION.md#L917) |

#### F-STATS-2 — Session Statistics

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Authorized session analytics include all required counts/rates, status/risk distributions, distance/time averages and a timeline using five-minute buckets labelled by minute. Code: [module2-backend/app/stats.py:308](../module2-backend/app/stats.py#L308) | [API-SPECIFICATION.md:951](../docs/API-SPECIFICATION.md#L951) |

#### F-STATS-3 — Course Statistics

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Course owner/admin analytics include session/student attendance, date bounds and low-attendance alerts. The implementation uses a documented-in-code 75% alert threshold because the specifications provide no numeric cutoff. Code: [module2-backend/app/stats.py:411](../module2-backend/app/stats.py#L411) | [API-SPECIFICATION.md:988](../docs/API-SPECIFICATION.md#L988) |

#### F-STATS-4 — Student Statistics

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Instructor/admin student analytics scope visible courses and return student identity, enrollment/session/attendance totals, course rates and recent sessions/check-ins. Code: [module2-backend/app/stats.py:549](../module2-backend/app/stats.py#L549) | [API-SPECIFICATION.md:1035](../docs/API-SPECIFICATION.md#L1035) |

#### F-EXPORT-1 — Session Export

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Authorized session export returns JSON records/summary or downloadable UTF-8 CSV, quotes via csv.writer, neutralizes formula-leading text and writes data_exported. Code: [module2-backend/app/main.py:3212](../module2-backend/app/main.py#L3212); [module2-backend/app/main.py:3233](../module2-backend/app/main.py#L3233) | [API-SPECIFICATION.md:1421](../docs/API-SPECIFICATION.md#L1421); [module4.md:112](../docs/module4.md#L112); [SECURITY-REQUIREMENTS.md:200](../docs/SECURITY-REQUIREMENTS.md#L200) |

#### F-EXPORT-2 — Course Attendance Export

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Course-owner/admin export supports CSV/JSON and inclusive date filters, with the specified eight gradebook columns and audited export. Defaults use configured semester start and Singapore end-of-day. Code: [module2-backend/app/main.py:3338](../module2-backend/app/main.py#L3338) | [API-SPECIFICATION.md:1390](../docs/API-SPECIFICATION.md#L1390); [module4.md:112](../docs/module4.md#L112) |

#### F-AUDIT-1 — Immutable Audit Trail

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Persistent append-only AuditLog model includes the required metadata and no updated_at. ORM update/delete listeners reject changes; business actions append within their transaction and no cleanup removes audit records. This is an application-level guarantee, not a database-role/trigger audit. Code: [module2-backend/app/models.py:609](../module2-backend/app/models.py#L609); [module2-backend/app/audit.py:134](../module2-backend/app/audit.py#L134) | [DATABASE-SCHEMA.md:231](../docs/DATABASE-SCHEMA.md#L231); [SECURITY-REQUIREMENTS.md:212](../docs/SECURITY-REQUIREMENTS.md#L212) |

#### F-AUDIT-3 — Audit Log Query

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin-only audit query implements all required filters, default/max 100/1000, limit/offset, total and timestamp plus user-email/severity enrichment. Code: [module2-backend/app/audit.py:240](../module2-backend/app/audit.py#L240) | [API-SPECIFICATION.md:1309](../docs/API-SPECIFICATION.md#L1309) |

#### F-AUDIT-4 — Audit Summary

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin-only summary groups actions over a validated days window and returns period_days, total_logs and by_action. Code: [module2-backend/app/audit.py:304](../module2-backend/app/audit.py#L304) | [SECURITY-REQUIREMENTS.md:198](../docs/SECURITY-REQUIREMENTS.md#L198); [DATABASE-SCHEMA.md:231](../docs/DATABASE-SCHEMA.md#L231) |

#### F-PRIVACY-2 — No Raw Biometric Storage

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Users/check-ins have no raw image/BLOB columns and persist only 64-hex SimHash-derived templates; image requests are not stored by the processing paths. SimHash is expressly allowed by the PRD's verification section; cryptographic irreversibility/encryption is not established by these checks. Code: [module2-backend/app/models.py:76](../module2-backend/app/models.py#L76); [module2-backend/app/models.py:481](../module2-backend/app/models.py#L481); [module3-face-recognition/app/template.py](../module3-face-recognition/app/template.py); [module3-face-recognition/app/main.py](../module3-face-recognition/app/main.py) | [DATABASE-SCHEMA.md:274](../docs/DATABASE-SCHEMA.md#L274); [SECURITY-REQUIREMENTS.md:165](../docs/SECURITY-REQUIREMENTS.md#L165); [module3.md:97](../docs/module3.md#L97) |

#### F-PRIVACY-3 — Response Data Minimization

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Explicit serializers omit password/hash material from user responses and omit raw images from attendance/face responses; validation errors redact submitted inputs. Code: [module2-backend/app/main.py:110](../module2-backend/app/main.py#L110); [module2-backend/app/main.py:695](../module2-backend/app/main.py#L695); [module2-backend/app/main.py:2535](../module2-backend/app/main.py#L2535); [module3-face-recognition/app/main.py:148](../module3-face-recognition/app/main.py#L148) | [SECURITY-REQUIREMENTS.md:165](../docs/SECURITY-REQUIREMENTS.md#L165); [API-SPECIFICATION.md:107](../docs/API-SPECIFICATION.md#L107); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606) |

#### F-SEC-1 — Password Storage

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Passwords are hashed/verified with bcrypt via passlib (default cost 12); register, bulk-create and invitation setup store hashes and responses exclude them. Code: [module2-backend/app/auth.py:19](../module2-backend/app/auth.py#L19); [module2-backend/app/auth.py:31](../module2-backend/app/auth.py#L31); [module2-backend/app/main.py:173](../module2-backend/app/main.py#L173); [module2-backend/app/invitations.py](../module2-backend/app/invitations.py) | [SECURITY-REQUIREMENTS.md:9](../docs/SECURITY-REQUIREMENTS.md#L9) |

#### F-SEC-3 — SQL Injection Prevention

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** User-controlled filters use SQLAlchemy bound expressions/joins; literal SQL is limited to fixed probes/engine operations. Search strings are treated as data and wildcard-sensitive searches use autoescape. Code: [module2-backend/app/main.py:710](../module2-backend/app/main.py#L710); [module2-backend/app/main.py:2679](../module2-backend/app/main.py#L2679); [module2-backend/app/audit.py:240](../module2-backend/app/audit.py#L240); [module2-backend/app/database.py](../module2-backend/app/database.py) | [SECURITY-REQUIREMENTS.md:149](../docs/SECURITY-REQUIREMENTS.md#L149) |

#### F-SEC-6 — CORS Policy

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Default exact origins include ports 3000 and 8501. CORS_ORIGINS accepts CSV/JSON configuration and rejects wildcard/path-bearing origins; credentialed browser calls are supported. Code: [module2-backend/app/security.py:26](../module2-backend/app/security.py#L26); [module2-backend/app/main.py:130](../module2-backend/app/main.py#L130) | [SECURITY-REQUIREMENTS.md:220](../docs/SECURITY-REQUIREMENTS.md#L220); [API-SPECIFICATION.md:1946](../docs/API-SPECIFICATION.md#L1946) |

#### F-ADMIN-1 — Deactivate User

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin deactivation persists false activity, returns the user summary/message and audits the change; subsequent valid-password login returns 403. Code: [module2-backend/app/main.py:542](../module2-backend/app/main.py#L542); [module2-backend/app/main.py:281](../module2-backend/app/main.py#L281) | [API-SPECIFICATION.md:1762](../docs/API-SPECIFICATION.md#L1762) |

#### F-ADMIN-2 — Activate User

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin activation persists true activity and returns the expected summary/message with audit logging. Code: [module2-backend/app/main.py:572](../module2-backend/app/main.py#L572) | [API-SPECIFICATION.md:1775](../docs/API-SPECIFICATION.md#L1775) |

#### F-ADMIN-3 — Bulk User Creation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Bulk creation validates each item, handles duplicate/invalid entries, hashes accepted passwords with bounded parallel workers, returns 201 counts/users/errors and audits new accounts. Code: [module2-backend/app/main.py:607](../module2-backend/app/main.py#L607); [module2-backend/app/schemas.py:38](../module2-backend/app/schemas.py#L38) | [API-SPECIFICATION.md:1788](../docs/API-SPECIFICATION.md#L1788) |

#### F-ADMIN-4 — Force Session Status

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin status endpoint accepts the four session states, applies them directly, preserves actual timestamps and returns the old/new-status message plus audit entry. Code: [module2-backend/app/main.py:2057](../module2-backend/app/main.py#L2057); [module2-backend/app/schemas.py:123](../module2-backend/app/schemas.py#L123) | [API-SPECIFICATION.md:1826](../docs/API-SPECIFICATION.md#L1826) |

#### F-ADMIN-5 — Admin Enrollment

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin enrollment bypasses instructor ownership, validates course/student, reuses duplicate-safe membership creation and returns the documented 201 object. Code: [module2-backend/app/main.py:1336](../module2-backend/app/main.py#L1336); [module2-backend/app/main.py:1079](../module2-backend/app/main.py#L1079) | [API-SPECIFICATION.md:1848](../docs/API-SPECIFICATION.md#L1848) |

#### F-FE-1 — Progressive Web App Shell

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Manifest, icons/install UI and versioned service worker cache the shell/static allowlist. APIs/auth/submissions are excluded; IndexedDB retains account-scoped, expiring, read-only session snapshots. Code: [module1-frontend/app/manifest.ts](../module1-frontend/app/manifest.ts); [module1-frontend/public/sw.js](../module1-frontend/public/sw.js); [module1-frontend/scripts/build-service-worker.mjs](../module1-frontend/scripts/build-service-worker.mjs); [module1-frontend/lib/offline/sessionCache.ts](../module1-frontend/lib/offline/sessionCache.ts) | [module1.md:3](../docs/module1.md#L3); [module1.md:87](../docs/module1.md#L87) |

#### F-FE-4 — Liveness Challenge UI

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Two-blink instructions, local landmark guidance, timestamped frame capture, enrollment and server sequence verification are connected. Motion-enabled sessions submit a one-use verification ID through the documented optional extension; photo sessions submit liveness_challenge_response. Code: [module1-frontend/components/check-in/FaceVerification.tsx](../module1-frontend/components/check-in/FaceVerification.tsx); [module1-frontend/features/camera/useFaceGuidance.ts](../module1-frontend/features/camera/useFaceGuidance.ts); [module1-frontend/lib/api/checkins.ts](../module1-frontend/lib/api/checkins.ts); [module2-backend/app/motion.py](../module2-backend/app/motion.py) | [module1.md:45](../docs/module1.md#L45); [module3.md:70](../docs/module3.md#L70); [API-SPECIFICATION.md:2215](../docs/API-SPECIFICATION.md#L2215) |

#### F-FE-5 — Geolocation Capture

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Browser getCurrentPosition captures latitude/longitude/accuracy with high accuracy, zero-age fixes and timeout/denial UI. Normal submission carries all three; a separately configured integration-test build can substitute synthetic coordinates. Code: [module1-frontend/features/geolocation/useGeolocation.ts](../module1-frontend/features/geolocation/useGeolocation.ts); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx) | [module1.md:25](../docs/module1.md#L25); [INTEGRATION-GUIDE.md:112](../docs/INTEGRATION-GUIDE.md#L112) |

#### F-FE-6 — Consent & Permission Handling

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Camera/location permission state is queried, purposes and explicit checkboxes precede sequential prompts, denial/revocation resets local evidence, and consent is sent via PUT /users/me. Unconditional server enforcement is assessed separately under F-PRIVACY-1. Code: [module1-frontend/features/camera/useCamera.ts](../module1-frontend/features/camera/useCamera.ts); [module1-frontend/features/geolocation/useGeolocation.ts](../module1-frontend/features/geolocation/useGeolocation.ts); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx); [module1-frontend/lib/api/auth.ts](../module1-frontend/lib/api/auth.ts) | [module1.md:106](../docs/module1.md#L106); [API-SPECIFICATION.md:124](../docs/API-SPECIFICATION.md#L124) |

#### F-DASH-1 — Instructor Login

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Dashboard credentials reach the same backend login handler through /auth/dashboard/login; memory JWTs and a separate HttpOnly refresh cookie protect subsequent API calls, restoration and logout. Code: [module4-observability/src/lib/api.ts](../module4-observability/src/lib/api.ts); [module4-observability/src/routes/auth.tsx](../module4-observability/src/routes/auth.tsx); [module4-observability/src/hooks/useAuth.tsx](../module4-observability/src/hooks/useAuth.tsx); [module2-backend/app/main.py:218](../module2-backend/app/main.py#L218) | [INTEGRATION-GUIDE.md:275](../docs/INTEGRATION-GUIDE.md#L275); [module4.md:93](../docs/module4.md#L93) |

#### F-DASH-7 — Export to Gradebook

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Export UI uses authenticated course/session export APIs, date selection, CSV/JSON downloads and server-provided filenames. Backend CSV uses headers, UTF-8 and correct quoting. Code: [module4-observability/src/components/dashboard/ExportPanel.tsx](../module4-observability/src/components/dashboard/ExportPanel.tsx); [module4-observability/src/lib/exports.ts](../module4-observability/src/lib/exports.ts); [module4-observability/src/components/dashboard/InstructorCheckIns.tsx](../module4-observability/src/components/dashboard/InstructorCheckIns.tsx); [module2-backend/app/main.py:3212](../module2-backend/app/main.py#L3212) | [API-SPECIFICATION.md:1390](../docs/API-SPECIFICATION.md#L1390); [API-SPECIFICATION.md:1421](../docs/API-SPECIFICATION.md#L1421); [module4.md:112](../docs/module4.md#L112) |

#### F-DASH-8 — Role-Scoped Views

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Actual student/TA/instructor/admin accounts get distinct views; own-history, enrollment/course-assistant and instructor ownership boundaries are enforced in backend reads. Admin view-as is explicitly a layout preview, not impersonation; TA review tooling remains incomplete under F-DASH-4. Code: [module4-observability/src/routes/index.tsx](../module4-observability/src/routes/index.tsx); [module4-observability/src/components/dashboard/StudentView.tsx](../module4-observability/src/components/dashboard/StudentView.tsx); [module4-observability/src/components/dashboard/TaView.tsx](../module4-observability/src/components/dashboard/TaView.tsx); [module2-backend/app/permissions.py](../module2-backend/app/permissions.py) | [module4.md:93](../docs/module4.md#L93); [SECURITY-REQUIREMENTS.md:55](../docs/SECURITY-REQUIREMENTS.md#L55) |

#### F-DASH-9 — Real-Time Updates

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** React Query polls check-ins, rosters, overview, audit and metrics at 30 seconds; SessionsPanel refreshes sessions at five seconds and mutation success invalidates affected queries. Code: [module4-observability/src/components/dashboard/InstructorView.tsx](../module4-observability/src/components/dashboard/InstructorView.tsx); [module4-observability/src/components/dashboard/InstructorCheckIns.tsx](../module4-observability/src/components/dashboard/InstructorCheckIns.tsx); [module4-observability/src/components/dashboard/SessionsPanel.tsx](../module4-observability/src/components/dashboard/SessionsPanel.tsx); [module4-observability/src/components/dashboard/AuditLogs.tsx](../module4-observability/src/components/dashboard/AuditLogs.tsx) | [module4.md:52](../docs/module4.md#L52) |

#### F-DASH-10 — Audit Log Explorer

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Admin audit explorer reads the audit endpoint, polls, displays timestamp/user/action/severity/details and filters/exports the loaded events. It only loads the latest 200; full-history server-side browsing is an enhancement beyond this feature's minimum. Code: [module4-observability/src/components/dashboard/AuditLogs.tsx](../module4-observability/src/components/dashboard/AuditLogs.tsx); [module4-observability/src/components/dashboard/AdminView.tsx](../module4-observability/src/components/dashboard/AdminView.tsx); [module2-backend/app/audit.py:240](../module2-backend/app/audit.py#L240) | [API-SPECIFICATION.md:1309](../docs/API-SPECIFICATION.md#L1309); [module4.md:93](../docs/module4.md#L93) |

#### F-OPS-2 — Prometheus Metrics

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Both /metrics surfaces export request counters/duration histograms; backend records attempt/success/outcome counters and risk histogram. Prometheus scrapes both every 15 seconds; queue/ratio queries can use outcome labels. Code: [module2-backend/app/prometheus_metrics.py](../module2-backend/app/prometheus_metrics.py); [module2-backend/app/stats.py:766](../module2-backend/app/stats.py#L766); [module3-face-recognition/app/metrics.py](../module3-face-recognition/app/metrics.py); [module4-observability/prometheus.yml](../module4-observability/prometheus.yml) | [INTEGRATION-GUIDE.md:324](../docs/INTEGRATION-GUIDE.md#L324); [module4.md:73](../docs/module4.md#L73) |

#### F-OPS-5 — Alerting Signals

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Outcome counters expose flagged-versus-approved rates; HTTP counters expose login 4xx spikes for both login aliases. These signals are queryable in Prometheus. Prebuilt dashboards/notification rules are not present and are not implied by this signal-only status. Code: [module2-backend/app/prometheus_metrics.py](../module2-backend/app/prometheus_metrics.py); [module2-backend/app/stats.py:766](../module2-backend/app/stats.py#L766); [module4-observability/prometheus.yml](../module4-observability/prometheus.yml) | [module4.md:73](../docs/module4.md#L73); [INTEGRATION-GUIDE.md:324](../docs/INTEGRATION-GUIDE.md#L324) |

#### F-API-1 — REST Conventions

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** Canonical backend resources use /api/v1, plural resource nouns, HTTP methods and query filters. Legacy unprefixed auth aliases and internal face/health/metrics routes coexist with the canonical API rather than replacing it. Code: [module2-backend/app/main.py](../module2-backend/app/main.py); [module2-backend/app/stats.py](../module2-backend/app/stats.py); [module2-backend/app/audit.py](../module2-backend/app/audit.py) | [API-SPECIFICATION.md:3](../docs/API-SPECIFICATION.md#L3); [module2.md:3](../docs/module2.md#L3) |

#### F-API-3 — Response Shape Consistency

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** All explicitly named bare-array and paginated-envelope endpoints use the PRD's required shapes; ordinary HTTP/validation errors have detail. Flagged queue intentionally follows the PRD envelope despite the docs' old array example. General unhandled-error gaps are recorded under F-SEC-8/F-API-2. Code: [module2-backend/app/main.py:1670](../module2-backend/app/main.py#L1670); [module2-backend/app/main.py:2561](../module2-backend/app/main.py#L2561); [module2-backend/app/main.py:2780](../module2-backend/app/main.py#L2780); [module2-backend/app/audit.py:240](../module2-backend/app/audit.py#L240) | [API-SPECIFICATION.md:1968](../docs/API-SPECIFICATION.md#L1968); [API-SPECIFICATION.md:381](../docs/API-SPECIFICATION.md#L381); [API-SPECIFICATION.md:695](../docs/API-SPECIFICATION.md#L695); [API-SPECIFICATION.md:755](../docs/API-SPECIFICATION.md#L755) |

#### F-API-4 — Implementation Agnosticism

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Implemented.** The implementation serves the HTTP contract through FastAPI and browser clients; the public suite interacts over HTTP without requiring a particular internal framework or dashboard library. Code: [module2-backend/app/main.py](../module2-backend/app/main.py); [module3-face-recognition/app/main.py](../module3-face-recognition/app/main.py); [tests/conftest.py](../tests/conftest.py) | [Briefing.md:591](../docs/Briefing.md#L591); [module2.md:3](../docs/module2.md#L3) |


## Unimplemented or incomplete features

This list includes partial implementations, missing features, and acceptance requirements awaiting runtime verification. The status in each row makes the distinction explicit.

#### F-AUTH-1 — User Registration

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Registration, bcrypt, validation, duplicate rejection and default flags exist. The 201 response omits required created_at; strict mode additionally restricts public registration to students. Code: [module2-backend/app/main.py:173](../module2-backend/app/main.py#L173); [module2-backend/app/schemas.py:21](../module2-backend/app/schemas.py#L21) | [API-SPECIFICATION.md:30](../docs/API-SPECIFICATION.md#L30); [SECURITY-REQUIREMENTS.md:9](../docs/SECURITY-REQUIREMENTS.md#L9); [DATABASE-SCHEMA.md:25](../docs/DATABASE-SCHEMA.md#L25) |

#### F-AUTH-2 — Login and Token Issuance

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Login returns both tokens, checks passwords/account activity and logs success/failure. It never updates last_login_at. JWTs use user_id rather than sub, omit email/iat, and read JWT_SECRET rather than SECRET_KEY. Code: [module2-backend/app/main.py:218](../module2-backend/app/main.py#L218); [module2-backend/app/auth.py:45](../module2-backend/app/auth.py#L45) | [API-SPECIFICATION.md:59](../docs/API-SPECIFICATION.md#L59); [SECURITY-REQUIREMENTS.md:31](../docs/SECURITY-REQUIREMENTS.md#L31); [DATABASE-SCHEMA.md:25](../docs/DATABASE-SCHEMA.md#L25) |

#### F-AUTH-4 — Token Enforcement on Protected Endpoints

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** JWT signature, expiry, access-token type and active-account checks protect normal authenticated routes. GET /courses/ instead accepts anonymous callers and returns a 200 empty envelope, although its contract requires authentication. Code: [module2-backend/app/auth.py:85](../module2-backend/app/auth.py#L85); [module2-backend/app/main.py:887](../module2-backend/app/main.py#L887) | [API-SPECIFICATION.md:8](../docs/API-SPECIFICATION.md#L8); [API-SPECIFICATION.md:248](../docs/API-SPECIFICATION.md#L248); [SECURITY-REQUIREMENTS.md:31](../docs/SECURITY-REQUIREMENTS.md#L31) |

#### F-RBAC-2 — Endpoint Permission Matrix

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Most role/ownership boundaries are enforced. GET /checkins/my-checkins rejects TA/instructor/admin despite the PRD's all-role row; GET /checkins/ and most statistics reject TAs despite broader matrix entries. Anonymous courses and active discovery also differ from the PRD. See specification conflicts below. Code: [module2-backend/app/main.py:2561](../module2-backend/app/main.py#L2561); [module2-backend/app/main.py:2728](../module2-backend/app/main.py#L2728); [module2-backend/app/stats.py:126](../module2-backend/app/stats.py#L126); [module2-backend/app/permissions.py:45](../module2-backend/app/permissions.py#L45) | [SECURITY-REQUIREMENTS.md:64](../docs/SECURITY-REQUIREMENTS.md#L64); [API-SPECIFICATION.md:339](../docs/API-SPECIFICATION.md#L339); [API-SPECIFICATION.md:654](../docs/API-SPECIFICATION.md#L654); [API-SPECIFICATION.md:695](../docs/API-SPECIFICATION.md#L695); [API-SPECIFICATION.md:917](../docs/API-SPECIFICATION.md#L917) |

#### F-USER-1 — Own Profile Retrieval

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Own profile exposes identity, role and consent/enrollment flags and excludes password material. It omits created_at and scheduled_deletion_at, although the PRD calls for the creation timestamp and cites retention-field coverage. Code: [module2-backend/app/main.py:437](../module2-backend/app/main.py#L437); [module2-backend/app/models.py:21](../module2-backend/app/models.py#L21) | [API-SPECIFICATION.md:107](../docs/API-SPECIFICATION.md#L107); [DATABASE-SCHEMA.md:25](../docs/DATABASE-SCHEMA.md#L25) |

#### F-COURSE-1 — Course Listing

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Course listing has activity/instructor filters, pagination and batched instructor lookup. The semester filter is absent; students receive a metadata-only catalog without required venue/security fields; anonymous calls succeed with an empty page. Code: [module2-backend/app/main.py:887](../module2-backend/app/main.py#L887); [module2-backend/app/main.py:887](../module2-backend/app/main.py#L887) | [API-SPECIFICATION.md:248](../docs/API-SPECIFICATION.md#L248); [DATABASE-SCHEMA.md:52](../docs/DATABASE-SCHEMA.md#L52) |

#### F-COURSE-2 — Course Detail

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Full course metadata, venue and security settings are available to authorized/enrolled callers. Unenrolled students receive only catalog metadata, and unrelated instructors/TAs get 403; this is narrower than the PRD's full-detail contract. Code: [module2-backend/app/main.py:972](../module2-backend/app/main.py#L972); [module2-backend/app/permissions.py:34](../module2-backend/app/permissions.py#L34) | [API-SPECIFICATION.md:286](../docs/API-SPECIFICATION.md#L286); [DATABASE-SCHEMA.md:52](../docs/DATABASE-SCHEMA.md#L52) |

#### F-SESSION-1 — Session Creation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Ownership checks, future/timing validation, default check-in windows, scheduled initial status and session_created audit exist. session_type is an unrestricted string in both schema/model, so values outside lecture/tutorial/lab/exam are accepted. The docs' creation example uses session_name while code/PRD require name. Code: [module2-backend/app/main.py:1580](../module2-backend/app/main.py#L1580); [module2-backend/app/schemas.py:88](../module2-backend/app/schemas.py#L88); [module2-backend/app/models.py:305](../module2-backend/app/models.py#L305) | [API-SPECIFICATION.md:459](../docs/API-SPECIFICATION.md#L459); [DATABASE-SCHEMA.md:95](../docs/DATABASE-SCHEMA.md#L95) |

#### F-SESSION-2 — Session Lifecycle

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** PATCH, active-only/window-bound check-ins, actual timestamps and automatic scheduled activation/closure exist. The normal PATCH path assigns any allowed status without validating the transition graph; closed to active succeeds. Finalization is derived by roster/statistics reads rather than a stored final-attendance snapshot. Code: [module2-backend/app/main.py:1903](../module2-backend/app/main.py#L1903); [module2-backend/app/main.py:1572](../module2-backend/app/main.py#L1572); [module2-backend/app/session_lifecycle.py:15](../module2-backend/app/session_lifecycle.py#L15) | [API-SPECIFICATION.md:490](../docs/API-SPECIFICATION.md#L490); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606) |

#### F-SESSION-5 — Active Session Discovery

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Authenticated discovery returns an array of active sessions within the open check-in window, scoped to course relationships. Anonymous requests always return [], even when an eligible active session exists; public discovery is therefore not implemented as specified. Code: [module2-backend/app/main.py:1670](../module2-backend/app/main.py#L1670); [module2-backend/app/permissions.py:45](../module2-backend/app/permissions.py#L45) | [API-SPECIFICATION.md:381](../docs/API-SPECIFICATION.md#L381) |

#### F-SESSION-7 — Session Detail

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Session reads return schedule and effective venue/security policy for eligible callers. qr_code_enabled is omitted; unrelated students receive schedule-only metadata, and unrelated staff are denied. The PRD's any-authenticated full-detail statement is broader than current docs/code. Code: [module2-backend/app/main.py:1495](../module2-backend/app/main.py#L1495); [module2-backend/app/main.py:1862](../module2-backend/app/main.py#L1862) | [API-SPECIFICATION.md:429](../docs/API-SPECIFICATION.md#L429); [DATABASE-SCHEMA.md:95](../docs/DATABASE-SCHEMA.md#L95) |

#### F-SESSION-8 — QR Code Challenge (Optional)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Missing.** Only QR secret/expiry columns, an accepted qr_code input and a default-false result column exist. There is no challenge issue/expiry/consumption or matching-code enforcement in check-in processing. Code: [module2-backend/app/models.py:346](../module2-backend/app/models.py#L346); [module2-backend/app/schemas.py:125](../module2-backend/app/schemas.py#L125); [module2-backend/app/main.py:2351](../module2-backend/app/main.py#L2351) | [DATABASE-SCHEMA.md:95](../docs/DATABASE-SCHEMA.md#L95); [DATABASE-SCHEMA.md:165](../docs/DATABASE-SCHEMA.md#L165); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606) |

#### F-CHECKIN-1 — Check-In Submission

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Student/session/window/enrollment/duplicate validation, geo/biometric decision, persistence and outcome audit exist. Missing pipeline steps: resolve/bind a device, increment its count, persist risk_signals rows, and schedule 30-day deletion. Default non-strict photo processing can skip unavailable/missing required evidence; full biometric latency remains unverified. Code: [module2-backend/app/main.py:2351](../module2-backend/app/main.py#L2351); [module2-backend/app/main.py:2220](../module2-backend/app/main.py#L2220); [module2-backend/app/face_service.py:147](../module2-backend/app/face_service.py#L147) | [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606); [DATABASE-SCHEMA.md:165](../docs/DATABASE-SCHEMA.md#L165); [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204); [INTEGRATION-GUIDE.md:112](../docs/INTEGRATION-GUIDE.md#L112) |

#### F-CHECKIN-4 — Session Check-In Roster

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Scoped roster, joined student identity, timing, distance, risk and liveness are returned as an array; students are denied. device_trusted is absent and the device is not joined or bound. Code: [module2-backend/app/main.py:2615](../module2-backend/app/main.py#L2615) | [API-SPECIFICATION.md:733](../docs/API-SPECIFICATION.md#L733); [DATABASE-SCHEMA.md:165](../docs/DATABASE-SCHEMA.md#L165) |

#### F-CHECKIN-7 — Check-In Detail

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Owner/staff detail access and verification/review/appeal fields exist, but the response contains no risk_factors or risk_signals. This follows the current docs' explicit exclusion of factors, while the PRD requires all associated signals. Code: [module2-backend/app/main.py:2828](../module2-backend/app/main.py#L2828) | [API-SPECIFICATION.md:787](../docs/API-SPECIFICATION.md#L787); [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204) |

#### F-GEO-2 — Geofence Enforcement

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Out-of-bounds factors and rejection beyond twice the radius exist. However distance/radius/2 contributes positive geo risk even inside the radius, contrary to the PRD's zero-contribution rule. No configured venue means geofencing is skipped. Code: [module2-backend/app/main.py:2110](../module2-backend/app/main.py#L2110) | [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606); [SECURITY-REQUIREMENTS.md:109](../docs/SECURITY-REQUIREMENTS.md#L109); [DATABASE-SCHEMA.md:52](../docs/DATABASE-SCHEMA.md#L52) |

#### F-GEO-4 — Location Quality and Anomaly Signals

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Poor accuracy can raise geo_accuracy_low and Module 3 scores accuracy. No previous-check-in impossible-travel comparison exists; submitted coordinates are stored as full-precision floats, without a precision-reduction policy. Code: [module2-backend/app/main.py:2110](../module2-backend/app/main.py#L2110); [module2-backend/app/main.py:2465](../module2-backend/app/main.py#L2465); [module3-face-recognition/app/risk.py:205](../module3-face-recognition/app/risk.py#L205) | [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204); [SECURITY-REQUIREMENTS.md:181](../docs/SECURITY-REQUIREMENTS.md#L181); [API-SPECIFICATION.md:1619](../docs/API-SPECIFICATION.md#L1619) |

#### F-DEVICE-4 — Device Update and Revocation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Owners can rename/deactivate and admins can change trust. DELETE hard-deletes the row rather than recording revoked_at/revocation_reason; later owner re-registration can reactivate an existing device. Code: [module2-backend/app/main.py:3125](../module2-backend/app/main.py#L3125); [module2-backend/app/main.py:3167](../module2-backend/app/main.py#L3167); [module2-backend/app/models.py:579](../module2-backend/app/models.py#L579) | [API-SPECIFICATION.md:1118](../docs/API-SPECIFICATION.md#L1118); [API-SPECIFICATION.md:1123](../docs/API-SPECIFICATION.md#L1123); [DATABASE-SCHEMA.md:130](../docs/DATABASE-SCHEMA.md#L130) |

#### F-DEVICE-5 — Public Key Rotation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Key/timestamp columns exist and owner re-registration can replace public_key. No rotation operation, key validation, creation/expiry timestamp maintenance or check-in expiry enforcement exists. Code: [module2-backend/app/models.py:545](../module2-backend/app/models.py#L545); [module2-backend/app/schemas.py:151](../module2-backend/app/schemas.py#L151); [module2-backend/app/main.py:3012](../module2-backend/app/main.py#L3012) | [DATABASE-SCHEMA.md:130](../docs/DATABASE-SCHEMA.md#L130) |

#### F-DEVICE-6 — Device Trust Signals

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Missing.** Device safety/trust columns and a standalone Module 3 attestation service exist, but check-ins ignore the fingerprint, do not look up trust or attestation, do not grow trust from history, and do not enforce require_device_binding or emit device risk factors. Code: [module2-backend/app/main.py:2422](../module2-backend/app/main.py#L2422); [module2-backend/app/models.py:549](../module2-backend/app/models.py#L549); [module3-face-recognition/app/attestation.py](../module3-face-recognition/app/attestation.py) | [DATABASE-SCHEMA.md:130](../docs/DATABASE-SCHEMA.md#L130); [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204); [API-SPECIFICATION.md:1700](../docs/API-SPECIFICATION.md#L1700); [SECURITY-REQUIREMENTS.md:118](../docs/SECURITY-REQUIREMENTS.md#L118) |

#### F-FACE-6 — Liveness Detection *(bonus)*

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Passive liveness, image-based blink/head-turn evidence, depth/mesh/texture/color scoring and 0.60 threshold exist; an additional sequence route checks two temporal blinks. Full anti-spoofing is not achieved: the recorded 24 October phone-screen trial passed liveness at 0.822759 and was approved. Single-image active checks are posture proxies, not temporal/unpredictable challenges. Code: [module3-face-recognition/app/main.py:480](../module3-face-recognition/app/main.py#L480); [module3-face-recognition/app/liveness.py:555](../module3-face-recognition/app/liveness.py#L555); [module3-face-recognition/app/motion.py](../module3-face-recognition/app/motion.py); [new-documentations/test-logs/phone-replay-test.md](../new-documentations/test-logs/phone-replay-test.md) | [API-SPECIFICATION.md:1556](../docs/API-SPECIFICATION.md#L1556); [module3.md:70](../docs/module3.md#L70); [API-SPECIFICATION.md:2215](../docs/API-SPECIFICATION.md#L2215) |

#### F-FACE-7 — Risk Assessment

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Weighted multi-signal risk, levels, breakdowns, recommendations and high/low behavior are implemented. The device component validates signature/key format only, not cryptographic signature validity, because this endpoint has no signed challenge. Backend check-ins also omit actual device/network inputs. Code: [module3-face-recognition/app/risk.py:129](../module3-face-recognition/app/risk.py#L129); [module3-face-recognition/app/risk.py:261](../module3-face-recognition/app/risk.py#L261); [module2-backend/app/main.py:2257](../module2-backend/app/main.py#L2257) | [API-SPECIFICATION.md:1619](../docs/API-SPECIFICATION.md#L1619); [SECURITY-REQUIREMENTS.md:118](../docs/SECURITY-REQUIREMENTS.md#L118) |

#### F-RISK-1 — Signal Persistence

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Missing.** No RiskSignal ORM model/table creation or insertion path exists. Check-ins store only a JSON text risk_factors array, without a row per signal, confidence, metadata or detection time. Code: [module2-backend/app/models.py:411](../module2-backend/app/models.py#L411); [module2-backend/app/main.py:2465](../module2-backend/app/main.py#L2465) | [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204) |

#### F-RISK-2 — Recognized Signal Taxonomy

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** The backend emits geo_out_of_bounds, geo_accuracy_low, liveness_failed and face_match_failed. The remaining specified network/device/behavioral, impossible-travel and low-confidence/spoof signal taxonomy is not integrated or persisted; standalone heuristics are insufficient. Code: [module2-backend/app/main.py:2110](../module2-backend/app/main.py#L2110); [module2-backend/app/main.py:2291](../module2-backend/app/main.py#L2291); [module3-face-recognition/app/risk.py](../module3-face-recognition/app/risk.py) | [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204) |

#### F-RISK-3 — Signal Fusion and Exposure

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Module 3 supplies weighted category contributions and the queue exposes stored factors. Backend fusion is max(geo risk, Module 3 risk), not weighted per-signal confidence fusion; it does not retain/expose every contributing factor or signal confidence. Code: [module2-backend/app/main.py:2291](../module2-backend/app/main.py#L2291); [module2-backend/app/main.py:2679](../module2-backend/app/main.py#L2679); [module3-face-recognition/app/risk.py:261](../module3-face-recognition/app/risk.py#L261) | [SECURITY-REQUIREMENTS.md:118](../docs/SECURITY-REQUIREMENTS.md#L118); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606); [API-SPECIFICATION.md:755](../docs/API-SPECIFICATION.md#L755); [DATABASE-SCHEMA.md:204](../docs/DATABASE-SCHEMA.md#L204) |

#### F-RISK-4 — Configurable Thresholds

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Session-to-course threshold inheritance, numeric overrides and default 0.5/0.6/0.7/100m values exist. Backend default risk remains literal 0.5; RISK_SCORE_THRESHOLD is unused, while Module 3 reads the differently named RISK_THRESHOLD. Code: [module2-backend/app/main.py:1462](../module2-backend/app/main.py#L1462); [module2-backend/app/main.py:2431](../module2-backend/app/main.py#L2431); [module3-face-recognition/app/config.py:217](../module3-face-recognition/app/config.py#L217) | [SECURITY-REQUIREMENTS.md:109](../docs/SECURITY-REQUIREMENTS.md#L109); [SECURITY-REQUIREMENTS.md:248](../docs/SECURITY-REQUIREMENTS.md#L248); [DATABASE-SCHEMA.md:52](../docs/DATABASE-SCHEMA.md#L52); [DATABASE-SCHEMA.md:95](../docs/DATABASE-SCHEMA.md#L95) |

#### F-AUDIT-2 — Tracked Actions (18 types)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** The 18 named business action types are defined and emitted, with data_exported too. security_violation is defined but has no runtime producer. Check-in requests refused before persistence do not get checkin_attempted; standalone login/logout audit writes are best-effort on database failures. Code: [module2-backend/app/models.py:585](../module2-backend/app/models.py#L585); [module2-backend/app/audit.py:134](../module2-backend/app/audit.py#L134); [module2-backend/app/main.py:2493](../module2-backend/app/main.py#L2493) | [API-SPECIFICATION.md:1309](../docs/API-SPECIFICATION.md#L1309); [SECURITY-REQUIREMENTS.md:200](../docs/SECURITY-REQUIREMENTS.md#L200) |

#### F-PRIVACY-1 — Consent Tracking

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Consent fields default false and can be read/updated; enrollment/motion check camera consent and the UI requests explicit permissions. Full check-in requires both flags only when STRICT_SECURITY_MODE=true; default mode can approve with both false. Motion-proof consumption rechecks camera consent, but geolocation-consent enforcement remains strict-mode-only. Code: [module2-backend/app/models.py:64](../module2-backend/app/models.py#L64); [module2-backend/app/main.py:2360](../module2-backend/app/main.py#L2360); [module2-backend/app/motion.py:68](../module2-backend/app/motion.py#L68); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx) | [SECURITY-REQUIREMENTS.md:181](../docs/SECURITY-REQUIREMENTS.md#L181); [DATABASE-SCHEMA.md:274](../docs/DATABASE-SCHEMA.md#L274); [module1.md:106](../docs/module1.md#L106) |

#### F-PRIVACY-4 — Data Retention

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** scheduled_deletion_at columns exist, but check-in creation leaves them null. There is no user deletion-request workflow or scheduled expiry cleanup. Audit records are retained. Code: [module2-backend/app/models.py:100](../module2-backend/app/models.py#L100); [module2-backend/app/models.py:497](../module2-backend/app/models.py#L497); [module2-backend/app/main.py:2465](../module2-backend/app/main.py#L2465); [module2-backend/app/session_lifecycle.py](../module2-backend/app/session_lifecycle.py) | [SECURITY-REQUIREMENTS.md:188](../docs/SECURITY-REQUIREMENTS.md#L188); [DATABASE-SCHEMA.md:274](../docs/DATABASE-SCHEMA.md#L274) |

#### F-PRIVACY-5 — GDPR-like Principles

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Minimal biometric processing and explicit browser opt-ins exist. Right-to-deletion workflow/cleanup, limited coordinate precision and unconditional backend consent enforcement remain missing; complete compliance cannot be claimed. Code: [module2-backend/app/models.py](../module2-backend/app/models.py); [module2-backend/app/main.py:2351](../module2-backend/app/main.py#L2351); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx) | [SECURITY-REQUIREMENTS.md:163](../docs/SECURITY-REQUIREMENTS.md#L163); [DATABASE-SCHEMA.md:274](../docs/DATABASE-SCHEMA.md#L274); [module1.md:106](../docs/module1.md#L106) |

#### F-SEC-2 — Rate Limiting (Redis-backed)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** All four Redis-backed fixed-window limits, atomic increments/expiry and 429/Retry-After responses exist, but enforce_rate_limit immediately returns in default compatibility mode. Keys use saiv:limit:<category>:<hashed-identity>, differing from the PRD's illustrative key layout. Code: [module2-backend/app/security.py:47](../module2-backend/app/security.py#L47); [module2-backend/app/auth.py:127](../module2-backend/app/auth.py#L127); [module2-backend/app/main.py:173](../module2-backend/app/main.py#L173); [module2-backend/app/main.py:2351](../module2-backend/app/main.py#L2351) | [SECURITY-REQUIREMENTS.md:76](../docs/SECURITY-REQUIREMENTS.md#L76); [API-SPECIFICATION.md:1935](../docs/API-SPECIFICATION.md#L1935) |

#### F-SEC-4 — XSS Prevention

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Profile updates, appeals, review notes and invitation name handling escape markup, and React text rendering provides browser escaping. Registration, course/device input and their JSON serializers can still round-trip raw tags; the PRD's all-user-content API rule is not met. Code: [module2-backend/app/main.py:173](../module2-backend/app/main.py#L173); [module2-backend/app/main.py:452](../module2-backend/app/main.py#L452); [module2-backend/app/main.py:862](../module2-backend/app/main.py#L862); [module2-backend/app/main.py:2877](../module2-backend/app/main.py#L2877) | [SECURITY-REQUIREMENTS.md:155](../docs/SECURITY-REQUIREMENTS.md#L155) |

#### F-SEC-5 — Input Validation

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Email/password/numeric/timestamp and many enum validations exist, with safe 422 field lists. Most IDs are plain strings rather than UUIDv4 types; session_type and some status filters are unrestricted strings. Audit UUID filters are an exception. Code: [module2-backend/app/schemas.py](../module2-backend/app/schemas.py); [module2-backend/app/main.py:1698](../module2-backend/app/main.py#L1698); [module2-backend/app/audit.py:240](../module2-backend/app/audit.py#L240) | [SECURITY-REQUIREMENTS.md:141](../docs/SECURITY-REQUIREMENTS.md#L141) |

#### F-SEC-7 — Secret Management

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Database/Redis/JWT values are read from environment, and strict mode validates a 32-character non-placeholder JWT secret. The documented SECRET_KEY name is unused; Compose retains development credential/secret defaults, and token TTL/bcrypt/risk override names are not all honored. Code: [module2-backend/app/auth.py:25](../module2-backend/app/auth.py#L25); [module2-backend/app/security.py:17](../module2-backend/app/security.py#L17); [module2-backend/app/database.py:8](../module2-backend/app/database.py#L8); [docker-compose.yml](../docker-compose.yml) | [SECURITY-REQUIREMENTS.md:238](../docs/SECURITY-REQUIREMENTS.md#L238); [INTEGRATION-GUIDE.md:431](../docs/INTEGRATION-GUIDE.md#L431) |

#### F-SEC-8 — Error Message Hygiene

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Expected business errors use detail and validation errors redact sensitive values; Module 3 has a generic exception handler and safe telemetry. Module 2 lacks an equivalent global JSON exception handler/correlation policy; unhandled failures can produce non-JSON 500 responses. Code: [module2-backend/app/main.py:110](../module2-backend/app/main.py#L110); [module2-backend/app/checkin_diagnostics.py](../module2-backend/app/checkin_diagnostics.py); [module3-face-recognition/app/main.py:165](../module3-face-recognition/app/main.py#L165) | [module2.md:111](../docs/module2.md#L111); [API-SPECIFICATION.md:1874](../docs/API-SPECIFICATION.md#L1874) |

#### F-FE-2 — Authentication UI

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Register/login/logout, memory access tokens, HttpOnly refresh and 401 retry exist. Structured backend 422 errors collapse to a generic client message; failed final refresh/retry does not consistently reset Home's existing user state to show login immediately. Code: [module1-frontend/components/auth/AuthCard.tsx](../module1-frontend/components/auth/AuthCard.tsx); [module1-frontend/lib/api/client.ts](../module1-frontend/lib/api/client.ts); [module1-frontend/app/page.tsx](../module1-frontend/app/page.tsx) | [module1.md:65](../docs/module1.md#L65); [INTEGRATION-GUIDE.md:62](../docs/INTEGRATION-GUIDE.md#L62); [INTEGRATION-GUIDE.md:155](../docs/INTEGRATION-GUIDE.md#L155) |

#### F-FE-3 — Camera Capture (WebRTC)

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Front-camera/resolution capture, video/canvas JPEG export and prefix stripping exist; tracks stop on submit success, logout, backgrounding or unmount. They remain live during the post-capture review/submission step, rather than stopping immediately when capture completes. Code: [module1-frontend/features/camera/useCamera.ts](../module1-frontend/features/camera/useCamera.ts); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx); [module1-frontend/components/check-in/FaceVerification.tsx](../module1-frontend/components/check-in/FaceVerification.tsx) | [module1.md:25](../docs/module1.md#L25); [module1.md:45](../docs/module1.md#L45) |

#### F-FE-7 — Device Fingerprinting

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** A SHA-256 fingerprint of browser/device attributes accompanies each submission, but the active frontend never calls POST /devices/register. There is no persistent per-install key/identifier, and display/browser changes can change the fingerprint. Code: [module1-frontend/lib/device.ts](../module1-frontend/lib/device.ts); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx); [module1-frontend/lib/api/checkins.ts](../module1-frontend/lib/api/checkins.ts) | [API-SPECIFICATION.md:1071](../docs/API-SPECIFICATION.md#L1071); [INTEGRATION-GUIDE.md:112](../docs/INTEGRATION-GUIDE.md#L112); [DATABASE-SCHEMA.md:130](../docs/DATABASE-SCHEMA.md#L130) |

#### F-FE-8 — Check-In Workflow

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Session selection, camera/location/verification, real-time submit and status/risk result are connected. Location precedes liveness capture; rejected/flagged result text is generic and offers no direct appeal action or factor-specific explanation. Appeals exist separately in Module 4 history. Code: [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx); [module4-observability/src/components/dashboard/CourseHistory.tsx](../module4-observability/src/components/dashboard/CourseHistory.tsx) | [INTEGRATION-GUIDE.md:112](../docs/INTEGRATION-GUIDE.md#L112); [API-SPECIFICATION.md:606](../docs/API-SPECIFICATION.md#L606); [API-SPECIFICATION.md:792](../docs/API-SPECIFICATION.md#L792) |

#### F-FE-9 — Mobile Browser Support

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Verification pending.** Responsive layout, playsInline video, secure-context checks and unsupported/denied fallbacks exist. This audit did not exercise real iOS/Android browsers, cameras or physical GPS, so complete mobile compatibility remains unverified. Code: [module1-frontend/app/globals.css](../module1-frontend/app/globals.css); [module1-frontend/features/camera/useCamera.ts](../module1-frontend/features/camera/useCamera.ts); [module1-frontend/features/geolocation/useGeolocation.ts](../module1-frontend/features/geolocation/useGeolocation.ts) | [module1.md:25](../docs/module1.md#L25) |

#### F-FE-10 — Error and Rate-Limit Handling

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Forms retain state and show network/time-out errors; offline sessions are explicitly read-only. ApiError does not retain Retry-After and the UI has no header-driven wait/countdown behavior for 429. Code: [module1-frontend/lib/api/client.ts](../module1-frontend/lib/api/client.ts); [module1-frontend/components/auth/AuthCard.tsx](../module1-frontend/components/auth/AuthCard.tsx); [module1-frontend/components/check-in/StudentDashboard.tsx](../module1-frontend/components/check-in/StudentDashboard.tsx) | [INTEGRATION-GUIDE.md:155](../docs/INTEGRATION-GUIDE.md#L155); [API-SPECIFICATION.md:1935](../docs/API-SPECIFICATION.md#L1935) |

#### F-DASH-2 — Session Management Interface

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Sessions UI creates/edits/deletes scheduled sessions, closes/cancels active sessions and shows a calendar. Automatic backend activation is implemented, but no prominent manual activate control is present as required by this PRD feature. Code: [module4-observability/src/components/dashboard/SessionsPanel.tsx](../module4-observability/src/components/dashboard/SessionsPanel.tsx); [module4-observability/src/components/dashboard/SessionCalendar.tsx](../module4-observability/src/components/dashboard/SessionCalendar.tsx); [module2-backend/app/session_lifecycle.py](../module2-backend/app/session_lifecycle.py) | [API-SPECIFICATION.md:490](../docs/API-SPECIFICATION.md#L490); [API-SPECIFICATION.md:531](../docs/API-SPECIFICATION.md#L531); [module4.md:3](../docs/module4.md#L3) |

#### F-DASH-3 — Live Attendance Monitoring

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Selected-session roster/live polling shows student identity, timestamp, attendance/verification status and risk. Distance is stored/exposed by backend check-in APIs but absent from the live roster/table/detail display. Code: [module4-observability/src/components/dashboard/InstructorCheckIns.tsx](../module4-observability/src/components/dashboard/InstructorCheckIns.tsx); [module4-observability/src/components/dashboard/AttendanceTable.tsx](../module4-observability/src/components/dashboard/AttendanceTable.tsx); [module4-observability/src/lib/checkin-roster.ts](../module4-observability/src/lib/checkin-roster.ts) | [API-SPECIFICATION.md:733](../docs/API-SPECIFICATION.md#L733); [API-SPECIFICATION.md:549](../docs/API-SPECIFICATION.md#L549); [module4.md:52](../docs/module4.md#L52) |

#### F-DASH-4 — Flagged Review Workflow

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Instructor review filters, appeal text and approve/reject-with-notes calls are connected. Risk-factor detail is rendered only for appealed records, not ordinary flagged records. TA's generic CheckInsPanel has no review actions despite backend TA review support. Code: [module4-observability/src/components/dashboard/InstructorCheckIns.tsx:396](../module4-observability/src/components/dashboard/InstructorCheckIns.tsx#L396); [module4-observability/src/components/dashboard/TaView.tsx](../module4-observability/src/components/dashboard/TaView.tsx); [module4-observability/src/components/dashboard/CheckInsPanel.tsx](../module4-observability/src/components/dashboard/CheckInsPanel.tsx) | [API-SPECIFICATION.md:755](../docs/API-SPECIFICATION.md#L755); [API-SPECIFICATION.md:817](../docs/API-SPECIFICATION.md#L817); [module4.md:93](../docs/module4.md#L93) |

#### F-DASH-5 — Analytics and Charts

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Attendance cards, risk categories, timeline bars and scrolling sortable tables exist. Trends use bars and merge equal hours across dates; course average risk rounds the raw 0-1 value without percentage scaling. Full labelled time-series/zero-axis requirements are not satisfied. Code: [module4-observability/src/components/dashboard/CheckInTrend.tsx](../module4-observability/src/components/dashboard/CheckInTrend.tsx); [module4-observability/src/components/dashboard/MetricsPanel.tsx](../module4-observability/src/components/dashboard/MetricsPanel.tsx); [module4-observability/src/components/dashboard/InstructorView.tsx:71](../module4-observability/src/components/dashboard/InstructorView.tsx#L71); [module4-observability/src/lib/attendance.ts:282](../module4-observability/src/lib/attendance.ts#L282) | [module4.md:28](../docs/module4.md#L28); [API-SPECIFICATION.md:951](../docs/API-SPECIFICATION.md#L951) |

#### F-DASH-6 — Information Hierarchy

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Summary cards, review counts and drill-down tabs provide a hierarchy. Instructor Overview counts all loaded sessions/attendance rather than prioritizing today's sessions, and it exposes technical Metrics/Audit tabs even though audit access is admin-only. Code: [module4-observability/src/components/dashboard/InstructorView.tsx](../module4-observability/src/components/dashboard/InstructorView.tsx); [module4-observability/src/components/dashboard/SessionsPanel.tsx](../module4-observability/src/components/dashboard/SessionsPanel.tsx) | [module4.md:3](../docs/module4.md#L3); [module4.md:93](../docs/module4.md#L93) |

#### F-OPS-1 — Health Endpoints

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Backend and face /health return healthy, and backend /db-health separately probes SQL. Backend /health never checks database/Redis or returns dependency-based 503; frontend/dashboard have no dedicated /health handler. Reachable application pages are not dependency health checks. Code: [module2-backend/app/main.py:162](../module2-backend/app/main.py#L162); [module3-face-recognition/app/main.py:181](../module3-face-recognition/app/main.py#L181); [module1-frontend/app](../module1-frontend/app); [module4-observability/src/routes](../module4-observability/src/routes) | [INTEGRATION-GUIDE.md:462](../docs/INTEGRATION-GUIDE.md#L462) |

#### F-OPS-3 — Distributed Tracing

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Module 3 instruments FastAPI and exports OTLP traces when configured; collector receivers/pipeline exist. Module 2 has no OpenTelemetry provider/exporter or outgoing HTTP trace propagation, so a linked cross-service check-in trace is missing. Code: [module3-face-recognition/app/telemetry.py:270](../module3-face-recognition/app/telemetry.py#L270); [module2-backend/app/checkin_diagnostics.py](../module2-backend/app/checkin_diagnostics.py); [module2-backend/app/face_service.py](../module2-backend/app/face_service.py); [module4-observability/otel-collector-config.yml](../module4-observability/otel-collector-config.yml) | [INTEGRATION-GUIDE.md:7](../docs/INTEGRATION-GUIDE.md#L7); [INTEGRATION-GUIDE.md:431](../docs/INTEGRATION-GUIDE.md#L431); [module4.md:73](../docs/module4.md#L73) |

#### F-OPS-4 — Grafana Dashboards

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Grafana service, Prometheus datasource and file-provider configuration exist. No dashboard JSON files are included or mounted for latency/error/throughput/risk panels; provisioning a provider alone does not create those dashboards. Code: [docker-compose.yml](../docker-compose.yml); [module4-observability/grafana/provisioning/datasources.yml](../module4-observability/grafana/provisioning/datasources.yml); [module4-observability/grafana/provisioning/dashboards.yml](../module4-observability/grafana/provisioning/dashboards.yml) | [module4.md:73](../docs/module4.md#L73); [INTEGRATION-GUIDE.md:324](../docs/INTEGRATION-GUIDE.md#L324); [Briefing.md:318](../docs/Briefing.md#L318) |

#### F-OPS-6 — Docker Deployment

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Dockerfiles and Compose include every named service/port, named data volumes, same-origin client proxies and Redis health dependencies. Backend requires externally supplied DATABASE_URL and does not depend on healthy local Postgres; the PRD's self-contained local database startup/wait behavior is incomplete. No full-stack restart was performed. Code: [docker-compose.yml](../docker-compose.yml); [module1-frontend/Dockerfile](../module1-frontend/Dockerfile); [module2-backend/Dockerfile](../module2-backend/Dockerfile); [module3-face-recognition/Dockerfile](../module3-face-recognition/Dockerfile); [module4-observability/Dockerfile](../module4-observability/Dockerfile) | [INTEGRATION-GUIDE.md:7](../docs/INTEGRATION-GUIDE.md#L7); [INTEGRATION-GUIDE.md:431](../docs/INTEGRATION-GUIDE.md#L431); [Briefing.md:318](../docs/Briefing.md#L318) |

#### F-OPS-7 — Database Migrations

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Missing.** There is no Alembic configuration, revisions directory, upgrade or downgrade workflow. Startup uses Base.metadata.create_all, which does not migrate existing schemas. Code: [module2-backend/app/main.py:85](../module2-backend/app/main.py#L85); [module2-backend/app/database.py](../module2-backend/app/database.py) | [DATABASE-SCHEMA.md:257](../docs/DATABASE-SCHEMA.md#L257) |

#### F-PERF-1 — Latency Budgets

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Verification pending.** The current public latency checks passed on disposable SQLite. Their check-in payload has no real biometric image, so it does not establish the under-two-second full face-service round trip. Native face/model and deployed database/network latency budgets remain unverified here. Code: [tests/public/test_performance.py](../tests/public/test_performance.py); [tests/public/test_integration.py](../tests/public/test_integration.py); [module2-backend/app/face_service.py](../module2-backend/app/face_service.py) | [Briefing.md:570](../docs/Briefing.md#L570); [DATABASE-SCHEMA.md:284](../docs/DATABASE-SCHEMA.md#L284); [INTEGRATION-GUIDE.md:188](../docs/INTEGRATION-GUIDE.md#L188) |

#### F-PERF-2 — Concurrency

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Verification pending.** Admission control, bounded pools and duplicate-race handling exist; current public login/integration concurrency passed. The 20-check-in public case is pre-skipped. Prior 23 October evidence records 100 successful PostgreSQL check-ins, but excludes simultaneous bcrypt/native face work and was not rerun today; full stress acceptance remains unverified. Code: [module2-backend/app/admission.py](../module2-backend/app/admission.py); [module2-backend/app/database.py](../module2-backend/app/database.py); [new-tests/run_concurrency_audit.py](../new-tests/run_concurrency_audit.py); [docs/audits/2026-10-23-hidden-category-audit.md](../docs/audits/2026-10-23-hidden-category-audit.md) | [Briefing.md:587](../docs/Briefing.md#L587); [DATABASE-SCHEMA.md:284](../docs/DATABASE-SCHEMA.md#L284) |

#### F-PERF-3 — Query Efficiency

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Core course/session/check-in pages batch joins/counts and relevant latency checks passed. Own-enrollment listing still queries each course/instructor in a loop; sessions.instructor_id lacks its FK index and checkins.device_id has no FK. PostgreSQL pool is size 3/overflow 0, not the specified 10/20. Code: [module2-backend/app/main.py:1364](../module2-backend/app/main.py#L1364); [module2-backend/app/main.py:933](../module2-backend/app/main.py#L933); [module2-backend/app/main.py:2615](../module2-backend/app/main.py#L2615); [module2-backend/app/models.py:294](../module2-backend/app/models.py#L294); [module2-backend/app/database.py:14](../module2-backend/app/database.py#L14) | [DATABASE-SCHEMA.md:284](../docs/DATABASE-SCHEMA.md#L284) |

#### F-PERF-4 — Pagination

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Sessions, users, global/flagged check-ins, course/device directories and audits paginate correctly. Own devices, own enrollments, course enrollment roster and session check-in roster do not accept limit/offset; thus the PRD's every-list requirement is incomplete. Code: [module2-backend/app/main.py:1364](../module2-backend/app/main.py#L1364); [module2-backend/app/main.py:1396](../module2-backend/app/main.py#L1396); [module2-backend/app/main.py:2615](../module2-backend/app/main.py#L2615); [module2-backend/app/main.py:3072](../module2-backend/app/main.py#L3072); [module2-backend/app/audit.py:240](../module2-backend/app/audit.py#L240) | [API-SPECIFICATION.md:1968](../docs/API-SPECIFICATION.md#L1968); [API-SPECIFICATION.md:1098](../docs/API-SPECIFICATION.md#L1098); [API-SPECIFICATION.md:1143](../docs/API-SPECIFICATION.md#L1143); [API-SPECIFICATION.md:733](../docs/API-SPECIFICATION.md#L733) |

#### F-API-2 — Status Code Discipline

| Status, finding and code evidence | Specification in `docs/` |
| --- | --- |
| **Partial.** Normal CRUD/business/validation/status codes match the API and current public checks. Anonymous courses return 200 instead of an auth error; Module 2 unhandled errors lack the required detail envelope, and dependency failures are not reflected by /health. Code: [module2-backend/app/main.py:162](../module2-backend/app/main.py#L162); [module2-backend/app/main.py:887](../module2-backend/app/main.py#L887); [module2-backend/app/main.py:110](../module2-backend/app/main.py#L110); [module2-backend/app/auth.py:19](../module2-backend/app/auth.py#L19) | [API-SPECIFICATION.md:1874](../docs/API-SPECIFICATION.md#L1874); [module2.md:27](../docs/module2.md#L27) |

## Cross-cutting data requirements (PRD §4)

These rows assess the PRD's table-level requirements in addition to the feature lists; they are not extra feature IDs.

| Table / invariant | Current implementation and remaining gap | Specification in `docs/` |
| --- | --- | --- |
| `users` | UUID-string key, unique email, role/activity indexes, bcrypt hash, false-default consent, 64-character template and retention columns exist. Login/retention timestamps are not maintained as required. | [DATABASE-SCHEMA.md — users](../docs/DATABASE-SCHEMA.md#users) |
| `courses` | Metadata, unique code, semester/activity indexes, venue and security policy fields exist. | [DATABASE-SCHEMA.md — courses](../docs/DATABASE-SCHEMA.md#courses) |
| `enrollments` | Membership FKs/indexes and the unique student/course index exist; drop/reactivate lifecycle preserves history. | [DATABASE-SCHEMA.md — enrollments](../docs/DATABASE-SCHEMA.md#enrollments) |
| `sessions` | UUID key, course/instructor references, status/time/window indexes and QR placeholders exist. Instructor FK is not indexed; session type is a free string. | [DATABASE-SCHEMA.md — sessions](../docs/DATABASE-SCHEMA.md#sessions) |
| `devices` | Unique fingerprint and owner/activity/trust indexes exist. Public key and creation time are nullable despite documented NOT NULL constraints; attestation token column and maintained rotation/revocation state are missing. | [DATABASE-SCHEMA.md — devices](../docs/DATABASE-SCHEMA.md#devices) |
| `checkins` | Unique session/student index, key filter indexes and biometric/review/appeal fields exist. `device_id` lacks its documented FK; retention is not populated and coordinates are not reduced in precision. | [DATABASE-SCHEMA.md — checkins](../docs/DATABASE-SCHEMA.md#checkins) |
| `risk_signals` | Missing ORM model, table definition, indexes and persistence path. A JSON field on `checkins` does not satisfy the normalized table requirement. | [DATABASE-SCHEMA.md — risk signals](../docs/DATABASE-SCHEMA.md#risk_signals) |
| `audit_logs` | Required indexed event metadata, no updated_at and application-level append-only guards exist. Database privilege/trigger enforcement was not verified. | [DATABASE-SCHEMA.md — audit logs](../docs/DATABASE-SCHEMA.md#audit_logs) |
| Additional data models | Course assistants, venues, invitation/outbox and optional motion metadata are present; they do not replace the eight required core tables. Motion/invitation extensions have specifications in current docs. | [DATABASE-SCHEMA.md — optional motion metadata](../docs/DATABASE-SCHEMA.md#optional-motion-metadata-tables); [account invitations](../docs/DATABASE-SCHEMA.md#account-invitations-and-durable-email-outboxadded-by-ishita) |
| Privacy invariants | No raw biometric/BLOB storage path was found in the relevant processing/models. Non-invertibility of deterministic SimHash templates, encryption at rest and deletion guarantees were not proven. | [DATABASE-SCHEMA.md — privacy](../docs/DATABASE-SCHEMA.md#privacy-requirements); [SECURITY-REQUIREMENTS.md — biometric data](../docs/SECURITY-REQUIREMENTS.md#biometric-data) |

## Specification gaps and discrepancies

| Topic | PRD / documentation / implementation discrepancy |
| --- | --- |
| Session activation and deletion | PRD F-SESSION-2 describes manual lifecycle transitions, and F-DASH-2 requires a visible activation control. Current [session PATCH documentation](../docs/API-SPECIFICATION.md#patch-sessionssession_id) additionally mandates automatic schedule transitions, which code implements. No manual activation UI exists. [Deletion docs](../docs/API-SPECIFICATION.md#delete-sessionssession_id) allow admins as well as owning instructors, agreeing with the PRD matrix but broader than F-SESSION-3's isolated wording. |
| Session-create name | [POST sessions example](../docs/API-SPECIFICATION.md#post-sessions) uses `session_name`; the PRD, code, client and tests use `name`. |
| Session and course detail scope | PRD F-SESSION-7 describes full details for any authenticated user; [current docs](../docs/API-SPECIFICATION.md#get-sessionssession_id) restrict enrollment/ownership. Code returns schedule-only metadata to ineligible students. Course list/detail similarly redact student catalog entries despite the [full course contract](../docs/API-SPECIFICATION.md#get-courses). |
| Flagged-queue shape | PRD F-CHECKIN-6/F-API-3 and tests require a paginated envelope; the [API example](../docs/API-SPECIFICATION.md#get-checkinsflagged) still shows a bare array. Code returns the envelope. |
| Check-in detail signals | PRD F-CHECKIN-7 requires associated risk signals; [current API text](../docs/API-SPECIFICATION.md#get-checkinscheckin_id) explicitly excludes risk factors from detail. Code follows that exclusion. Review consumers must obtain factors from the queue/session roster. |
| Permission matrix | PRD F-RBAC-2 allows every role on own-history and broadly permits TA access to statistics/global check-ins. The [endpoint-specific documentation](../docs/API-SPECIFICATION.md#check-ins) and implementation are narrower in places. Course assignments, current database role authority and TA assignment rows also go beyond the PRD's simple JWT-role wording. |
| JWT claims and configuration | [Security requirements](../docs/SECURITY-REQUIREMENTS.md#jwt-tokens) require `SECRET_KEY`, `sub`, `email` and `iat`; [module2.md](../docs/module2.md) illustrates `user_id/role/exp`. Code uses `JWT_SECRET` and `user_id/role/type/exp`; optional TTL/bcrypt/risk environment settings are not consistently honored. |
| Default security mode | [Rate limits](../docs/SECURITY-REQUIREMENTS.md#rate-limiting) and [consent requirements](../docs/SECURITY-REQUIREMENTS.md#consent-tracking) are unconditional in the PRD/docs, but backend rate limiting/full check-in consent enforcement are opt-in. Strict-mode public student-only registration conflicts with the PRD's face-value role registration contract. |
| Risk decisions | [API check-in status logic](../docs/API-SPECIFICATION.md#post-checkins) flags high aggregate risk unless a named critical signal forces rejection. [Security risk levels](../docs/SECURITY-REQUIREMENTS.md#risk-levels) instead say risk ≥0.7 is auto-rejected. Code follows the API-style hard-rejection rules. Backend max-fusion and positive in-radius geo risk are not the PRD's full weighted/zero-in-radius behavior. |
| Device keys and revocation | [Database device schema](../docs/DATABASE-SCHEMA.md#devices) requires a non-null public key/creation time and provides revocation fields; code makes keys/timestamps optional and hard-deletes devices. The [DELETE API](../docs/API-SPECIFICATION.md#delete-devicesdevice_id) says “remove” without specifying preservation, while the PRD explicitly requires revocation metadata. |
| Dashboard implementation | [Integration examples](../docs/INTEGRATION-GUIDE.md#module-4-dashboard--module-2-backend) use Streamlit/direct SQL. Current Module 4 is React/Vite with authenticated HTTP calls. The PRD permits framework freedom, so this technology difference alone is not treated as missing functionality. |
| Biometric hash guarantees | [Security/database docs](../docs/SECURITY-REQUIREMENTS.md#biometric-data) say SHA-256; PRD F-FACE-4 expressly allows SimHash because similarity is needed. Code emits deterministic 256-bit SimHash-derived templates. “Hash-only” is not proof of cryptographic non-invertibility or encryption. |
| Performance/pagination wording | [Database guidance](../docs/DATABASE-SCHEMA.md#performance-optimization) specifies 10+20 pool capacity; implementation intentionally bounds PostgreSQL connections to 3+0. Generic [pagination guidance](../docs/API-SPECIFICATION.md#pagination) and PRD F-PERF-4 are broader than several endpoint-specific array/roster contracts. |
| Numeric policies not specified | Geo accuracy warning uses accuracy greater than the venue radius; low-attendance alerts use 75%; timeline buckets use five minutes. The PRD/docs do not fully define accuracy severity/weight, low-attendance cutoff or all rate denominators. `stats.py` counts a check-in of any verification status as attendance; the newer roster computes attendance independently from verification and enrollment history. |
| Audit extensions | [Audit docs](../docs/API-SPECIFICATION.md#audit-logs) enumerate 18 actions; PRD adds `data_exported` and `security_violation`. The summary route and admin all-device directory are PRD requirements without equally detailed dedicated endpoint entries in current API docs; their rows therefore cite the closest security/schema sections. |

## Checks run and results

All new traffic/data created for this audit used disposable local SQLite or temporary containers. Existing application containers were not restarted or reconfigured. Native model checks used a fresh container with no network, a read-only root filesystem/repository mount and a temporary `/tmp`; no new dependencies were installed.

| Check | Result and scope |
| --- | --- |
| Repository inventory/source review | Read PRD feature definitions and relevant `docs`, all four modules, route registration, schemas/models, client adapters, dashboards, PWA worker and deployment/monitoring configuration. Reviewed prior reports only as explicitly dated supplementary evidence. |
| Backend HTTP/regression suites | **312 passed, 1 skipped** in 57.72 seconds. Command uses `venv/bin/python new-tests/run_session_regressions.py` with the seven public backend/security/privacy/observability/frontend-contract/performance/integration files, `module2-backend/tests/test_stats_metrics.py`, and five regression files: missing endpoints, session deletion, appeal contract, instructor strict scope and session read scope. Exact targets are listed below. The skipped test is the public concurrent-check-in test. |
| Security/admission tests | **26 passed** in 1.87 seconds: `venv/bin/python -m pytest -q -p no:cacheprovider new-tests/test_advanced_security_audit.py new-tests/test_database_admission.py`. Redis behavior is mocked in this run, so it does not replace the earlier real-Redis audit. |
| Native face/motion tests | **40 passed** in 5.65 seconds: existing face image, privacy, attestation, score, temporal sequence and native static-photo/model-failure regressions. Used the existing face-service image, source mounted at `/workspace:ro`, running `python -m pytest -q -p no:cacheprovider new-tests/test_face_module3.py new-tests/test_motion_sequence.py new-tests/test_motion_native.py`. |
| Frontend/dashboard Node checks | Initial broad run: **90 passed, 10 failed**. Three failures require a running proxy but the test container had networking disabled; five file-level failures require missing `react-test-renderer`, `fake-indexeddb` or the precompiled `/private/tmp/saiv-frontend-time-check/time.js` fixture. Two test/source mismatches remain: the history harness overwrites its captured history query with the newer second sessions query, then fails on `query.placeholderData`; the overview test expects an anchor calling the old attendance callback, while the current button opens the calendar. These failures need test/behavior reconciliation and do not establish a reproduced browser defect. Application and existing test files were left unchanged. |
| Targeted behavior probes | Disposable SQLite/TestClient confirmed missing register/profile timestamps; access claim names and unchanged last_login_at; anonymous courses 200/active sessions []; invalid session_type accepted; closed→active PATCH accepted; default check-in approval without consent/device binding; null retention time; absent detail risk factors/roster device trust/QR-enabled field; hard-deleted device; instructor own-history 403; positive in-radius geo risk. |
| Initial host-runtime attempts | `.venv` is Python 3.9 and could not collect modern type annotations/dataclass options. Retried with existing Python 3.12 `venv`. Host native face run then produced **28 passed, 6 failed, 6 errors** because face-recognition/dlib was unavailable; the isolated native-runtime retry above passed all 40. The first local-port attempt was sandbox-blocked and was retried successfully with approved local-port access. These are environment/setup failures, not counted as feature regressions. |
| Existing real-world replay evidence | [24 October phone replay report](test-logs/phone-replay-test.md): participant-reported static phone-screen presentation passed passive liveness and attendance. It is one observed false acceptance, not an attack-success-rate estimate. Not rerun during this audit. |
| Existing load evidence | [23 October audit](../docs/audits/2026-10-23-hidden-category-audit.md): 100/100 own-profile reads and distinct-student check-ins passed on disposable PostgreSQL. It excluded account setup/password hashing and native face analysis from the timed window; not rerun during this audit. |
| PRD/link/format checks | Every PRD F-ID is present exactly once; category totals reconcile; all relative file targets exist; source/spec line references and formatting checked. Passed: 124/124 unique feature IDs, 622 valid relative link targets, 22 area totals reconciled and `git diff --check` clean. |

Backend runner targets:

```text
tests/public/test_api_functional.py
tests/public/test_security_basic.py
tests/public/test_privacy_basic.py
tests/public/test_observability.py
tests/public/test_frontend_dashboard.py
tests/public/test_performance.py
tests/public/test_integration.py
module2-backend/tests/test_stats_metrics.py
new-tests/test_missing_endpoints.py
new-tests/test_session_deletion.py
new-tests/test_appeal_contract.py
new-tests/test_instructor_strict_scope.py
new-tests/test_session_read_scope.py
```

The automated suites do not prove full conformance: the disposable probes demonstrate requirements missed by their current assertions. Real mobile permissions/GPS, broad attack-corpus accuracy, linked distributed traces, dependency-outage health, retention cleanup, deployed-network latency and a fresh full-stack load/deployment acceptance run remain unverified or incomplete as listed above.

## Change scope

- **Files changed:** `new-documentations/list-of-features-26OCT.md` only.
- **Endpoints implemented or reused:** none added or changed. Existing authentication, users, courses, sessions, enrollments, devices, check-in/history/appeal/review, statistics, audit, export, face/motion and metrics endpoints were inspected or exercised on disposable fixtures.
- **Specification gaps:** recorded per feature and in the discrepancy table; `docs/` remains read-only.
- **Checks:** source/document traceability, backend/security/native-face/Node suites and targeted probes, with limitations recorded above.
