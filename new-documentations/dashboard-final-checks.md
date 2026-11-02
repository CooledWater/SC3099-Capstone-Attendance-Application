# Dashboard final checks ? 31 Oct 2026

## Verdict

The checked dashboard/API contracts pass, but the entire repository is not yet green. A review push can include the known test limitations below; this audit does not certify a release or every legacy suite.

## Passing checks

- TypeScript: npx tsc --noEmit in module4-observability passes. Fixed optional verification and fixed-size date indexing errors in StudentSessionCalendar without changing its displayed dates or attendance rules.
- Production dashboard build passes; Vite retains its existing large-chunk advisory.
- Module 4 frontend suites: 152 tests pass. Two Module 1 camera/session files are outside this dashboard run: session-checkin-policy.test.mjs and student-attendance-restore.test.mjs. A separate exploratory run found stale mocks in those files; they are not claimed to pass.
- Isolated backend role suites: 205 tests pass across TA scope/assignment/overview, instructor roster/risk, admin device owners/weekly charts, historical snapshots, session lifecycle/read scope, and enrollment initial credentials.
- Connected role workflow: one additional test passes, covering instructor-created student credentials, sign-in, admin TA assignment/session activation, unverified-device flagging, TA review, student history, instructor export and admin audit. TA enrollment/export and instructor audit access remain forbidden.
- Public API/dashboard/observability plus cookie authentication and enrollment HTTP suites: 66 tests pass against a disposable SQLite backend. The public scoring summary is 48/48 for the exercised scored categories.
- Runtime route inventory: all 54 backend method/path headings from API-SPECIFICATION.md match registered routes (86 signatures including aliases/extensions). Face-service endpoints were excluded. This proves route presence; the suites above check response behavior and permissions. No missing dashboard endpoint was identified and no new endpoint was implemented.
- Headless Edge enrollment browser checks pass outside the sandbox, including scoped course selection, roster search/filtering, enrollment validation/results, deletion by enrollment ID, mobile layout and retry/error states.
- Headless Edge export browser checks pass outside the sandbox, including Singapore date bounds, CSV/JSON downloads, empty/error cases and mobile layout.
- git diff --check passes (line-ending notices only).

## Remaining checks and limitations

- The expanded legacy HTTP run (test_missing_endpoints.py, test_devices_sessions_checkins.py, test_audit_logs.py and module2-backend/tests/test_stats_metrics.py in addition to the passing contracts) finished with 155 passed, 5 failed and 81 setup errors. Shared fixtures expect GPS-only submissions from unverified devices to be approved; current device policy flags them. Many dependent cases never reached their assertions. Do not count these cases as passed or weaken device verification to satisfy the fixtures. The remaining legacy assertions need individual review.
- The check-in browser script now reaches the session/roster screen after updating its assigned-course mock, but still fails its table-heading/timezone assertion. Its pagination/review/export steps after that assertion are not browser-verified in this audit; corresponding component/API tests pass.
- Sandboxed Edge runs closed their CDP connections; enrollment and export were repeated successfully outside the sandbox.
- The admin system-wide table remains all-time, and its previously noted loading/active-session presentation caveats were not changed. Only the requested average-risk No data display was authorized in that review.
- Instructors can see an Audit logs tab but its component refuses access; general audit access is admin-only, as specified. TA accounts can review assigned courses but cannot create student accounts or modify enrollments.

## Specification update

API-SPECIFICATION.md was edited under the user's explicit request, overriding the local docs read-only rule for that file. It now documents initial_password, no-store responses, existing-account behavior, transient staff credential display, normal password sign-in, and retirement/404 of the five invitation endpoints. No SMTP worker or Mailpit service is required. Existing invitation metadata is retained only for legacy privacy cleanup.

Other official docs were not edited. INTEGRATION-GUIDE.md still contains historical Mailpit setup instructions and DATABASE-SCHEMA.md still describes its legacy table; the current API specification and new-documentations/enrollment-initial-passwords.md describe the active behavior.

## Files changed during this audit

- docs/API-SPECIFICATION.md: invitation retirement and initial-password contract.
- module4-observability/src/components/dashboard/StudentSessionCalendar.tsx: type-check fixes.
- new-tests/test_dashboard_role_flow.py: connected multi-role flow regression.
- new-tests/admin-dashboard.test.mjs, ta-view.test.mjs, student-history-pagination.test.mjs and student-overview.test.mjs: current selectors, shared permission helper and query/navigation mocks.
- new-tests/run_session_regressions.py: explicitly routes both API URL variables to its disposable backend and keeps strict mode disabled for the published classroom contracts.
- new-tests/browser_enrollments.py, browser_exports.py and browser_checkins.py: current dashboard base path, assigned-course mocks and removed-summary expectations.
- This report.

No shared/Supabase test data was created by these test runs. No git commit or push was made.
