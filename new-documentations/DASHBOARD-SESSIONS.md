# Dashboard sessions

Module 1 keeps its existing `/api/v1/auth/login`, `/refresh`, and `/logout`
flow and the HttpOnly `saiv_refresh_token` cookie at `/api/v1/auth`.

Module 4 uses these additional POST endpoints:

| Endpoint | Behavior |
| --- | --- |
| `/api/v1/auth/dashboard/login` | Same credentials/response as ordinary login; sets only the dashboard cookie. |
| `/api/v1/auth/dashboard/refresh` | Restores/renews only the dashboard session. |
| `/api/v1/auth/dashboard/student-session` | Reads the SAIV cookie, verifies an active student in the database, and creates a separate dashboard session without replacing the SAIV cookie. |
| `/api/v1/auth/dashboard/logout` | Clears only the dashboard cookie. |

The dashboard cookie is `saiv_dashboard_refresh_token`, HttpOnly, SameSite=Lax,
with path `/api/v1/auth/dashboard` and the existing seven-day expiry/Secure
configuration. Signed refresh tokens identify their app. Dashboard tokens are
rejected by ordinary SAIV refresh, including its JSON-body compatibility path.
Older unscoped tokens remain valid for SAIV and the student-only bridge.

On opening the dashboard, an existing dashboard session takes precedence.
Otherwise, an active SAIV student can enter automatically. TA, instructor, and
admin SAIV sessions cannot enter automatically; they use dashboard login.
Any role may explicitly log into the dashboard. No dashboard login creates a
SAIV cookie. Existing bearer-token permissions remain enforced by Module 2.

Dashboard logout suppresses automatic student entry in the current tab until
an explicit dashboard login or the tab's session storage is cleared. Module 1
logout leaves the separate dashboard session intact. Access tokens are still
not revoked server-side, consistent with the existing authentication contract.

Access tokens live only in module memory, like Module 1. Reloading the page
restores them through the dashboard's HttpOnly refresh cookie. Neither access
nor refresh tokens are written to localStorage or sessionStorage; sessionStorage
holds only the dashboard sign-out preference.

Upgrade: old dashboard access-token storage is removed. Staff sign into the
dashboard again. If a previous dashboard login already replaced the old SAIV
cookie, sign out/in to Module 1 once as the intended student to correct it.

Validation:

- `node --test new-tests/dashboard-auth-client.test.mjs`
- In a disposable backend container with the repository mounted at `/workspace`:
  `python -m pytest new-tests/backend_dashboard_auth_cases.py -q -p no:cacheprovider`
- In the same environment: `python new-tests/run_dashboard_auth_regressions.py`
  (runs existing public auth/authorization and cookie tests against a temporary
  SQLite backend; does not access the configured attendance database).

Modules 1 and 3 are unchanged. Timestamp display is a separate pending task.
