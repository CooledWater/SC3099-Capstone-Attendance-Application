# Admin weekly analytics

The admin graphs cover Monday–Sunday in the application timezone. There are no monthly controls. The week selector applies a typed date on blur or Enter, normalized to Monday.

## Endpoints and counting

- Existing `GET /stats/overview?days=30` supplies KPIs and timezone.
- `GET /stats/overview?include_course_participation=true&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` supplies both graphs in two aggregate SQL reads regardless of course count. This projection requires admin access and exactly seven calendar days; end_date is exclusive. Ordinary overview responses retain their existing contract.
- Daily counts use check-in timestamps converted to application timezone, include every verification status, zero-fill elapsed days, and leave future days null. Today remains partial in the tooltip; the explanatory footer is removed.
- Course participation includes active and closed sessions starting within the selected week. It sums recorded check-ins and saved expected student-session attendances separately. It never averages percentages or substitutes approved-only records.
- `GET /sessions/` adds `saved_expected_attendance` to session summaries. The admin's existing system-wide course table uses these saved counts for held sessions. Existing `total_enrolled` retains its current-enrollment meaning for other consumers.
- No eligible sessions, missing snapshots, or a zero denominator shows No data. Missing snapshots return expected_attendances=null, never an invented zero. Rates remain uncapped. Above-100% values are labelled and kept visible against the fixed chart axis.
- The unique database index `ix_checkins_session_student` prevents duplicate student/session submissions. Attempts do not inflate record counts.
- Course clicks still open the existing analytics view. The default instructor/course statistics endpoints retain their documented current-enrollment semantics; this change scopes historical denominators to the admin overview and its system-wide course table.

## Approved historical denominator change

The user explicitly approved departing from the documented current-active-enrollment denominator in this conversation. Official files under docs remain unchanged and read-only.

The additive `session_attendance_snapshots` table stores one row per session: session_id (primary key, sessions FK with ON DELETE CASCADE), expected_attendances (integer), captured_at (UTC timestamp), and historical_enrollment_limited (boolean). No student identifiers or personal data are copied into snapshots. The existing Base.metadata.create_all startup creates the table.

The lifecycle reconciliation captures missing snapshots for started active/closed sessions before its transaction commits, including startup backfill. Enrollment create, bulk-create and drop paths capture missing held-session snapshots before changing enrollment records. The last successful enrollment_added/enrollment_removed audit event at or before scheduled_start determines eligibility; available enrollment intervals are the fallback. Students are counted once. Enrollment mutations and later clock ticks never overwrite an existing snapshot. Concurrent workers use INSERT ON CONFLICT DO NOTHING, so the first saved denominator wins.

The first backfill cannot recover enrollment rows or intervals that were overwritten/deleted before audit collection. Captures delayed more than five seconds after scheduled_start conservatively carry historical_enrollment_limited=true. These are stable approximations from available history, not a claim of complete historical reconstruction. Later enrollment changes cannot alter their saved counts. Recorded check-ins remain the numerator and are not used to invent enrollment membership. Future sessions are not frozen before scheduled_start; an early manually active/closed session has an unknown denominator until then.

The requested enrollment warning, all-status subtitle suffix, partial-day footer, included-session tooltip count, and closed-only tooltip line are removed. Active-session tooltips still indicate provisional participation.

## Presentation and verification

Purple straight line segments and markers, whole-number count ticks, percentage bars with a fixed 0–100% axis, readable course labels and contained scrolling are retained. Request failures show Retry rather than zeros. The browser uses one chart request, caches for 30 seconds and retries once. No new routes were added.

Regression coverage is in new-tests/test_attendance_snapshots.py, test_admin_weekly_charts.py, test_session_lifecycle.py and admin-overview-charts.test.mjs. All backend regression fixtures use isolated SQLite databases; no public integration fixtures are run against Supabase.
