# Local Setup (self-contained, no external database)

The whole application runs on one machine with Docker Compose. The only database is the
bundled PostgreSQL 15 container. No Supabase account, cloud project or external database
is required.

| Service | Container | URL / host port |
|---|---|---|
| PostgreSQL 15 | `saiv-postgres` | `localhost:5434` (container `postgres:5432`) |
| Redis 7 | `saiv-redis` | `localhost:6380` |
| Backend API (Module 2) | `saiv-backend` | http://localhost:8000/docs |
| Face service (Module 3) | `saiv-face-recognition` | http://localhost:8001/docs |
| Student PWA (Module 1) | `saiv-frontend` | http://localhost:3000 |
| Dashboard (Module 4) | `saiv-dashboard` | http://localhost:8501 |
| Prometheus / Grafana | `saiv-prometheus` / `saiv-grafana` | http://localhost:9090 / http://localhost:3001 |

## 1. Fresh clone

Prerequisites: Docker Desktop (with Compose v2), Git. Python 3.11+ is needed only for the
test suites.

```powershell
git clone <repo-url>
cd SC3099-Capstone-Attendance-Application
Copy-Item .env.example .env        # optional: every value has a working default
# Edit .env and set JWT_SECRET to a random 32+ character string.
docker compose up -d --build
docker compose ps                  # postgres and redis should show "healthy"
```

The first build takes several minutes (face-service and frontend images).

## 2. Database initialization

There is no manual migration step for a fresh database. When the backend starts, it:

1. waits for the `postgres` health check (`depends_on: condition: service_healthy`);
2. runs SQLAlchemy `Base.metadata.create_all()`, which creates every table, foreign key,
   unique constraint and index defined in `module2-backend/app/models.py` and the
   feature modules (`device_binding.py`, `device_rotation.py`, `motion.py`,
   `push_notifications.py`, ...);
3. installs the `audit_logs` append-only trigger (`app/audit_storage.py`) as part of
   creating that table.

Check it:

```powershell
Invoke-RestMethod http://localhost:8000/health
docker compose exec postgres psql -U saiv -d saiv -c "\dt"
docker compose exec postgres psql -U saiv -d saiv -c "SELECT tgname FROM pg_trigger WHERE tgrelid = 'audit_logs'::regclass AND NOT tgisinternal;"
```

Optional follow-ups:

- **Venues.** The table starts empty. Load the confirmed starter venues with
  `Get-Content scripts/seed_local_venues.sql | docker compose exec -T postgres psql -U saiv -d saiv`.
- **Alembic.** Revision `20261107_01` only upgrades databases created before it existed.
  A fresh schema already includes everything in it. Running it is still safe if you want
  the version recorded:
  `docker compose exec backend alembic upgrade head`.
- The SQL files in `scripts/` and `module2-backend/migrations/*.sql` are for upgrading
  older hand-provisioned databases. A fresh local database does not need them.

## 3. First accounts

With `STRICT_SECURITY_MODE=false` (the default), the first admin can self-register:

```powershell
$body = @{ email = 'admin@example.com'; full_name = 'Local Admin'; password = '<strong password>'; role = 'admin' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/register -ContentType 'application/json' -Body $body
```

Registration is limited to 10 per IP per hour. After that, create instructors, TAs and
students as the admin from the dashboard. If you then set `STRICT_SECURITY_MODE=true`,
only student self-registration remains open.

## 4. Smoke test of the critical flows

With the stack running, either run the public suite (it creates its own test data in the
local database):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-test.txt
$env:TEST_BACKEND_URL = 'http://localhost:8000'; $env:TEST_FACE_URL = 'http://localhost:8001'
python -m pytest tests/public -v
```

or check by hand in the PWA (http://localhost:3000) and the dashboard (http://localhost:8501):
register/login, create a course, enroll students, create and start a session, check in
with face verification, review flagged check-ins, view statistics, and export the CSV.

## 5. Running the backend outside Docker (optional)

```powershell
docker compose up -d postgres redis face-recognition
cd module2-backend
Copy-Item .env.example .env
python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Stop the `backend` container first (`docker compose stop backend`) so port 8000 is free.

## 6. Reset or stop

```powershell
docker compose down        # stop; data is kept in the postgres_data volume
docker compose down -v     # stop AND delete all local data (fresh database next start)
```

## Moving an existing checkout off Supabase

Older checkouts kept a Supabase `DATABASE_URL` in the git-ignored files `.env` and
`module2-backend/.env`. Compose no longer reads `DATABASE_URL`, so the containers always
use local PostgreSQL. To finish the move:

1. In the root `.env`, delete the `DATABASE_URL=` line and copy any wanted values from
   `.env.example`.
2. Replace `module2-backend/.env` with `module2-backend/.env.example` (this matters only
   if you run the backend outside Docker).
3. `docker compose up -d --build`.

Data from the old hosted database is **not** copied over. The local database starts empty.
If the team needs the old data, the data owner can export it with `pg_dump` and restore it
with `docker compose exec -T postgres psql -U saiv -d saiv`. This is optional, and nothing
in the repository does it automatically.

## Troubleshooting

- **Port 5434, 6380, 8000 or 8001 already in use:** stop the other process. You can also
  set `POSTGRES_HOST_PORT` in `.env` to change the database port.
- **Password authentication failed after changing `POSTGRES_PASSWORD`:** the volume keeps
  the original credentials. Run `docker compose down -v` (this deletes local data) or
  change the password back.
- **Backend exits with `Security controls require REDIS_URL`:** start it through Compose,
  or set `REDIS_URL` in `module2-backend/.env`.
