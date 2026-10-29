# Module 2 (Backend API) audit and roadmap: 25 Oct 2026

**Code deadline:** Tuesday 27 Oct 2026
**Status:** Plan only. Waiting for approval before Phase 1.
**How to track:** tick the boxes in the [Implementation checklist](#6-implementation-checklist) and update each part's **Status** line as work lands. Each new Claude session should read this file first.

Status values: `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED` · `DEFERRED`

---

## 1. Audit summary

### 1.1 What already works (no action needed)

- **Endpoint coverage is complete.** Every endpoint in `docs/API-SPECIFICATION.md` has a route:
  - auth, users, courses, sessions (including `/sessions/{id}/attendance`), check-ins (including flagged, appeal and review), stats (including `/stats/my-overview`), devices, enrollments (including bulk and invitations), audit, export and admin.
  - The routes are in `module2-backend/app/main.py` plus the routers in `attendance_roster.py`, `audit.py`, `invitations.py`, `motion.py`, `stats.py`, `student_overview.py` and `prometheus_metrics.py`.
- **Check-in pipeline:**
  - Window, enrollment and duplicate checks run in one query.
  - Haversine geofence: more than 2× the radius is rejected.
  - Calls to Module 3 for liveness, face verification and risk run through `face_service.py`. The scores fail open, but a required check that returns no result is flagged.
  - The one-use motion challenge is in `motion.py`.
  - A race on the unique constraint returns 400 instead of 500.
  - Each check-in writes two audit rows: `checkin_attempted` and `checkin_<status>`.
- **Concurrency:** the admission queue (`admission.py`) handled 100 concurrent reads and 100 concurrent check-ins in the 23 Oct audit.
- **Audit log:** it is append-only. ORM `before_update` and `before_delete` guards are in `models.py:575-580`, there are 20 action types, and `/audit/` and `/audit/summary` exist.
- **Strict mode** (`STRICT_SECURITY_MODE=true`) adds Redis rate limits, single-use refresh tokens, the consent requirement and required biometric evidence.
- **Last verified totals** come from `docs/audits/2026-10-23-audit-evidence.json`: public suite 102 passed and 1 skipped, 170 backend regressions passed, and 33 frontend regressions passed. **These were not re-run in this session.** Commits `a751741` and `c1851f9` (student dashboard and calendar) landed after that audit.

### 1.2 Gaps found

| ID | Gap | Evidence | Hidden-test category at risk |
|---|---|---|---|
| G1 | The `risk_signals` table does not exist. Only 7 of the 8 tables in the schema are implemented, and risk factors are stored only as JSON in `checkins.risk_factors`. | `models.py` (no `RiskSignal`); comment at `main.py:2298-2301`; `DATABASE-SCHEMA.md` §risk_signals | Privacy Audit (DB inspection), Advanced Security |
| G2 | Device binding is not enforced. Check-in ignores `device_fingerprint`, `checkins.device_id` is never set, `courses.require_device_binding` (default **True**) is never read, and `devices.total_checkins` and `last_seen_at` are never updated by check-in. | `main.py:2300`, `models.py:160`, `models.py:365` | Advanced Security (proxy sign-in) |
| G3 | The network/VPN signal never reaches Module 3. Module 2 does not forward `ip_address` or `user_agent` to `/risk/assess`, and only calls `/risk/assess` when a biometric score exists. | `main.py:2139-2148`; Module 3 accepts both fields (`module3-face-recognition/app/schemas.py:185-192`) | Advanced Security (network) |
| G4 | No GPS-spoofing heuristics beyond distance and accuracy. There is no `impossible_travel` or `rapid_succession` check. | `_assess_checkin_geofence` in `main.py` | Advanced Security (GPS spoofing) |
| G5 | The passive single-frame liveness path has no replay detection. The same captured frame can be resubmitted for another session. The motion path is already one-use. | `_run_biometric_verification` in `main.py` | Advanced Security (replay) |
| G6 | Rate limiting does nothing unless strict mode is on. The briefing and the spec both list the limits as required behaviour. | `security.py:47-49` | Security Basic, Network security |
| G7 | Audit rows never record `ip_address` or `user_agent` (no caller passes them), and `security_violation` is never emitted. | `audit.py:160` is the only use | Privacy Audit, Advanced Security |
| G8 | Retention is not implemented. `scheduled_deletion_at` is never set on users or check-ins, and there is no cleanup job. | `SECURITY-REQUIREMENTS.md` §Data Retention | Privacy Audit |
| G9 | **The specs disagree with each other.** `SECURITY-REQUIREMENTS.md` says a risk score of at least 0.7 is CRITICAL and auto-rejected. The status table in `API-SPECIFICATION.md` only rejects on a failed liveness check or GPS beyond 2× the radius. The code follows API-SPEC. | both docs | Advanced Security |
| G10 | Location is stored at full float precision. The briefing says "limited precision". | `CheckIn.latitude` and `longitude` | Privacy Audit |
| G11 | `CheckInCreate.device_fingerprint` has no length limit, but `devices.device_fingerprint` is `VARCHAR(64)`. Module 1 sends base64 SHA-256 (44 chars), which fits, but test clients may send longer values. | `schemas.py:121` | Robustness |
| G12 | The end-to-end flow has not been re-verified since the latest frontend commits. | git log | Integration, presentation demo |

Out of scope by earlier decision (no action): strict RBAC and the `course_assistants` TA model are not on `main` (see the RBAC policy memory). Main keeps the existing instructor scope rule.

---

## 2. Ownership split

| Area | Owner | Notes |
|---|---|---|
| Check-in decision, risk fusion, `risk_signals`, device binding, rate limits, audit, retention, all REST endpoints | **Module 2** | Covered in this plan |
| Calling `POST /devices/register` after login; sending `X-Forwarded-For` through the Next.js API proxy; a stable fingerprint | **Module 1** | Needed for G2 and G3 to give real values in the PWA (see blockers) |
| `/risk/assess` network scoring weights, liveness and anti-spoof models, `/device/attest` | **Module 3** | Module 2 only forwards inputs |
| Showing new risk-factor types (`device_unknown`, `impossible_travel`, `vpn_detected`, `replay_suspected`) in the flagged-review UI; optionally a `risk_signals` view | **Module 4** | Must render unknown factor types without crashing |

---

## 3. Phases

There are **3 phases**. Phase 1 secures the end-to-end flow (P0). Phase 2 adds the check-in hardening the hidden tests target. Phase 3 covers the policy and privacy items that need a decision, then the freeze.

### Phase 1: Baseline and end-to-end lock (P0), Sun 25 to Mon 26 Oct (morning)

#### Part 1.1: Re-baseline every suite in disposable storage
- **What:** Run the public suite, the backend regressions and the frontend regressions against the disposable audit stack (`new-tests/docker-compose.audit.yml`), so later failures can be attributed to our changes. No code changes.
- **Status:** TODO
- **Priority:** P0
- **Files/endpoints:** `tests/public/`, `new-tests/*.py`, `new-tests/*.mjs`
- **Dependencies:** none. The user runs it; never point it at `:8000` or Supabase.
- **Tests:** public 102 passed and 1 skipped; regression totals match the 23 Oct evidence or differences are explained.
- **Effort:** 1 h

#### Part 1.2: End-to-end attendance flow test
- **What:** Add `new-tests/test_e2e_attendance_flow.py`, one HTTP test covering the full flow:
  1. Admin bulk-creates users.
  2. Student logs in and consents via `PUT /users/me`.
  3. Face enroll (`POST /users/me/face/enroll` with a sample image).
  4. Device register.
  5. Instructor creates and activates a session.
  6. Student checks in, once on the passive path and once on the motion path where Module 3 is available.
  7. The check-in appears in `/checkins/session/{id}` and the `/sessions/{id}/attendance` roster.
  8. A flagged check-in is appealed, then reviewed.
  9. `/export/session/{id}` and `/stats/sessions/{id}` reflect the result.
  10. The audit log contains the expected actions.
- **Status:** TODO
- **Priority:** P0
- **Files/endpoints:** new test only, plus the endpoints listed above
- **Dependencies:** Module 3 must be up for steps 3 and 6. Steps that need Module 3 skip when it is unreachable.
- **Tests:** the new file passes against the disposable stack.
- **Effort:** 2–3 h

#### Part 1.3: Fix regressions found in 1.1 and 1.2
- **What:** Fix anything 1.1 or 1.2 turn up. This part is contingent and may be empty.
- **Status:** TODO
- **Priority:** P0
- **Files/endpoints:** TBD
- **Dependencies:** 1.1 and 1.2
- **Tests:** re-run the failing suite.
- **Effort:** 0–3 h

#### Part 1.4: Shared Supabase schema drift check (read-only)
- **What:** Confirm the live Supabase schema matches `models.py`. `create_all` creates missing tables but never adds columns or enum values.
  - Check the motion and invitation tables, every `audit_action` enum value, and the check-in columns.
  - This is a gate before Phase 2 adds a table.
- **Status:** TODO
- **Priority:** P0
- **Files/endpoints:** a read-only SQL or SQLAlchemy inspection script that I write and you run.
- **Dependencies:** your approval to read the shared DB.
- **Tests:** a drift report with no missing columns, or a list of `ALTER` statements for your approval.
- **Effort:** 0.5 h

### Phase 2: Check-in risk-signal hardening (P1), Mon 26 Oct

All Phase 2 parts edit `create_checkin` and `_combine_checkin_assessment` in `main.py`. They are logically independent, but should be **implemented one at a time** to avoid merge conflicts. Risk-fusion rule for every new signal:
- It adds a factor to `risk_factors`.
- It becomes one more component in the existing `max(...)` fusion.
- Nothing new hard-rejects except where noted.

Public tests accept `approved`, `flagged` and `pending` for check-ins, so new flags do not break them.

#### Part 2.1: `risk_signals` table and persistence
- **What:** Add the `RiskSignal` model exactly as specified in `DATABASE-SCHEMA.md`, using enums for `signal_type` and `severity` and the specified indexes. Write one row per risk factor in the same transaction as the check-in. Keep `checkins.risk_factors` JSON for API compatibility.
- **Status:** TODO
- **Priority:** P1
- **Files/endpoints:** `models.py`, `main.py` (`create_checkin`). Response contract unchanged.
- **Dependencies:**
  - Part 1.4.
  - **Shared DB:** saving `models.py` while `uvicorn --reload` runs against Supabase creates the table there. Stop the dev server first or approve the table creation.
- **Tests:** `new-tests/test_risk_signals.py`
  - A flagged check-in produces matching rows.
  - An approved check-in with no factors writes no rows.
  - A duplicate-race rollback leaves no orphan rows.
  - Signal types outside the spec enum are mapped or rejected.
- **Effort:** 2 h

#### Part 2.2: Device binding in check-in
- **What:**
  - Look up the student's active device by `device_fingerprint` (hash to 64 hex characters if the value is longer than 64; closes G11).
  - When the device is known: set `checkins.device_id` and bump `total_checkins` and `last_seen_at`.
  - When the student has registered devices and this fingerprint is not among them: add `device_unknown` (weight 0.15, as in the spec example). If `require_device_binding` is on, flag the check-in.
  - When the student has no devices at all: needs a decision (see blocker B1).
  - When the fingerprint belongs to another user: informational only, because Module 1's fingerprint (UA, language, platform, screen) collides across identical phones.
- **Status:** TODO
- **Priority:** P1
- **Files/endpoints:** `main.py` (`create_checkin`, device helpers); reuses `POST /devices/register`.
- **Dependencies:** Module 1 does not currently call `/devices/register` (blocker B1). Module 4 must render the `device_unknown` factor.
- **Tests:** `new-tests/test_checkin_device_binding.py`
  - known device → linked and counters bumped
  - unknown device → `device_unknown`, flagged when binding is required
  - revoked device → treated as unknown
  - first-device behaviour per the decision
  - fingerprint over 64 characters → no 500
- **Effort:** 2.5 h

#### Part 2.3: Forward network signals to Module 3
- **What:** Pass `ip_address` and `user_agent` to `/risk/assess`, and call it on every check-in, not only when a biometric score exists.
  - Use a short timeout (about 1.5 s) for the risk-only call so a Module 3 outage cannot push check-ins past the 2 s performance budget.
  - Map Module 3's VPN and proxy flags to `vpn_detected` and `proxy_detected` factors.
  - Take the IP from `request.client.host`. Read `X-Forwarded-For` only from a configured trusted proxy.
- **Status:** TODO
- **Priority:** P1
- **Files/endpoints:** `main.py` (`_run_biometric_verification`), `face_service.py`
- **Dependencies:** Module 3 contract is already in place. Module 1's proxy needs to forward the client IP (blocker B2).
- **Tests:** `new-tests/test_checkin_network_signal.py`
  - a VPN user agent produces a network factor (mocked or real Module 3)
  - Module 3 down → check-in still returns 201 within 2 s
  - spoofed `X-Forwarded-For` from an untrusted peer is ignored
- **Effort:** 1–1.5 h

#### Part 2.4: Impossible travel and rapid succession
- **What:** Compare the new check-in with the same student's most recent earlier check-in, using one indexed query.
  - An implied speed above about 250 km/h (a constant, documented as a judgement call) → `impossible_travel`, flagged.
  - Several check-in attempts within seconds across different sessions → `rapid_succession`.
- **Status:** TODO
- **Priority:** P1
- **Files/endpoints:** `main.py`
- **Dependencies:** none
- **Tests:** `new-tests/test_checkin_gps_spoofing.py`
  - jump from Singapore to London in 10 minutes → flagged with `impossible_travel`
  - same-campus sessions → no factor
  - first-ever check-in → no factor
- **Effort:** 2 h

#### Part 2.5: Replay detection on the passive frame
- **What:** Hash the submitted `liveness_challenge_response` (SHA-256 only, never storing the image).
  - Reusing that hash within a TTL, for a different session or user → `replay_suspected`, flagged, plus a `security_violation` audit row.
  - Store hashes in Redis with a TTL. Fail open if Redis is unavailable: the dev `.env` has no `REDIS_URL`, while Compose sets one.
- **Status:** TODO
- **Priority:** P1 (stretch)
- **Files/endpoints:** `main.py`, `security.py`
- **Dependencies:** Redis in the deployed stack
- **Tests:** `new-tests/test_checkin_replay.py`
  - same frame in two sessions → second check-in flagged
  - distinct frames → no flag
  - Redis down → 201 with no factor
- **Effort:** 1.5 h

#### Part 2.6: Audit context and security violations
- **What:**
  - Pass the request IP and user agent into `create_audit_log` for login, logout, check-in, export, face enroll and device register.
  - Emit `security_violation` when a check-in is rejected for GPS beyond 2×, or carries `impossible_travel` or `replay_suspected`.
- **Status:** TODO
- **Priority:** P1
- **Files/endpoints:** `main.py`, `audit.py`; reuses `GET /audit/` and `/audit/summary`.
- **Dependencies:** none. Can run in parallel with 2.1–2.5 except for edits to the same lines.
- **Tests:** extend `new-tests/test_audit_logs.py`
  - login_success and login_failed rows carry an IP
  - security_violation appears for an out-of-geofence rejection
  - existing audit tests still pass
- **Effort:** 1.5 h

### Phase 3: Policy and privacy decisions, then freeze, Mon 26 to Tue 27 Oct

#### Part 3.1: Rate limits on by default (needs a decision)
- **What:** Split the strict-mode switch into per-category settings.
  - On by default: login 60/hour per IP, check-in 10/minute per user, API 1000/hour per user.
  - Registration (10/hour per IP) stays strict-only, because the public fixtures register far more than 10 users from one IP.
  - Redis outage outside strict mode → fail open, so dev without Redis keeps working.
  - Decide whether single-use refresh rotation also becomes the default.
- **Status:** TODO
- **Priority:** P1
- **Files/endpoints:** `security.py`, `main.py`
- **Dependencies:** your decision (B3) and a full public-suite run to prove that no fixture exceeds the login limit.
- **Tests:**
  - `new-tests/test_rate_limits_default.py`: the 61st login gets 429 with `Retry-After`; the 11th check-in in a minute gets 429; no Redis → no 503 in default mode.
  - Public suite still at baseline.
- **Effort:** 1.5 h

#### Part 3.2: Retention
- **What:**
  - Set `checkins.scheduled_deletion_at = checked_in_at + 30 days`.
  - Set `users.scheduled_deletion_at = now + 30 days` on deactivation, and clear it on reactivation.
  - Add an idempotent purge function, run at startup and/or by a scheduled task. It removes or anonymises due rows and never touches `audit_logs`.
- **Status:** TODO
- **Priority:** P2
- **Files/endpoints:** `main.py` (admin activate/deactivate, check-in create), new `retention.py`
- **Dependencies:** decision B4 (deleting check-ins after 30 days conflicts with semester-long exports and stats).
- **Tests:** `new-tests/test_retention.py`
- **Effort:** 2 h

#### Part 3.3: Limited-precision location storage
- **What:** Round the stored latitude and longitude to 5 decimal places (about 1 m) after the distance is computed at full precision.
- **Status:** TODO
- **Priority:** P2
- **Files/endpoints:** `main.py`
- **Dependencies:** check that Module 4's map and exports are fine with rounded values.
- **Tests:** stored values are rounded and `distance_from_venue_meters` is unchanged.
- **Effort:** 0.5 h

#### Part 3.4: Resolve the critical-risk conflict (G9)
- **What:** Decision only. Either keep the API-SPEC behaviour (recommended, matching current code and the public contract) or auto-reject risk scores of at least 0.7. If auto-reject is chosen, it is a small change to `_combine_checkin_assessment`.
- **Status:** TODO
- **Priority:** P2
- **Dependencies:** your decision (B5); docs conflict under rule 6
- **Tests:** a unit test for the chosen threshold behaviour
- **Effort:** 0.5 h

#### Part 3.5: Final regression and freeze
- **What:**
  - Re-run every suite from 1.1 plus all new Phase 2 and 3 tests.
  - Build the backend image and run `docker compose config`.
  - Update `new-documentations/` handoff notes for Modules 1, 3 and 4.
  - Commit only when you ask.
- **Status:** TODO
- **Priority:** P0
- **Files/endpoints:** none new
- **Dependencies:** everything merged
- **Tests:** totals at or above the baseline, with every new test green.
- **Effort:** 2 h

---

## 4. Independent vs. sequential work

- **Must be sequential:**
  - 1.1 and 1.2 → 1.3.
  - 1.4 → 2.1.
  - Everything → 3.5.
  - 2.2 should come after 2.1 so device signals land in `risk_signals`. Not strictly required, because 2.1 mirrors all factors anyway.
- **Logically independent, but they edit the same function and should be done one at a time:** 2.2, 2.3, 2.4, 2.5 and 2.6.
- **Independent of each other and of Phase 2:** 1.2 (test only), 3.3 and 3.4 (decision).
- **Blocked on a decision:** 2.2 (B1, first-device rule), 3.1 (B3), 3.2 (B4), 3.4 (B5).

## 5. Totals

- **Phases:** 3
- **Parts:** 15 (Phase 1: 4, Phase 2: 6, Phase 3: 5)
- **Estimated effort:** about 21–26 h

## 6. Implementation checklist

1. [ ] 1.1 Re-baseline all suites (disposable stack)
2. [ ] 1.2 E2E attendance flow test
3. [ ] 1.3 Fix baseline and E2E regressions
4. [ ] 1.4 Supabase schema drift check (read-only)
5. [ ] 2.1 `risk_signals` table and persistence
6. [ ] 2.2 Device binding in check-in
7. [ ] 2.3 Forward IP and user agent to `/risk/assess`
8. [ ] 2.4 Impossible travel and rapid succession
9. [ ] 2.5 Passive-frame replay detection
10. [ ] 2.6 Audit IP and user agent, plus `security_violation`
11. [ ] 3.1 Default-on rate limits
12. [ ] 3.2 Retention / `scheduled_deletion_at`
13. [ ] 3.3 Limited-precision location
14. [ ] 3.4 Critical-risk policy decision
15. [ ] 3.5 Final regression and freeze

## 7. Recommended execution order

1.1 → 1.2 → 1.3 → 1.4 → 2.1 → 2.6 → 2.2 → 2.3 → 3.1 → 2.4 → 2.5 → 3.5, then 3.3, 3.4 and 3.2 if time remains (re-run 3.5 after them).

Why this order: 2.6 and 2.1 are self-contained and give the hidden Privacy Audit and Advanced Security categories the most coverage per hour. 2.2 and 2.3 depend on teammate input, so they should start while that input is being gathered. 3.1 needs a full public-suite run, so it should happen before the final freeze.

## 8. Blockers that need teammate or user coordination

| ID | Blocker | Who |
|---|---|---|
| B1 | Module 1 never calls `POST /devices/register`. Decide one of two approaches: (a) Module 1 registers the device after login, or (b) Module 2 trusts the first device a student checks in from ("trust on first use") and auto-registers it at first check-in. Option (b) is not in the spec. **Recommended:** (b) as a fallback plus (a) if Module 1 has time. | You + Module 1 |
| B2 | The Next.js API proxy must forward the real client IP (`X-Forwarded-For`), or every check-in shows the proxy's IP. Module 2 also needs the proxy's address configured as trusted. | Module 1 |
| B3 | Rate limits on by default: which categories, and whether refresh-token reuse rejection also becomes the default. | You |
| B4 | Retention: should due check-ins be deleted or anonymised? Deleting them after 30 days breaks semester exports and stats. | You (and Module 4 for exports) |
| B5 | The G9 spec conflict: should a risk score of at least 0.7 be auto-rejected? Rule 6 means I need explicit approval before departing from API-SPEC. | You |
| B6 | Part 2.1 creates a table on shared Supabase as soon as `models.py` is saved, because the dev server runs with `--reload`. Stop the dev server or approve the table creation. | You |
| B7 | Module 4 must render the new factor types without errors. | Module 4 |
| B8 | Module 3 must confirm the `/risk/assess` network weights and that it handles requests with no biometric scores (needed for 2.3). | Module 3 |

## 9. What can realistically be done by 27 Oct

- **Will finish:** Phase 1 (1.1–1.4), 2.1, 2.6, 2.2 (using whichever B1 option is chosen), 2.3, 3.1 and 3.5. That is about 15–17 h across Sunday night, Monday and Tuesday morning.
- **Stretch:** 2.4 and 2.5. Each is about 2 h, and each targets a named hidden-test category.
- **Likely deferred past code freeze:** 3.2, 3.3 and 3.4. They are P2 and blocked on decisions. If not done, mention them in the presentation as known limitations.
- **Risk:** if 1.1 or 1.2 turn up regressions from the latest frontend commits, Part 1.3 takes priority over all of Phase 2.

## 10. Specification gaps (record only; `./docs` is read-only)

- `SECURITY-REQUIREMENTS.md` CRITICAL auto-reject vs. the `API-SPECIFICATION.md` status table (G9).
- No spec defines how individual risk signals are fused. The code uses `max(...)`; the earlier Week 5 integration note explains why.
- There is no spec for registering a device implicitly at check-in, or for treating a student's first device as trusted.
- There is no impossible-travel speed threshold.
- Retention says "auto-delete" but does not say how that fits semester-long exports.
- There is no endpoint for a user to request deletion of their own data, even though the briefing lists a "right to deletion". Adding one would be a new endpoint outside the spec, so it is not planned.
