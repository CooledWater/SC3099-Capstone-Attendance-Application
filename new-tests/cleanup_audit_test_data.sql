-- ONE-OFF cleanup: test data written to the shared database by
-- new-tests/test_audit_logs.py when it was accidentally run against the dev
-- server on localhost:8000 (delete this file once it has been used).
--
-- What it removes - only rows that trace back to the test fixtures:
--   * users whose email ends in @audit-test.com
--   * the "Audit Course" (code AU + 8 hex chars) taught by one of those users,
--     its sessions, enrollments and check-ins
--   * those users' devices and audit_logs, plus audit rows about those
--     resources and failed-login rows for @audit-test.com addresses
-- Real users' rows are never matched.
--
-- audit_logs is append-only by design; direct SQL is the only way to delete
-- from it, which is what this deliberately does for test rows only.
--
-- Usage (psql or the Supabase SQL editor): run the whole script. It ends in
-- ROLLBACK so nothing is deleted until you have read the "before" and "after"
-- counts; change the last line to COMMIT to keep the deletions.

BEGIN;

CREATE TEMP TABLE t_users    AS SELECT id FROM users WHERE email LIKE '%@audit-test.com';
CREATE TEMP TABLE t_courses  AS SELECT id FROM courses
    WHERE name = 'Audit Course' AND code LIKE 'AU%' AND length(code) = 10
      AND instructor_id IN (SELECT id FROM t_users);
CREATE TEMP TABLE t_sessions AS SELECT id FROM sessions WHERE course_id IN (SELECT id FROM t_courses);
CREATE TEMP TABLE t_checkins AS SELECT id FROM checkins
    WHERE session_id IN (SELECT id FROM t_sessions) OR student_id IN (SELECT id FROM t_users);
CREATE TEMP TABLE t_enrolls  AS SELECT id FROM enrollments
    WHERE course_id IN (SELECT id FROM t_courses) OR student_id IN (SELECT id FROM t_users);
CREATE TEMP TABLE t_devices  AS SELECT id FROM devices WHERE user_id IN (SELECT id FROM t_users);

CREATE TEMP TABLE t_audit AS SELECT id FROM audit_logs
    WHERE user_id IN (SELECT id FROM t_users)
       OR resource_id IN (SELECT id FROM t_users)
       OR resource_id IN (SELECT id FROM t_sessions)
       OR resource_id IN (SELECT id FROM t_checkins)
       OR resource_id IN (SELECT id FROM t_enrolls)
       OR resource_id IN (SELECT id FROM t_devices)
       OR (user_id IS NULL AND details LIKE '%@audit-test.com%');

-- BEFORE: expect roughly a dozen users, 1 course, 1 session, 2 enrollments,
-- 2 check-ins, 1 device and ~50 audit rows. If a number looks far too big,
-- stop and ROLLBACK.
SELECT 'users' AS what, count(*) FROM t_users
UNION ALL SELECT 'courses',     count(*) FROM t_courses
UNION ALL SELECT 'sessions',    count(*) FROM t_sessions
UNION ALL SELECT 'enrollments', count(*) FROM t_enrolls
UNION ALL SELECT 'checkins',    count(*) FROM t_checkins
UNION ALL SELECT 'devices',     count(*) FROM t_devices
UNION ALL SELECT 'audit_logs',  count(*) FROM t_audit;

-- Children first (foreign keys).
DELETE FROM audit_logs WHERE id IN (SELECT id FROM t_audit);
DELETE FROM motion_challenges WHERE user_id IN (SELECT id FROM t_users) OR session_id IN (SELECT id FROM t_sessions);
DELETE FROM session_motion_policies WHERE session_id IN (SELECT id FROM t_sessions);
DELETE FROM checkins WHERE id IN (SELECT id FROM t_checkins);
DELETE FROM enrollments WHERE id IN (SELECT id FROM t_enrolls);
DELETE FROM devices WHERE id IN (SELECT id FROM t_devices);
DELETE FROM sessions WHERE id IN (SELECT id FROM t_sessions);
DELETE FROM courses WHERE id IN (SELECT id FROM t_courses);
DELETE FROM users WHERE id IN (SELECT id FROM t_users);

-- AFTER: every count must be 0.
SELECT 'users left' AS what, count(*) FROM users WHERE email LIKE '%@audit-test.com'
UNION ALL SELECT 'audit rows left', count(*) FROM audit_logs WHERE id IN (SELECT id FROM t_audit)
UNION ALL SELECT 'audit rows for test users left', count(*) FROM audit_logs
    WHERE user_id IN (SELECT id FROM t_users);

ROLLBACK;  -- change to COMMIT once the counts above look right
