# Codebase inspection against `docs`

Inspection date: **3 November 2026, Asia/Singapore**. Source revision: `5dbb4848f11ca0961d2fce3f923adc7c94d91f2e`.

The application implements the main attendance workflow and has handlers for **all 64 explicitly documented API routes: 56 backend routes and 8 face-service routes**, including the optional device-attestation endpoint. Route presence does not establish contract compliance. Several requirements are missing, disabled in the default configuration, or inconsistent with the documented behavior.

The most consequential gaps are default-disabled rate limits and consent enforcement, missing independent check-in retention, incomplete fraud-signal integration, and audit immutability that can be bypassed through bulk database operations. There are also API field/filter mismatches and requirements that conflict with other documents or recent implementation decisions.

This inspection changes documentation only. It does not implement fixes, change application settings, or modify `docs`.

## Scope, evidence, and interpretation

Reviewed all 11 files under `docs`, the four application modules, Docker/service configuration, and the relevant public and additional tests. The evidence file contains SHA-256 fingerprints for the inspected documents, the complete route inventory with implementation locations, and isolated behavioral observations:

- [Machine-readable inspection evidence](inspection/requirements-inspection-2026-11-03-evidence.json)
- [API specification](../docs/API-SPECIFICATION.md)
- [Database schema](../docs/DATABASE-SCHEMA.md)
- [Security requirements](../docs/SECURITY-REQUIREMENTS.md)
- [Integration guide](../docs/INTEGRATION-GUIDE.md)
- [Briefing](../docs/Briefing.md)
- Module guidance: [frontend](../docs/module1.md), [backend](../docs/module2.md), [face recognition](../docs/module3.md), [dashboard](../docs/module4.md)
- Historical evidence: [23 October audit](../docs/audits/2026-10-23-hidden-category-audit.md) and its [JSON results](../docs/audits/2026-10-23-audit-evidence.json)

Classification used below:

| Classification | Meaning |
| --- | --- |
| Implemented | A concrete implementation exists; any fresh runtime verification is identified separately. |
| Partial | Some required behavior exists, but a material part is missing or conditional. |
| Missing | No implementing path was found, supported by the cited code/search or a probe. |
| Contract mismatch | Existing behavior differs from a documented request, response, or rule. |
| Specification conflict | Documents prescribe incompatible behavior, or describe an older implementation. Resolve the intended contract before changing code. |
| Unverified | The current environment or available data did not permit a reliable runtime conclusion. |

Endpoint-specific contracts take precedence over generic examples when they are explicit. Technology suggestions, development timelines, and course administration/presentation requirements are not treated as missing application features. Liveness is explicitly a **bonus** in the API specification; device attestation and push notifications are optional. HTTP-only deployment is explicitly permitted by the security/API documents.

All new behavioral probes used disposable SQLite data and in-process FastAPI clients. The public HTTP tests used a separate temporary SQLite backend. Neither the configured application database nor an external account was inspected or mutated. A single face-client call was stubbed to inspect the fields sent to risk assessment; this is payload inspection, not model validation. Fresh-schema conclusions do not establish what constraints or legacy tables an independently administered deployment might contain.

## Missing and partial requirements

### G01 — Required rate limits are disabled by default — high priority, partial

**Requirement:** Security/API rate limiting specifies registration 10/hour/IP, login 60/hour/IP, authenticated API 1,000/hour/user, and check-ins 10/minute/user, using Redis.

**Implementation:** [security.py:48](../module2-backend/app/security.py#L48) returns immediately from `enforce_rate_limit` unless strict mode is enabled. [Compose](../docker-compose.yml) defaults `STRICT_SECURITY_MODE` to false. Call sites exist, and the strict-mode tests pass, but default deployments do not enforce the required limits. An isolated probe called the registration limiter 11 times with the same identity without an exception.

**Remaining work:** Make the required limits effective under the intended default contract and verify them with real Redis. Simply enabling all strict-mode behavior changes public staff/admin registration, which the briefing and API explicitly permit; that conflict needs a separate decision.

### G02 — Backend consent enforcement is conditional — high priority, partial

**Requirement:** The briefing requires both consent flags before check-in; security requirements require consent before collecting biometric/location data.

**Implementation:** The PWA guides consent, and backend face enrollment and motion challenges check camera consent. However, [create_checkin:2360](../module2-backend/app/main.py#L2360) checks both consent flags only in strict mode. A student with both flags false submitted coordinates and no image and received `201` with a persisted **flagged** record. The record was not approved; `identity_unverified` correctly identifies the missing required evidence.

**Remaining work:** Enforce the chosen consent policy at the API boundary in normal operation. Clarify the intentional compatibility behavior for missing required biometric evidence: default mode flags it, while strict mode refuses the submission. The integration guide's fail-open example conflicts with stronger interpretations of required verification.

### G03 — Independent 30-day check-in retention is missing — high priority, missing

**Requirement:** Security requirements specify 30-day check-in retention; the schema supplies `checkins.scheduled_deletion_at`; the briefing describes automatic deletion.

**Implementation:** [Check-in creation](../module2-backend/app/main.py#L2490) never assigns the deletion field. [purge_due_students:77](../module2-backend/app/data_deletion.py#L77) removes records only when an explicitly scheduled student-account deletion is due. It does not independently sweep expired check-ins. A probe set a record to 40 days old with a deletion deadline 10 days in the past; it survived that cleanup function.

**Implemented portion:** Password-confirmed student deletion requests, cancellation, the background cleanup task, and audit-preserving anonymization exist; their five targeted regression tests passed. This is a separate lifecycle from automatic check-in expiry. Equivalent self-service deletion for staff roles is not implemented; the documents do not clearly scope whether all user roles need it.

### G04 — Location precision is not minimized — high priority, contract mismatch

**Requirement:** Briefing, “Privacy: Data Handling Rules,” says location is used for geofencing and stored with limited precision.

**Implementation:** [create_checkin](../module2-backend/app/main.py#L2490) writes and returns the submitted latitude/longitude unchanged. The probe retained `1.348312345678, 103.683112345678` exactly. Authorized check-in list/detail responses also expose coordinates.

**Remaining work:** Define the permitted precision, storage purpose, and retention policy before implementing minimization. The API's examples themselves include coordinates, so a blanket prohibition on all location storage would conflict with the API.

### G05 — Fraud-signal integration is incomplete — high priority, partial

**Requirement:** The briefing calls for impossible-travel/GPS-spoofing detection; security risk scoring includes network and device signals; the schema enumerates geographic, network, device, behavioral, liveness, and face signals.

**Implementation:** [risk.py](../module3-face-recognition/app/risk.py) implements five weighted categories and IP/user-agent heuristics. However, [the backend biometric path:2227](../module2-backend/app/main.py#L2227) sends scores and geolocation without the request IP or user agent. It calls `/risk/assess` only when a biometric score is available. The probe observed only `geolocation` and `liveness_score` for a liveness-only request. [Motion consumption](../module2-backend/app/motion.py#L217) computes risk locally from the two scores instead of collecting network/history signals. Device proof risk is integrated separately.

No implementing backend path was found for comparing earlier locations/times to detect impossible travel, or for the listed `rapid_succession`, `unusual_time`, and `pattern_anomaly` signals. Browser-provided coordinates are range/distance/accuracy checked, but their authenticity is not established. The network helper is heuristic; it is not a verified VPN/Tor/proxy intelligence integration.

**Remaining work:** Connect server-observed request context and historical signals to the actual attendance decision, specify signal thresholds, and validate real spoofing/replay cases. Enumerating a signal in the frontend label map does not implement detection.

### G06 — The required `risk_signals` table is absent — medium priority, missing

**Requirement:** Database schema specifies a normalized `risk_signals` table with check-in FK, type, severity, confidence, details, weight, and detection time.

**Implementation:** No mapped `RiskSignal` model exists. Fresh startup creates seven of the eight main tables; risk factors are stored as JSON text on `checkins` instead. The cleanup code's conditional handling of an externally existing `risk_signals` table does not create or populate it.

**Remaining work:** Implement the documented table and persistence, or explicitly agree that the JSON representation replaces that requirement. Existing scalar risk factors and API explanations are implemented.

### G07 — QR verification has storage/request placeholders only — medium priority, missing

**Requirement:** The API accepts `qr_code` when required by a session; the schema includes a session secret/expiry and `qr_code_verified`; session detail documents `qr_code_enabled`.

**Implementation:** [Session model:346](../module2-backend/app/models.py#L346) explicitly marks QR as unused. The check-in handler never validates `qr_code`, secret, or expiry, and never sets `qr_code_verified`. A probe installed a secret and unexpired deadline directly in the scratch session, submitted a wrong QR value, and still received `201`. Session serialization omits `qr_code_enabled`. No session QR enable/issue UI or API configuration path was found.

**Remaining work:** Specify how sessions enable/rotate QR codes, then implement validation and presentation. The submitted field is optional, so this is a missing conditional workflow rather than a requirement to scan QR for every check-in.

### G08 — Audit immutability is limited to mapped-instance operations — high priority, partial

**Requirement:** Audit logs cannot be modified or deleted; use append-only/write-once storage.

**Implementation:** [models.py:668](../module2-backend/app/models.py#L668) rejects mapped-instance update/delete through ORM events. There is no repository-managed database trigger/privilege migration enforcing append-only access. A disposable-schema probe successfully executed and committed `query(AuditLog).filter(...).update(...)`.

**Remaining work:** Enforce immutability at the database permission/constraint layer as appropriate. There is no public audit mutation endpoint, and this probe does not demonstrate a remote API exploit. Separately managed database controls were not inspected.

### G09 — Security-relevant audit coverage is incomplete — medium priority, partial

**Requirement:** Database/briefing require all sensitive/security-relevant actions to be logged. Security requirements include submitted check-in attempts and security violations.

**Implementation:** Authentication, user changes, sessions, enrollments, device operations, face enrollment, review, and export have audit paths. However, [course create/update/delete](../module2-backend/app/main.py#L855) commit without audit entries; the course-create probe found zero events for that course. Refused check-ins return before the two audit inserts near the successful record commit. `security_violation` is an allowed action and can be serialized, but no application detection path was found that emits it. `last_login_at` is never updated after login; the probe observed null.

**Remaining work:** Define events for course/security changes and rejected attempts, log them without raw images/secrets, and populate the documented login metadata. The present `checkin_attempted` counter/event covers recorded attendance decisions, not every HTTP submission.

### G10 — Course security switches do not control the check-in policy — medium priority, partial

**Requirement:** The schema defines course-level `require_face_recognition` and `require_device_binding` as security settings. Their precedence relative to session flags needs clarification.

**Implementation:** Both values are accepted, stored, and serialized, but no attendance-policy read of either switch was found. [Session creation](../module2-backend/app/main.py#L1588) uses request/session flags, not the course's face-recognition switch. A course with `require_face_recognition=true` produced a session with `require_face_match=false`. A course with `require_device_binding=false` still produced the unknown-device risk factor.

**Remaining work:** Decide whether these are effective defaults, mandatory course controls, or obsolete fields, and implement/document precedence. Device registration, server challenges, key proof, account limits, and admin approval themselves are implemented.

### G11 — Database schema/migration requirements are incomplete — medium priority, partial

**Requirement:** Database schema defines column constraints, FK/index coverage, and an Alembic migration workflow.

**Observed fresh-schema differences:**

| Item | Documented | Current model/schema |
| --- | --- | --- |
| `courses.description` | Nullable text | Missing |
| `devices.attestation_token` | Nullable encrypted token | Missing |
| `devices.public_key` | NOT NULL | Nullable |
| `devices.public_key_created_at` | NOT NULL | Nullable |
| `checkins.device_id` | FK to `devices.id` | Plain nullable string without FK |
| `risk_signals` | Main table | Missing; see G06 |
| Migration workflow | Alembic revisions/upgrades/rollback | Dependency installed, but no Alembic environment or revisions found; startup uses `create_all` |
| FK indexes | All FK columns indexed | Examples lacking individual indexes: `courses.instructor_id`, `sessions.instructor_id`, `checkins.reviewed_by_id` |

The additional `courses.instructor_id` field is required by the API but absent from the schema document. Additional browser-identity, key-rotation, TA-assignment, venue, snapshot, push, and motion-spec tables exist; some are described in newer implementation notes. Their presence is not itself a missing feature or evidence that an extension was unauthorized.

`create_all` can create absent tables; it does not provide the documented upgrade/rollback workflow for changing existing columns. Existing production schema compatibility remains unverified.

### G12 — Validation and output sanitization are incomplete — medium priority, partial

**Requirement:** Security requirements demand UUIDv4 IDs, strict enums, and HTML escaping of user-provided response content.

**Implementation:** Email/password rules, finite coordinates, coordinate ranges, risk bounds, and several enums are validated. Many IDs remain unconstrained strings, and session type is a free string. The probes observed `404` for `GET /users/not-a-uuid` and successful creation (`201`) with `session_type="invalid-type"`. Registration returns a submitted `<script>…</script>` name without HTML escaping; profile edits and appeal/review prose do escape markup. Course/session/device text has no consistent output escaping policy.

**Remaining work:** Complete validation and agree on a consistent API sanitization contract. JSON content types and React's normal text rendering mitigate rendering attacks; this observation alone does not establish executable browser XSS. SQL queries use ORM/parameterized patterns; no user-interpolated SQL path was found in the reviewed request handling.

### G13 — Session status-transition rules are not enforced — medium priority, contract mismatch

**Requirement:** The API documents `scheduled → active → closed`, cancellation, and terminal cancelled/manually closed states. Admin status override is explicitly available for testing.

**Implementation:** [_apply_status_transition:1579](../module2-backend/app/main.py#L1579) assigns any permitted enum without checking the previous state. Through the ordinary `PATCH /sessions/{id}` route, the probe reopened both a closed session and a cancelled session as active (`200`). This was not the dedicated admin override route.

**Remaining work:** Clarify whether normal administrative PATCH is also intended to override terminal states; enforce the transition graph for normal session management if it is not. Background automatic activation/closure, catch-up after downtime, audit entries, and scheduled-only timing edits are implemented.

### G14 — Monitoring exists, but alert rules and end-to-end tracing are incomplete — medium priority, partial

**Requirement:** Module 4 guidance describes high-flagged-rate and failed-login alerts; integration/briefing include distributed tracing and Prometheus/Grafana.

**Implementation:** Backend and face-service `/metrics`, backend JSON metrics, Prometheus scrape targets, Grafana provisioning, and dashboard polling exist. No Prometheus alert rule files/Alertmanager configuration or Grafana alert provisioning was found. Visual high-risk items are not an automated failed-login/flagged-rate alert rule.

[Module 3 telemetry](../module3-face-recognition/app/telemetry.py) configures OpenTelemetry spans. Backend code has diagnostic correlation and aggregate metrics but no OpenTelemetry instrumentation/export setup; merely setting its `OTEL_EXPORTER_OTLP_ENDPOINT` does not create backend-to-face distributed spans. The collector currently exports traces to debug output, without a persisted trace-query backend. This is an observability completion gap, not a missing core attendance endpoint.

## API contract differences and specification conflicts

All routes exist. The following details still prevent claiming exact compliance with every document.

| ID | Requirement/source | Current implementation or conflict | Classification |
| --- | --- | --- | --- |
| C01 | `GET /courses/` supports `semester` | Handler has no semester argument/filter. Scratch requests for S1 and S2 both returned the same one S1 course. | Confirmed contract mismatch |
| C02 | `GET /courses/` requires authentication | Anonymous request returns `200` with an empty page. It does not disclose courses, but it does not require auth as documented. | Confirmed contract mismatch |
| C03 | Session-create example uses `session_name` | `SessionCreate` requires `name`; submitting the exact documented key returns `422` for missing `name`. Responses, clients, and public fixtures use `name`. | Confirmed request/document mismatch |
| C04 | Register and `GET /users/me` response examples include `created_at` | Both omit it. `_serialize_user` includes it for other user reads. | Confirmed response mismatch |
| C05 | Flagged-check-in response example is an array | `GET /checkins/flagged` returns `{items,total,limit,offset}`. The newer roster guidance describes paging this route, and the generic pagination section favors envelopes. | Contract mismatch plus document ambiguity |
| C06 | Session-check-in example includes `device_trusted`; session detail includes `qr_code_enabled` | Those fields are not serialized by the respective handlers. QR behavior is also missing (G07). | Static response mismatch |
| C07 | Security requires `SECRET_KEY`; optional TTL/cost/backend-risk settings are listed | Backend reads `JWT_SECRET`, fixes access/refresh TTLs at 60 minutes/7 days, and does not read the listed backend `BCRYPT_ROUNDS` or `RISK_SCORE_THRESHOLD`. Existing TTLs and bcrypt's default cost meet the required values. `RISK_THRESHOLD` is a separate Module 3 setting. | Configuration contract mismatch |
| C08 | JWT structure shows `sub`, `email`, `iat`, role, expiry | Current access claims are `user_id`, `role`, `type`, `exp`. Authentication works internally, but consumers expecting the shown claims are incompatible. | Confirmed example/claim mismatch |
| C09 | Liveness default is 0.60 in security/API documents | Current `Settings` default is 0.85 with independent learned PAD enforcement at 0.75. New regression/implementation notes deliberately assert this stricter policy. | Documentation drift; do not weaken automatically |
| C10 | Security/API say SHA-256 biometric hash | Current templates are 256-bit SimHash of normalized dlib descriptors, encoded as 64 hex characters. Module 3 teaching notes explicitly discuss SimHash because direct SHA-256 cannot support approximate matching. | Specification conflict; correct shape does not mean SHA-256 |
| C11 | Security critical risk range 0.7–1.0 auto-rejects | Backend returns flagged for risk 0.8 absent a liveness/geofence hard rejection. This agrees with the API's check-in decision table, which flags scores at/above threshold. Module 3 teaching notes use another set of boundaries. | Confirmed behavior, conflicting decision specifications |
| C12 | Student Overview says no added tabs and “View attendance” scrolls to history | [StudentView](../module4-observability/src/components/dashboard/StudentView.tsx) has Overview/My sessions/My devices tabs; [StudentOverview](../module4-observability/src/components/dashboard/StudentOverview.tsx) invokes `onViewCalendar`, switching to My sessions. Flagged “View records” still targets history. | Static UI contract drift |
| C13 | Roster paragraph says course/session ownership or no assigned instructor matches check-in detail/review/session-export permissions | Roster retains that broader rule; `can_staff_course` and session export enforce assigned-course ownership. Some other endpoint sections explicitly demand this stricter ownership. | Inconsistent cross-endpoint documentation/policy |
| C14 | Generic pagination says all list endpoints use envelopes | Endpoint-specific contracts explicitly retain arrays for active/my sessions and own check-ins; several device/enrollment lists are also arrays. | Internal documentation inconsistency; preserve explicit endpoint contracts |
| C15 | Schema/integration guide describe invitation table, durable SMTP outbox, Mailpit, and `/setup-account` | Current code/Compose has no invitation worker, invitation model, Mailpit service, or setup route. The API's updated 31 October section explicitly replaces invitations with one-time initial-password disclosure; that replacement is implemented in backend and dashboard. | Retired workflow still documented; do not restore automatically |
| C16 | Database recommends pool size 10 + overflow 20 | Current PostgreSQL pool is 3 + overflow 0 with admission control, explicitly tuned for the shared connection limit. | Documented sizing differs from intentional deployment tuning |
| C17 | Integration architecture/examples use Streamlit and direct dashboard DB/Prometheus access | Dashboard is React/Vite and uses authenticated backend APIs; metrics visualization uses backend metrics/Grafana. The briefing explicitly permits alternative stacks. | Architecture documentation drift, not a missing Streamlit implementation |
| C18 | Module 1 says HTTPS is a PWA component | Security/API explicitly permit HTTP only. Camera/geolocation still require a secure browser context, as the implemented hooks check. | Documentation/platform distinction, not an unconditional TLS requirement |

Missing `description`/attestation columns and typed IDs are documented schema/validation gaps even if current public tests do not assert them. Conversely, old TODO comments near the end of `main.py` list implemented authentication/audit models and obsolete aliases; they are not evidence that the actual documented routes are absent.

## Coverage of the complete requirement set

This matrix covers the requirements and teaching topics across every document. “Implemented” is a source-inspection conclusion unless the checks section identifies a fresh runtime check; it is not a promise about unseen tests or real-device accuracy.

| Document / requirement group | Assessment | Implementation evidence / remaining issue |
| --- | --- | --- |
| Briefing: four communicating modules, container deliverable | Implemented, runtime unverified | Four module Dockerfiles and Compose; backend orchestrates face calls. Full container startup was unavailable. |
| Briefing: courses, sessions, enrollment, student check-in and review | Implemented | Backend main handlers, dashboard session/roster/enrollment components; public backend contracts pass. |
| Briefing: GPS spoofing, impossible travel, replay and deepfake prevention | Partial/unverified | Geofencing, device proofs, random motion and PAD exist; G05 and real-attack validation remain. |
| Briefing: privacy, audit, security and grading/load goals | Partial | G01–G04, G08–G09; current full face/stress certification unavailable. Historical scores are not reused as fresh results. |
| API: authentication and users | Implemented with mismatches | Auth/profile/admin user handlers, face enrollment proxy; C04/C07/C08 and G01/G02/G12. |
| API: courses and TA assignments | Implemented with gaps | Course CRUD, assignment router; C01/C02 and G09/G10. |
| API: sessions, active/my sessions, calendar and lifecycle | Implemented with gaps | Main handlers, lifecycle scheduler, SessionsPanel/SessionCalendar; C03 and G07/G13. |
| API: instructor roster | Implemented, policy ambiguity | `attendance_roster.py` reconstructs eligibility, retains recorded students, separates Present from verification; C13. |
| API: check-ins, filters, own history, review, one appeal within seven days | Implemented with gaps | Main check-in/list/appeal/review handlers; G02–G05/G07, C05/C06. Required missing identity is flagged, not silently marked verified. |
| API: student Overview | Backend implemented; UI drift | `student_overview.py` handles semester configuration, history eligibility, distinct counts, null percentage and Singapore dates; frontend independently polls three cards; C12. |
| API: system/session/course/student analytics and course Overview | Implemented | `stats.py`, StudentAttendanceDetails, InstructorOverview and admin charts. Different denominator policies are explicitly described in endpoint-specific docs, so they are not automatically defects. |
| API: device registration, list, update and removal | Implemented | Main device handlers, `device_binding.py`, `device_rotation.py`, PWA MyDevices and dashboard approvals. Legacy public keys remain optional contrary to schema. |
| API: enrollments, reactivation, bulk account creation, initial passwords | Implemented | Main enrollment handlers; dashboard EnrollmentsPanel holds new credentials transiently; C15 identifies retired invitation text. |
| API: audit filtering and exports | Implemented with compliance gaps | Audit router/filtering/CSV, course/session CSV and JSON export; G08/G09. Session JSON includes summary/records, while course JSON is the documented array. |
| API: required admin testing endpoints | Implemented | Bulk users, activation/deactivation, status override and admin enrollment routes; all found in runtime route inventory. |
| API: face enrollment, verify, legacy match, risk assessment, health/root | Implemented; native identity run unverified | Face service handlers, in-memory decode/detection/embedding/template pipelines; C09/C10. |
| API: liveness (bonus), device attest (optional), motion extension | Implemented; accuracy unverified | Passive liveness/PAD, cryptographic attest and versioned one-use motion proofs. Motion v2 is explained by the linked implementation note; do not treat old fixed-blink text as missing v2 code. |
| API: response/error format, CORS, pagination, security | Partial | Pydantic error redaction, exact CORS, ORM and auth exist; G01/G12 and C02–C08/C14. |
| Database: users | Columns present; metadata behavior partial | Hash-only template field, bcrypt password, consent flags and deletion schedule; last-login/retention issues in G03/G09. |
| Database: courses | Partial | Missing description, added API-required instructor field; dormant policy controls. |
| Database: enrollments | Implemented | FKs, unique student/course pair, timestamps, deactivation/reactivation and audit history. |
| Database: sessions | Columns present; QR/transition behavior partial | Scheduling/security/QR columns exist; G07/G13. |
| Database: devices | Partial schema compliance | G11; actual one-use device proof and key renewal are implemented extensions. |
| Database: check-ins | Partial | Unique session/student, results/review/appeal columns; G03/G04/G11. |
| Database: risk_signals | Missing | G06. |
| Database: audit_logs | Partial | Columns/indexes and no updated_at, but G08 immutability limitation. |
| Database: migrations, pooling/indexes and privacy | Partial | G03/G11, C16; no BLOB columns in reviewed core models and no normal pipeline persistence of raw images/embeddings found. |
| Database: optional motion metadata | Implemented plus extension | Policies/challenges and scalar outcomes; v2 specifications in an extra child table. |
| Database: invitation metadata appendix | Conflicts with current workflow | C15; absent from fresh schema, legacy cleanup only. |
| Security: password/JWT settings | Required baseline values implemented | Bcrypt, minimum eight characters, HS256, 1h/7d; C07/C08. |
| Security: RBAC | Broadly implemented, consistency gaps | Endpoint-specific roles, assigned instructor courses, explicit TA assignments, own student records; C13 and instructor audit-tab issue below. |
| Security: rate limiting | Conditional | G01. |
| Security: risk thresholds and weights | Standalone risk service implemented; attendance integration partial | G05/G10 and C09/C11. |
| Security: input validation, SQL/XSS | Partial | G12. |
| Security: biometric protection, consent and retention | Partial | No normal raw-image persistence found; G02–G04, C10. No live storage/encryption audit was performed. |
| Security: audit, CORS, HTTP and environment variables | Partial | G08/G09, C07/C18. Exact CORS validation exists. Bearer auth protects normal application mutations; cookie refresh/logout use SameSite=Lax, without a separate CSRF token mechanism. The API's brief “token-based” CSRF requirement needs a precise browser-auth contract. |
| Integration: frontend/backend and dashboard/backend auth/data/error flows | Implemented | Memory access tokens, HttpOnly refresh cookies, refresh/retry clients, same-origin proxies, backend role checks. Fresh UI proxy validation was blocked by the environment. |
| Integration: backend/face communication and failure handling | Implemented, policies differ by flow | Reused HTTP client, short legacy calls, strict enrollment errors, 45s motion verification; legacy failure yields missing evidence/flagged status, required motion refuses invalid evidence. The guide's simple 5s example does not describe the extended motion contract. |
| Integration: database/Redis/Prometheus/configuration/health | Partial documentation alignment | DB/API paths and metrics exist; G01/G14, C07/C17. Backend and face expose /health; dedicated frontend/dashboard JSON /health routes were not found (the guide's own check example requests their roots). |
| Integration: enrollment SMTP instructions | Retired/conflicting | C15. |
| Module 1: PWA manifest, install, caching and offline shell | Implemented, browser unverified | Manifest/icons, build-service-worker script, service worker, install/update components and IndexedDB session snapshots. |
| Module 1: camera/geolocation and WebRTC cleanup | Implemented, hardware unverified | Permission queries, denial handling, fresh position capture, canvas frames, track stop on cancellation/unmount/visibility changes. |
| Module 1: token security and consent UX | Implemented client-side; API gap | In-memory access tokens, HttpOnly refresh cookie, logout clear, consent settings; G02. |
| Module 1: no cached auth/check-in submissions | Implemented | Service worker GET/static allowlist; offline mode displays saved session/attendance metadata and does not queue check-ins/images. |
| Module 1: push notifications (optional) | Implemented; delivery unverified | Backend encrypted push/outbox, opt-in settings, account-scoped service-worker notifications; ten fresh worker tests passed. |
| Module 2: REST methods, schemas, auth and persistence | Implemented with gaps | G11/G12 and C01–C08. Generic class/code names still referring to skeletons are stale comments. |
| Module 2: rate limits and error/logging patterns | Partial | G01/G09/G14. Input redaction exists; complete distributed request tracing does not. |
| Module 3: detection, extraction, approximate matching and thresholds | Implemented; native behavior unverified | Dlib descriptors/SimHash, 0.70 match score mapping, detection/quality checks; C09/C10 and calibration limits. |
| Module 3: active/passive liveness and privacy | Implemented; real-attack assurance unverified | Random blink/turn challenge, passive weighted cues and learned PAD, frame processing in memory. One scalar-regression test currently fails. |
| Module 3: risk integration teaching material | Partial/conflicting | G05 and C11. |
| Module 4: hierarchy, charts, tables and mobile layout | Implemented structure; visual QA unverified | Role views, cards/charts, scrollable roster/history tables; no fresh browser/mobile visual inspection. |
| Module 4: live updates | Implemented | React Query polling, usually 30s; session management polls at 5s. WebSockets are suggested, not required. |
| Module 4: metrics/monitoring/alerting | Partial | G14. |
| Module 4: role-aware navigation | Partial | InstructorView still includes an Audit logs tab although AuditLogs blocks non-admins and disables its query. No audit data leak was demonstrated; hiding the inaccessible tab remains a UX gap. |
| Module 4: CSV/JSON/PDF reporting | CSV/JSON implemented; PDF missing | PDF is mentioned in teaching guidance, but neither required API export contract offers PDF. Treat PDF as an unimplemented guidance feature, pending scope confirmation. |
| Historical audit and evidence | Reviewed, not rerun or adopted as current certification | Prior fixes remain visible; GPS/network/biometric limitations still apply. Its older full-suite/load results cannot certify the current motion/PAD version. |

## Checks run and results

| Check | Fresh result | What this establishes / limitation |
| --- | --- | --- |
| Route inventory vs API headings plus TA-assignment table | **64/64 present** | 56 backend, 8 face. Dynamic backend registration and static face decorators were compared with normalized parameter names/trailing slashes. Does not verify all request/response semantics. Full inventory below and in JSON. |
| Disposable SQLite behavioral probes | **Completed** | Confirmed the observations in G01–G04/G07–G13 and C01–C04/C08/C11. Core-table column names and several constraints were inspected on fresh ORM-created tables. No configured database access. |
| Public suite through `new-tests/run_session_regressions.py tests/public/` | **87 passed, 16 skipped** in 46.13s | Fifteen face tests skipped because the face URL was deliberately unavailable; one pre-existing concurrent-check-in test skips. Backend public cases, including its limited performance checks, passed. This is not 100% full-system coverage. |
| `test_advanced_security_audit.py` + `test_database_admission.py` | **26 passed** | Validation/redaction, strict-mode controls, duplicate behavior and admission queue. Security storage is mocked; this does not exercise real Redis deployment. |
| Selected `test_face_module3.py` cases | **11 passed, 11 deselected** | Template properties, risk boundaries/weights and cryptographic attestation. Native identity-image cases were deliberately not selected. |
| `test_liveness_thresholds.py` + `test_pad_enforcement.py` | **62 passed, 1 failed** | Scalar/policy/HTTP behavior with model components stubbed. Failure described below. |
| `test_pad_enforcement.py` independently | **32 passed, 1 failed** | Reproduced the same failure outside the combined run. Not a second distinct failure. |
| `test_device_rotation_privacy.py` | **5 passed** | Local key rotation and password-confirmed account-deletion behaviors, using disposable data. |
| `node --test new-tests/pwa/push-notifications.test.mjs` | **10 passed** | Service-worker notification payload/account/navigation behavior in a VM; no real push delivery. |
| Docker availability (`docker compose ps --format json`) | **Unavailable** | Docker daemon socket absent; full disposable PostgreSQL/Redis/face/Prometheus/Grafana stack was not started. |
| `frontend-time.test.cjs` | **Could not run** | Requires precompiled `/private/tmp/saiv-frontend-time-check/time.js`, which is absent. This is a missing test prerequisite, not a demonstrated time-function failure. |
| `frontend-api-proxy.test.mjs` | **3 infrastructure errors** | Requests to localhost:3000 failed with sandbox `EPERM`; no running frontend stack was provided. These do not establish a proxy implementation defect. |
| Full frontend/dashboard build, typecheck, lint and browser/mobile QA | **Not run** | Both module `node_modules` directories are absent. Node was found in the cached runtime, but application dependencies were not installed or changed for this audit. |

The public HTTP runner initially could not bind a localhost port inside the sandbox. The same isolated runner subsequently ran with the required local-port permission. All other behavioral probes used TestClient without binding a port.

### Reproducible PAD test failure

Failing case:

```text
new-tests/test_pad_enforcement.py::test_all_ten_recorded_captures_under_real_scoring_function[photo-pad-20261102T040453Z-1fb76484]
```

At line 166 the test expects `liveness_passed == (pad_live_score >= 0.75)`. That case has PAD score `0.999795` but weighted pre-PAD liveness `0.735096`, below the configured `0.85`; the implementation returns false. This agrees with the separate test `test_pad_pass_does_not_rescue_low_weighted_liveness` and with [liveness.py](../module3-face-recognition/app/liveness.py), which requires the weighted score to pass and lets PAD independently veto it. The failure therefore exposes an inconsistent test expectation; it does not prove the implementation should accept this capture. Resolve it without weakening the liveness policy automatically.

The local environment used Python 3.12.14, pytest 7.4.4, FastAPI 0.109.0, SQLAlchemy 2.0.25, Pydantic 2.5.3 and httpx 0.26.0. Its MediaPipe package reports 1.0.1 rather than the face container's pinned 0.10.18, and `face-recognition` is absent. No native biometric accuracy claim is made. Passlib emitted its known bcrypt-version warning; authentication checks still completed. Deprecation warnings were also present.

### Reproduction commands

Run from the repository root. Backend and face test processes must stay separate because both modules use the import name `app`.

```sh
TEST_FACE_URL=http://127.0.0.1:1 FACE_SERVICE_URL=http://127.0.0.1:1 \
  venv/bin/python new-tests/run_session_regressions.py tests/public/

PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m pytest -q -p no:cacheprovider \
  new-tests/test_advanced_security_audit.py new-tests/test_database_admission.py

PYTHONDONTWRITEBYTECODE=1 TELEMETRY_ENABLED=false JSON_LOGGING_ENABLED=false \
  venv/bin/python -m pytest -q -p no:cacheprovider new-tests/test_face_module3.py \
  -k 'templates_are or risk_level or risk_breakdown or device_attestation'

PYTHONDONTWRITEBYTECODE=1 TELEMETRY_ENABLED=false JSON_LOGGING_ENABLED=false \
  venv/bin/python -m pytest -q -p no:cacheprovider \
  new-tests/test_liveness_thresholds.py new-tests/test_pad_enforcement.py

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=module2-backend \
  venv/bin/python -m pytest -q --disable-warnings -p no:cacheprovider \
  new-tests/test_device_rotation_privacy.py

node --test new-tests/pwa/push-notifications.test.mjs
```

For a full subsequent verification, use the existing disposable [audit Compose configuration](../new-tests/docker-compose.audit.yml), install each module's declared dependencies, run all public face tests against native models, exercise Redis thresholds, and rerun PostgreSQL concurrency/load tests. Real mobile/webcam trials should cover the eight random motion combinations, genuine/impostor pairs, prints/screens/videos, permission loss and offline recovery. Do not treat the historical 100-user benchmark as a result for today's complete biometric workflow. Encryption-at-rest settings and trusted location attestation remain outside what source/SQLite checks can prove.

## Suggested resolution order

1. Agree on the conflicting contracts: default strict controls vs classroom registration, retention precision/scope, biometric hash representation, risk decisions, session terminal-state overrides, retired invitations, and student navigation. No conflicting code change is authorized by this inspection.
2. Complete the privacy/security behavior in G01–G05/G08–G09, with boundary and failure-path regression coverage in `new-tests` when implemented.
3. Complete schema/migrations and policy wiring, then correct the confirmed API field/filter mismatches and decide QR scope.
4. Reconcile the PAD scalar test, finish alert/tracing coverage as scoped, and run full native/PostgreSQL/browser verification.

## Files changed, endpoints, and specification gaps

- **Files changed:** this report and `inspection/requirements-inspection-2026-11-03-evidence.json` only. Application implementation and `docs` remain unchanged.
- **Endpoints implemented:** none in this inspection. Existing routes were inspected; disposable probes reused auth/users/courses/enrollment/session/check-in routes. The inventory below identifies the implementations.
- **Specification gaps:** G01–G14 and C01–C18 distinguish incomplete behavior, contract mismatches and conflicting/retired guidance. Optional/guidance-only omissions and runtime uncertainty are identified separately.
- **Checks/results:** recorded above; notably public backend run 87 passed/16 skipped, strict/security/admission 26 passed, selected face contracts 11 passed, liveness/PAD 62 passed/1 failed, privacy/key rotation 5 passed, push worker 10 passed. No implementation fix or test modification was made.

## Appendix: documented endpoint inventory

Backend paths use the `/api/v1` base; face-service paths use the separate Module 3 origin. Every row below has a current handler. The notes refer back to behavior gaps; an empty gap note would not imply exhaustive validation.

### Backend

| Method | Documented path | Handler location | Gaps / qualification |
| --- | --- | --- | --- |
| POST | `/auth/register` | [main.py:173](../module2-backend/app/main.py#L173) | G01/G12, C04 |
| POST | `/auth/login` | [main.py:218](../module2-backend/app/main.py#L218) | G01/G09, C07/C08 |
| POST | `/auth/refresh` | [main.py:294](../module2-backend/app/main.py#L294) | Present; see group assessment above |
| GET | `/users/me` | [main.py:430](../module2-backend/app/main.py#L430) | C04 |
| PUT | `/users/me` | [main.py:445](../module2-backend/app/main.py#L445) | Present; see group assessment above |
| GET | `/users/` | [main.py:703](../module2-backend/app/main.py#L703) | Present; see group assessment above |
| GET | `/users/{user_id}` | [main.py:740](../module2-backend/app/main.py#L740) | Present; see group assessment above |
| PATCH | `/users/{user_id}` | [main.py:776](../module2-backend/app/main.py#L776) | Present; see group assessment above |
| POST | `/users/me/face/enroll` | [main.py:479](../module2-backend/app/main.py#L479) | Present; see group assessment above |
| GET | `/courses/` | [main.py:880](../module2-backend/app/main.py#L880) | C01/C02 |
| GET | `/courses/{course_id}` | [main.py:965](../module2-backend/app/main.py#L965) | Present; see group assessment above |
| POST | `/courses/` | [main.py:855](../module2-backend/app/main.py#L855) | G09/G10 |
| PUT | `/courses/{course_id}` | [main.py:1009](../module2-backend/app/main.py#L1009) | G09/G10 |
| DELETE | `/courses/{course_id}` | [main.py:1041](../module2-backend/app/main.py#L1041) | G09 |
| GET | `/sessions/` | [main.py:1705](../module2-backend/app/main.py#L1705) | Present; see group assessment above |
| GET | `/sessions/active` | [main.py:1677](../module2-backend/app/main.py#L1677) | Present; see group assessment above |
| GET | `/sessions/my-sessions` | [main.py:1765](../module2-backend/app/main.py#L1765) | Present; see group assessment above |
| GET | `/sessions/{session_id}` | [main.py:1869](../module2-backend/app/main.py#L1869) | C06 |
| POST | `/sessions/` | [main.py:1587](../module2-backend/app/main.py#L1587) | G07/G10, C03 |
| PATCH | `/sessions/{session_id}` | [main.py:1910](../module2-backend/app/main.py#L1910) | G13 |
| DELETE | `/sessions/{session_id}` | [main.py:2020](../module2-backend/app/main.py#L2020) | Present; see group assessment above |
| GET | `/sessions/{session_id}/attendance` | [attendance_roster.py:20](../module2-backend/app/attendance_roster.py#L20) | C13 |
| POST | `/checkins/` | [main.py:2358](../module2-backend/app/main.py#L2358) | G01–G05/G07/G10 |
| GET | `/checkins/` | [main.py:2747](../module2-backend/app/main.py#L2747) | Present; see group assessment above |
| GET | `/checkins/my-checkins` | [main.py:2580](../module2-backend/app/main.py#L2580) | Present; see group assessment above |
| GET | `/checkins/session/{session_id}` | [main.py:2634](../module2-backend/app/main.py#L2634) | C06 |
| GET | `/checkins/flagged` | [main.py:2799](../module2-backend/app/main.py#L2799) | C05 |
| GET | `/checkins/{checkin_id}` | [main.py:2847](../module2-backend/app/main.py#L2847) | Present; see group assessment above |
| POST | `/checkins/{id}/appeal` | [main.py:2896](../module2-backend/app/main.py#L2896) | Present; see group assessment above |
| POST | `/checkins/{id}/review` | [main.py:2956](../module2-backend/app/main.py#L2956) | Present; see group assessment above |
| GET | `/stats/my-overview` | [student_overview.py:137](../module2-backend/app/student_overview.py#L137) | C12 (consumer UI) |
| GET | `/stats/overview` | [stats.py:221](../module2-backend/app/stats.py#L221) | Present; see group assessment above |
| GET | `/stats/sessions/{session_id}` | [stats.py:707](../module2-backend/app/stats.py#L707) | Present; see group assessment above |
| GET | `/stats/courses/{course_id}` | [stats.py:863](../module2-backend/app/stats.py#L863) | Present; see group assessment above |
| GET | `/stats/courses/{course_id}/overview` | [stats.py:421](../module2-backend/app/stats.py#L421) | Present; see group assessment above |
| GET | `/stats/students/{student_id}` | [stats.py:1007](../module2-backend/app/stats.py#L1007) | Present; see group assessment above |
| POST | `/devices/register` | [main.py:3039](../module2-backend/app/main.py#L3039) | Present; see group assessment above |
| GET | `/devices/my-devices` | [main.py:3086](../module2-backend/app/main.py#L3086) | Present; see group assessment above |
| DELETE | `/devices/{device_id}` | [main.py:3204](../module2-backend/app/main.py#L3204) | Present; see group assessment above |
| PATCH | `/devices/{device_id}` | [main.py:3146](../module2-backend/app/main.py#L3146) | Present; see group assessment above |
| GET | `/enrollments/my-enrollments` | [main.py:1366](../module2-backend/app/main.py#L1366) | Present; see group assessment above |
| GET | `/enrollments/course/{course_id}` | [main.py:1398](../module2-backend/app/main.py#L1398) | Present; see group assessment above |
| POST | `/enrollments/` | [main.py:1148](../module2-backend/app/main.py#L1148) | Present; see group assessment above |
| POST | `/enrollments/bulk` | [main.py:1201](../module2-backend/app/main.py#L1201) | C15 (retired invitation guidance) |
| DELETE | `/enrollments/{enrollment_id}` | [main.py:1307](../module2-backend/app/main.py#L1307) | Present; see group assessment above |
| GET | `/audit/` | [audit.py:240](../module2-backend/app/audit.py#L240) | G08/G09 (storage/event coverage) |
| GET | `/export/attendance/{course_id}` | [main.py:3388](../module2-backend/app/main.py#L3388) | Present; see group assessment above |
| GET | `/export/session/{session_id}` | [main.py:3283](../module2-backend/app/main.py#L3283) | C13 |
| PATCH | `/admin/users/{user_id}/deactivate` | [main.py:535](../module2-backend/app/main.py#L535) | Present; see group assessment above |
| PATCH | `/admin/users/{user_id}/activate` | [main.py:565](../module2-backend/app/main.py#L565) | Present; see group assessment above |
| POST | `/admin/users/bulk` | [main.py:600](../module2-backend/app/main.py#L600) | Present; see group assessment above |
| PATCH | `/admin/sessions/{session_id}/status` | [main.py:2064](../module2-backend/app/main.py#L2064) | Present; see group assessment above |
| POST | `/admin/enrollments/` | [main.py:1338](../module2-backend/app/main.py#L1338) | Present; see group assessment above |
| GET | `/admin/courses/{course_id}/tas` | [course_assistants.py:55](../module2-backend/app/course_assistants.py#L55) | Present; see group assessment above |
| POST | `/admin/courses/{course_id}/tas` | [course_assistants.py:73](../module2-backend/app/course_assistants.py#L73) | Present; see group assessment above |
| DELETE | `/admin/courses/{course_id}/tas/{user_id}` | [course_assistants.py:104](../module2-backend/app/course_assistants.py#L104) | Present; see group assessment above |

### Face service

| Method | Documented path | Handler location | Gaps / qualification |
| --- | --- | --- | --- |
| POST | `/face/enroll` | [main.py:261](../module3-face-recognition/app/main.py#L261) | C10; native accuracy unverified |
| POST | `/face/verify` | [main.py:449](../module3-face-recognition/app/main.py#L449) | C10; native accuracy unverified |
| POST | `/face/match` | [main.py:458](../module3-face-recognition/app/main.py#L458) | C10; legacy alias |
| POST | `/liveness/check` | [main.py:500](../module3-face-recognition/app/main.py#L500) | Bonus; C09; PAD test failure |
| POST | `/risk/assess` | [main.py:603](../module3-face-recognition/app/main.py#L603) | G05 (backend integration), C11 |
| POST | `/device/attest` | [main.py:625](../module3-face-recognition/app/main.py#L625) | Optional; cryptographic contract checked |
| GET | `/health` | [main.py:197](../module3-face-recognition/app/main.py#L197) | Present; see group assessment above |
| GET | `/` | [main.py:206](../module3-face-recognition/app/main.py#L206) | Present; see group assessment above |

