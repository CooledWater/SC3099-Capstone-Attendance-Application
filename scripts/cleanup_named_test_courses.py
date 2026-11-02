"""Approved one-off cleanup; run in the backend environment with --apply.

Matches only the complete course name 'Test course', ignoring case and outer
whitespace. User accounts, devices and audit records are never deleted.
Without --apply, the transaction rolls back after reporting affected counts.
"""
import json
import sys

from sqlalchemy import bindparam, text
from app.database import engine


DEPENDENCIES = [
    ("push_deliveries", "checkin_id", "checkins"),
    ("device_challenges", "session_id", "sessions"),
    ("motion_challenges", "session_id", "sessions"),
    ("session_motion_policies", "session_id", "sessions"),
    ("account_invitations", "course_id", "courses"),
    ("course_assistants", "course_id", "courses"),
    ("enrollments", "course_id", "courses"),
]


def cleanup(apply=False):
    if engine.dialect.name != "postgresql" or "supabase" not in (engine.url.host or ""):
        raise RuntimeError("Expected the configured Supabase PostgreSQL database")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            course_ids = list(connection.execute(text(
                "SELECT id FROM courses WHERE lower(trim(name)) = :name FOR UPDATE"
            ), {"name": "test course"}).scalars())

            def values(sql, ids):
                if not ids:
                    return []
                return list(connection.execute(
                    text(sql).bindparams(bindparam("ids", expanding=True)), {"ids": ids}
                ).scalars())

            ids = {"courses": course_ids}
            ids["sessions"] = values("SELECT id FROM sessions WHERE course_id IN :ids FOR UPDATE", course_ids)
            ids["checkins"] = values("SELECT id FROM checkins WHERE session_id IN :ids FOR UPDATE", ids["sessions"])
            other_courses_before = set(connection.execute(text(
                "SELECT id FROM courses WHERE lower(trim(name)) <> :name"
            ), {"name": "test course"}).scalars())
            counts = {}
            for table, column, parent in DEPENDENCIES:
                # Identifiers come only from the constant whitelist above.
                related_counts = values(f"SELECT count(*) FROM {table} WHERE {column} IN :ids", ids[parent])
                counts[table] = related_counts[0] if related_counts else 0
                if apply and counts[table]:
                    connection.execute(text(f"DELETE FROM {table} WHERE {column} IN :ids").bindparams(
                        bindparam("ids", expanding=True)), {"ids": ids[parent]})
            for table in ("checkins", "sessions", "courses"):
                counts[table] = len(ids[table])
                if apply and ids[table]:
                    connection.execute(text(f"DELETE FROM {table} WHERE id IN :ids").bindparams(
                        bindparam("ids", expanding=True)), {"ids": ids[table]})
            remaining = connection.execute(text(
                "SELECT count(*) FROM courses WHERE lower(trim(name)) = :name"
            ), {"name": "test course"}).scalar_one()
            other_courses_after = set(connection.execute(text(
                "SELECT id FROM courses WHERE lower(trim(name)) <> :name"
            ), {"name": "test course"}).scalars())
            if apply and remaining:
                raise RuntimeError("Matching courses remain; rolling back")
            if other_courses_before != other_courses_after:
                raise RuntimeError("Non-target courses changed; rolling back")
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
            print(json.dumps({"applied": apply, "affected_records": counts,
                              "matching_courses_remaining": remaining,
                              "other_courses_preserved": len(other_courses_after)}))
        except BaseException:
            if transaction.is_active:
                transaction.rollback()
            raise


if __name__ == "__main__":
    cleanup(apply="--apply" in sys.argv)
