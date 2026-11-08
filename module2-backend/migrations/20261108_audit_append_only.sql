-- PostgreSQL 14+ / Supabase. Apply explicitly in a transaction to an existing
-- deployment using its schema owner; fresh ORM schemas install this at creation.
-- No rows are changed. Audit inserts, selects and FK anchors remain available.
-- Use a nonowner runtime role with SELECT/INSERT only on audit_logs; do not grant
-- schema ownership, superuser, TRIGGER or permission to change this function.
CREATE OR REPLACE FUNCTION public.saiv_audit_append_only()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only; modification is forbidden'
        USING ERRCODE = '42501';
END;
$$;
CREATE OR REPLACE TRIGGER saiv_audit_no_mutation
BEFORE UPDATE OR DELETE OR TRUNCATE ON public.audit_logs
FOR EACH STATEMENT EXECUTE FUNCTION public.saiv_audit_append_only();
ALTER TABLE public.audit_logs ENABLE ALWAYS TRIGGER saiv_audit_no_mutation;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM PUBLIC;
