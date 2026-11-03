-- Backfill existing devices for the device trust/approval rules (PostgreSQL / Supabase).
--
-- Rules now enforced by the backend: a user's 1st device is HIGH and auto-approved, the 2nd
-- is LOW and pending admin approval (check-ins allowed but flagged), and registrations beyond
-- two active devices are rejected unless an admin approves an exception.
--
-- Before this change every newly registered device started untrusted ("low"). Without this
-- backfill nothing breaks: existing unapproved devices keep checking in, flagged, exactly as
-- before. The backfill gives each existing user's FIRST device the trust it would get today.
--
-- What it does:
--   1. For each user whose earliest active, non-removed device is unapproved, approve that one
--      device (is_trusted = true, trust_score = 'high') - but ONLY if the user has no approved
--      active device AND no device of theirs ever had an admin trust decision (approve/revoke).
--      An admin revocation is never undone, and a user whose first device was revoked does not
--      get a later device approved in its place.
--   2. Normalise trust_score so approved devices are 'high' and unapproved ones 'low' (no MEDIUM).
--   Nothing else changes: no rows are inserted or deleted, no schema change; users, courses,
--   sessions, enrollments, check-ins and audit logs are untouched.
--
-- Admin trust decisions are read from audit_logs: PATCH /devices/{id} logs
-- action 'device_registered' with details JSON containing "changes": {"is_trusted": ...}.
-- A plain text match is used so legacy non-JSON details can never make the script fail.
--
-- Re-runnable: a second run approves nothing (approved users are skipped, and any device an
-- admin later revokes has an audit record). Runs in one transaction that ROLLS BACK by default:
-- review the preview, then change the final ROLLBACK to COMMIT.
-- Do not run against the shared Supabase database without team sign-off.

BEGIN;

CREATE TEMP TABLE device_trust_backfill ON COMMIT DROP AS
WITH first_active AS (
    SELECT DISTINCT ON (d.user_id) d.id, d.user_id, d.is_trusted
    FROM devices d
    WHERE d.is_active = true
      AND (d.revocation_reason IS NULL OR d.revocation_reason <> 'device_removed')
    ORDER BY d.user_id, d.first_seen_at, d.id
)
SELECT f.id, f.user_id
FROM first_active f
WHERE f.is_trusted = false
  AND NOT EXISTS (
      SELECT 1 FROM devices t
      WHERE t.user_id = f.user_id AND t.is_active = true AND t.is_trusted = true
  )
  AND NOT EXISTS (
      SELECT 1
      FROM audit_logs a
      JOIN devices o ON o.id = a.device_id
      WHERE o.user_id = f.user_id
        AND a.action = 'device_registered'
        AND a.details LIKE '%"is_trusted"%'
  );

-- Preview: devices step 1 will approve.
SELECT b.id AS device_id, u.email, u.role, d.device_name, d.first_seen_at
FROM device_trust_backfill b
JOIN devices d ON d.id = b.id
JOIN users u ON u.id = b.user_id
ORDER BY u.email;

-- 1. Approve each eligible user's first device.
UPDATE devices d
SET is_trusted = true, trust_score = 'high'
FROM device_trust_backfill b
WHERE d.id = b.id;

-- 2. Keep trust_score consistent with approval (no MEDIUM level).
UPDATE devices SET trust_score = 'high' WHERE is_trusted = true AND trust_score <> 'high';
UPDATE devices SET trust_score = 'low' WHERE is_trusted = false AND trust_score <> 'low';

-- Verification: per-user summary after the backfill.
SELECT u.email,
       count(*) FILTER (WHERE d.is_active AND d.is_trusted)     AS approved_active,
       count(*) FILTER (WHERE d.is_active AND NOT d.is_trusted) AS pending,
       count(*) FILTER (WHERE NOT d.is_active)                   AS inactive_or_removed
FROM devices d JOIN users u ON u.id = d.user_id
GROUP BY u.email
ORDER BY u.email;

ROLLBACK;  -- Change to COMMIT once the preview looks right.
