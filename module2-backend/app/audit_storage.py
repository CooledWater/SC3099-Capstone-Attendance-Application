"""Storage-level append-only guards for fresh schemas and Alembic upgrades."""


def install_audit_guards(connection):
    dialect = connection.dialect.name
    if dialect == 'postgresql':
        statements = (
            """CREATE OR REPLACE FUNCTION saiv_audit_append_only() RETURNS trigger
               LANGUAGE plpgsql AS $$ BEGIN
                 RAISE EXCEPTION 'audit_logs rows are immutable (append-only)'
                   USING ERRCODE = '42501';
               END; $$""",
            'DROP TRIGGER IF EXISTS saiv_audit_append_only ON audit_logs',
            """CREATE TRIGGER saiv_audit_append_only
               BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_logs
               FOR EACH STATEMENT EXECUTE FUNCTION saiv_audit_append_only()""",
            'ALTER TABLE audit_logs ENABLE ALWAYS TRIGGER saiv_audit_append_only',
        )
    elif dialect == 'sqlite':
        statements = tuple(
            f"""CREATE TRIGGER IF NOT EXISTS saiv_audit_no_{operation.lower()}
                BEFORE {operation} ON audit_logs BEGIN
                SELECT RAISE(ABORT, 'audit_logs rows are immutable (append-only)'); END"""
            for operation in ('UPDATE', 'DELETE')
        ) + (
            # SQLite REPLACE otherwise silently deletes a conflicting row when
            # recursive_triggers is off (the SQLite default).
            """CREATE TRIGGER IF NOT EXISTS saiv_audit_no_replace
               BEFORE INSERT ON audit_logs WHEN EXISTS (SELECT 1 FROM audit_logs WHERE id = NEW.id)
               BEGIN SELECT RAISE(ABORT, 'audit_logs rows are immutable (append-only)'); END""",
        )
    else:
        raise RuntimeError('Append-only audit protection requires PostgreSQL or SQLite')
    for statement in statements:
        connection.exec_driver_sql(statement)
