-- Session-level TA assignments (PostgreSQL / Supabase). NOT executed automatically.
--
-- Adds session_assistants, matching app/models.py SessionAssistant. A TA can reach a
-- session only through a row here AND a course_assistants row for the session's course,
-- so removing a TA from a course revokes every session in it (the API also deletes the
-- rows). Existing course_assistants rows are untouched.
--
-- Effect on deploy: TAs who are assigned to courses but have no session rows will see
-- ZERO sessions until an admin assigns sessions via
--   POST /api/v1/admin/courses/{course_id}/tas/{user_id}/sessions
--
-- Note: the backend's startup create_all() also creates this table the first time the
-- new code runs against a database, so run this only if you deploy the schema by hand.
-- Requires course_assistants (created the same way) for the access rule to grant anything.
-- Safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS session_assistants (
    id          VARCHAR(36) PRIMARY KEY,
    session_id  VARCHAR(36) NOT NULL REFERENCES sessions (id),
    user_id     VARCHAR(36) NOT NULL REFERENCES users (id),
    created_at  TIMESTAMP   NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

-- Prevents duplicate assignments; also serves session -> TAs lookups.
CREATE UNIQUE INDEX IF NOT EXISTS ix_session_assistants_session_user
    ON session_assistants (session_id, user_id);

-- TA -> sessions lookups used by every TA access check.
CREATE INDEX IF NOT EXISTS ix_session_assistants_user_id
    ON session_assistants (user_id);

-- Verification.
SELECT count(*) AS session_assistant_rows FROM session_assistants;

COMMIT;
