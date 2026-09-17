# Latency investigation — 17 September 2026

## Conclusion

Both network/database round-trip latency and avoidable application work contribute. The session check-in list failure was reproduced using the actual handler with a read-only Supabase connection. The check-in write path was profiled locally; no check-in was inserted into Supabase during this investigation.

The reported failures were check-in at approximately 2.46 seconds (limit 2s) and session check-in list at approximately 1.33 seconds (limit 1s). These tests send no biometric image, so they do not exercise Module 3 or browser camera processing. Despite the test module's p95 description, the individual tests assert a single request's elapsed time.

## Measurements

Read-only probes used the configured database, without importing the application's startup against it, creating tables, modifying records, or printing credentials/row data. Handler profiling used an isolated in-process app, real database queries, and an existing session; it excludes browser-to-backend/deployed HTTP latency. The diagnostic environment used SQLAlchemy 2.0.54 and psycopg2 2.9.13, rather than the project's exact older pins, so deployment timings should be rechecked there.

| Measurement | Result |
| --- | --- |
| Fresh engine connection, including initialization | 4.624s |
| SELECT 1 as first statement of a transaction, six samples | 0.522–0.615s |
| Rollback ending those transactions | 0.260–0.355s |
| Representative joined session/check-in/user query: server execution | 15.116ms |
| Representative user lookup: server execution | 0.898ms |
| Session list handler, current transaction mode, four samples | 1.156s, 1.136s, 1.170s, 1.274s |
| Same handler, experimental read-only AUTOCOMMIT binding | 0.530s, 0.814s, 0.789s, 0.938s |

The joined query plan was a representative projection, not an EXPLAIN of every exact ORM column. First-statement times include implicit transaction startup. A second pool-reset rollback was observed but took about 0.01ms: it must not be counted as another full network trip. Mode-switch/reset overhead remains in the experimental total. Four samples are evidence of an improvement, not a p95 guarantee.

Locally, warm SQLite requests were about 3–5ms for check-in and 2ms for session check-in lists. Password verification took about 300ms, but neither of the two reported endpoint timers includes a login request.

## Confirmed implementation findings

1. **Post-commit user reload in `create_checkin`.** `db.commit()` expires ORM state; subsequently reading `current_user.id` while constructing the response issues another user SELECT and opens a new read transaction. This exists in HEAD before the motion feature too. Save the student ID in a local variable before committing. Do not globally disable transaction semantics as a workaround.
2. **Additional motion-policy SELECT.** The recent motion integration calls `motion.required(db, session.id)` separately, adding a query to ordinary image-free check-ins. This is an overhead introduced by the motion implementation, not an explanation for older teammate failures. Fold the policy into the existing session/course lookup with a LEFT JOIN or correlated expression, retaining strict enforcement for required-motion sessions.
3. **Session list is not N+1.** The trace contains one authentication user SELECT and one joined session/check-in/student SELECT, regardless of the number of returned check-ins in this code path. Its read transaction startup and rollback consume much of the 1s budget on this connection.

A temporary-copy prototype of fixes 1–2 reduced the check-in statement count from **5 (four SELECTs + INSERT) to 3 (two SELECTs + INSERT)** and removed the post-commit read transaction. It retained HTTP 201 in local profiling. Before the motion feature, the count was 4. This prototype was not applied to the working source and has not been benchmarked as a write against Supabase.

## Recommended changes

- Apply the two targeted check-in query reductions and cover query counts plus motion enforcement in regression tests.
- For the session-list endpoint, evaluate a dedicated read-only database session/engine using DBAPI AUTOCOMMIT, shared by authentication and the read handler. Preserve ordinary transactions for check-in writes and atomic motion-proof consumption. Do not switch the entire application's database engine to autocommit.
- Keep backend and database geographically close and measure connection establishment separately from warm requests. Connection recycling at 280 seconds can introduce reconnects, though the observed fresh-engine initialization time is not a measurement of every recycled connection.
- Repeat the original tests with the deployed/pinned environment and collect multiple samples before declaring a p95 target satisfied. Do not loosen the test thresholds to hide excess round trips.

SQLAlchemy documents DBAPI autocommit and isolation-level switching here:
https://docs.sqlalchemy.org/en/20/core/connections.html#understanding-the-dbapi-level-autocommit-isolation-level

## Changes made during the initial investigation

No application code, test thresholds, or Supabase data was changed. Profiling scripts, temporary databases, and prototype code were created only under the temporary directory. This report is the only new repository file for the investigation.


## Optimization applied after baseline verification

The initial findings above describe the pre-optimization implementation. The
following changes have now been applied in Module 2:

- Check-in LEFT JOINs the optional motion policy into its existing session query.
  A missing policy remains optional; required-motion enforcement is preserved.
- The response uses a student ID saved before commit, eliminating the implicit
  post-commit user reload and its additional transaction.
- Only `GET /api/v1/checkins/session/{session_id}` opts into `get_read_db` and
  read-mode authentication. Both share the same dependency/session. Token,
  active-account, and database-role checks use the original authentication code.
- The read factory uses DBAPI AUTOCOMMIT on an option engine sharing the original
  pool; SQLAlchemy restores isolation when the connection returns. This factory
  is intended only for read handlers, not for writes or snapshot-dependent
  multi-statement work. Existing write sessions remain transactional, including
  atomic challenge consumption plus attendance insertion.

Baseline verification ran before editing application code: **7 existing
performance tests passed, 1 was already skipped**, and **26 focused checks
passed**, with the check-in baseline explicitly asserting 5 SQL statements.
After the changes, the query budget is a fixed 3 statements. The expanded
**28 focused checks passed** using the project's pinned backend requirements
(SQLAlchemy 2.0.25, psycopg2 2.9.9, FastAPI 0.109.0, Pydantic 2.5.3 on Python 3.12).
These include role/token/account rejection, 404 behaviour, constant query count
at 0/1/20 check-ins, motion requirements, expiry/reuse, transaction rollback,
and read-mode scoping. Test thresholds were not changed.

Six read-only Supabase measurements of the implemented handler using those
pinned dependencies were **0.540, 0.879, 0.863, 0.883, 0.788, 0.791 seconds**.
All returned HTTP 200. This is a small warm-connection sample, not a guarantee
against cold connections or network jitter. No Supabase check-in writes or
schema migrations were performed during verification.

Final regression run against an isolated backend with pinned dependencies:
**65 passed, 1 existing skip**, covering API functionality, security, privacy,
frontend/dashboard contracts, integration, performance, and refresh cookies.
The backend test wrapper also passed after final review. A read-only PostgreSQL
connection test confirmed the pooled DBAPI `autocommit` flag transitions
`false → true → false` before/during/after the read path; the base engine's
transaction mode is restored. Check-in write timing was verified locally and
by query counts, not by inserting attendance into Supabase.
