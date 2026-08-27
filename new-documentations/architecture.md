# SAIV — System Architecture

**System:** SAIV — Secure Attendance & Identity Verification
**Version:** 1.0
**Companion document:** [`prd.md`](./prd.md)

---

## 1. Architectural Overview

SAIV is a **microservice system of four independently deployable modules** plus a shared infrastructure tier, all orchestrated by Docker Compose on a single bridge network. Every module communicates over HTTP; no module shares in-process state with another.

Three principles shape the design:

**1. The Backend API is the single point of authority.** Clients never call the Face Recognition service directly. The Backend owns authentication, authorization, business rules, and persistence, and it orchestrates the ML service as a subordinate. This keeps the trust boundary in one place: an attacker who reaches the face service directly cannot mint an attendance record, because only the Backend writes to the database.

**2. Service contracts are HTTP, not code.** Modules are validated purely by black-box HTTP behaviour. A team may implement any module in any language — the contract is the request/response shape, the status code, and the latency budget. This is why the architecture specifies *ports and payloads* rather than classes and interfaces.

**3. Sensitive data narrows as it flows inward.** A raw face image exists in exactly two places — the browser that captured it, and the memory of the face service that processes it. It is never written to disk, never persisted, and never returned. What crosses into storage is a fixed-length hash.

---

## 2. System Architecture Diagram

```mermaid
flowchart TB
    subgraph clients["Client Tier"]
        student["Student<br/>mobile browser"]
        instructor["Instructor<br/>desktop browser"]
    end

    subgraph app["Application Tier — student-implemented modules"]
        m1["<b>Module 1 — Frontend PWA</b><br/>Next.js 14 · React 18 · TypeScript<br/>WebRTC · Geolocation · Service Worker<br/><i>:3000</i>"]
        m2["<b>Module 2 — Backend API</b><br/>FastAPI · SQLAlchemy · Pydantic<br/>JWT · RBAC · rate limiting · audit<br/><i>:8000</i>"]
        m3["<b>Module 3 — Face Recognition &amp; Risk</b><br/>FastAPI · MediaPipe · OpenCV · NumPy<br/>enroll · verify · liveness · risk fusion<br/><i>:8001</i>"]
        m4["<b>Module 4 — Instructor Dashboard</b><br/>Streamlit · Pandas · Plotly<br/>sessions · review · analytics · export<br/><i>:8501</i>"]
    end

    subgraph data["Data Tier"]
        pg[("PostgreSQL 15<br/>8 tables<br/><i>:5434 → 5432</i>")]
        redis[("Redis 7<br/>rate-limit counters<br/><i>:6380 → 6379</i>")]
    end

    subgraph obs["Observability Tier"]
        otel["OTel Collector<br/><i>:4317 gRPC · :4318 HTTP</i>"]
        prom["Prometheus<br/><i>:9090</i>"]
        graf["Grafana<br/><i>:3001</i>"]
    end

    student -->|"HTTPS-less HTTP<br/>JWT bearer"| m1
    instructor -->|"HTTP session"| m4

    m1 -->|"REST /api/v1/*<br/>JWT · 30s timeout"| m2
    m4 -->|"REST /api/v1/*<br/>JWT · 30s timeout"| m2
    m2 -->|"internal REST<br/>no auth · 5s timeout"| m3

    m2 -->|"SQLAlchemy ORM<br/>pool 10+20 · 10s"| pg
    m2 -->|"TTL counters<br/>2s timeout"| redis
    m4 -.->|"read-only SQL<br/>for bulk export"| pg
    m4 -->|"PromQL /api/v1/query"| prom

    m2 -.->|"OTLP traces"| otel
    m3 -.->|"OTLP traces"| otel
    prom -.->|"scrape /metrics 15s"| m2
    prom -.->|"scrape /metrics 15s"| m3
    graf -->|"datasource"| prom

    classDef mod fill:#1f6feb22,stroke:#1f6feb,stroke-width:2px
    classDef store fill:#8957e522,stroke:#8957e5,stroke-width:2px
    classDef obsv fill:#d2992222,stroke:#d29922,stroke-width:2px
    classDef cli fill:#2da44e22,stroke:#2da44e,stroke-width:2px
    class m1,m2,m3,m4 mod
    class pg,redis store
    class otel,prom,graf obsv
    class student,instructor cli
```

### 2.1 Text Rendering of the Same Topology

```
                 ┌──────────────────┐        ┌──────────────────┐
                 │  Student Browser │        │Instructor Browser│
                 │     (mobile)     │        │    (desktop)     │
                 └────────┬─────────┘        └────────┬─────────┘
                          │ HTTP                      │ HTTP
                          ▼                           ▼
        ┌─────────────────────────────┐  ┌─────────────────────────────┐
        │  MODULE 1: Frontend PWA     │  │  MODULE 4: Dashboard        │
        │  Next.js / React / TS       │  │  Streamlit / Pandas / Plotly│
        │  :3000                      │  │  :8501                      │
        └──────────────┬──────────────┘  └───┬──────────────┬──────────┘
                       │ REST + JWT           │ REST + JWT   │ PromQL
                       │                      │              │
                       ▼                      ▼              │
        ┌──────────────────────────────────────────────┐     │
        │  MODULE 2: Backend API   (FastAPI)  :8000    │     │
        │  ─────────────────────────────────────────   │     │
        │  auth · RBAC · courses · sessions · checkins │     │
        │  geofence · risk fusion · audit · export     │     │
        └───┬───────────────┬──────────────┬───────────┘     │
            │ internal REST │ ORM          │ TTL counters    │
            │ (no auth, 5s) │              │                 │
            ▼               ▼              ▼                 │
   ┌──────────────────┐  ┌──────────┐  ┌─────────┐           │
   │  MODULE 3:       │  │PostgreSQL│  │  Redis  │           │
   │  Face Recognition│  │  :5434   │◄─┼─ ─ ─ ─ ─┼─ ─ ─ ─ ─ ─┘
   │  FastAPI +       │  │ 8 tables │  │  :6380  │  (M4 read-only SQL)
   │  MediaPipe :8001 │  └──────────┘  └─────────┘
   └────────┬─────────┘
            │
            │  ┌────────── OBSERVABILITY ──────────┐
            └─►│ OTel Collector :4317/:4318        │
               │ Prometheus :9090 ─► Grafana :3001 │
               └───────────────────────────────────┘
```

---

## 3. Technology Stack

The project is deliberately **technology-agnostic**: tests exercise HTTP endpoints only, so any language that serves HTTP qualifies. The stack below is the recommended baseline, scaffolded in the starter repository.

### 3.1 Module 1 — Frontend PWA

| Concern | Technology | Why |
|---------|-----------|-----|
| Framework | Next.js 14 (App Router) | File-based routing, built-in PWA-friendly build output, React Server Components where useful |
| Language | TypeScript 5 | Compile-time safety on API response shapes, which are contract-critical |
| UI | React 18 + Tailwind CSS 3 | Component model plus utility-first styling for fast mobile layout |
| HTTP client | Axios 1.6 | Interceptors make transparent 401 → refresh → retry straightforward |
| JWT handling | `jose` 5 | Decoding/validating tokens client-side without a heavyweight dependency |
| Offline storage | `localforage` 1.10 | IndexedDB wrapper with a localStorage-shaped API |
| Camera | WebRTC `MediaDevices.getUserMedia()` | Browser-native camera access; frames drawn to `<canvas>` and exported as base64 JPEG |
| Location | Geolocation API `getCurrentPosition()` | Latitude, longitude, and an accuracy figure the risk engine consumes |
| Permissions | Permissions API `navigator.permissions.query()` | Lets the app check state before prompting, enabling "explain first, then ask" |
| PWA | Service Worker + Web App Manifest | Installable, offline-capable app shell |

**Caching discipline.** The service worker caches static assets and the app shell (cache-first) but must never cache authentication responses or check-in submissions — a check-in is inherently real-time and a replayed cached response would be an attendance forgery.

### 3.2 Module 2 — Backend API

| Concern | Technology | Why |
|---------|-----------|-----|
| Framework | FastAPI 0.109 | Async-native, automatic OpenAPI docs at `/docs`, Pydantic-integrated validation |
| Server | Uvicorn 0.27 (standard) | ASGI server with production-grade concurrency |
| ORM | SQLAlchemy 2.0 | Parameterized queries by construction — the SQL-injection defense is structural, not a filter |
| Migrations | Alembic 1.13 | Versioned, reversible schema evolution |
| DB driver | psycopg2-binary 2.9 | Mature PostgreSQL adapter |
| Validation | Pydantic 2.5 + email-validator | Declarative schemas produce the required 422 responses listing every invalid field |
| JWT | python-jose 3.3 (cryptography) | HS256 signing and verification |
| Passwords | passlib 1.7 + bcrypt 4.1 | Bcrypt at cost ≥ 10 — deliberately ~100 ms per hash to blunt brute force |
| Cache / limits | redis-py 5.0 | Atomic `INCR` + `EXPIRE` pipeline for TTL-window rate limiting |
| Outbound HTTP | httpx 0.26 | Async client with per-call timeouts for the face-service hop |
| Geodesy | geopy 2.4 | Haversine great-circle distance for geofencing |
| Metrics | prometheus-client 0.19 | `/metrics` exposition |
| Tracing | OpenTelemetry SDK 1.22 + FastAPI/SQLAlchemy instrumentation | Spans across the HTTP hop and down to individual queries |

### 3.3 Module 3 — Face Recognition & Risk

| Concern | Technology | Why |
|---------|-----------|-----|
| Framework | FastAPI 0.109 + Uvicorn | Same async model; the service is CPU-bound per request but IO-served |
| Face detection | MediaPipe ≥ 0.10.9 | Pre-trained detection plus the 468-landmark Face Mesh with **z-coordinates**, which is what makes single-image depth analysis possible |
| Image processing | OpenCV ≥ 4.9 | Cropping, resizing, texture and colour analysis |
| Arrays | NumPy ≥ 1.24 | Embedding arithmetic, projections, distance computation |
| Image IO | Pillow ≥ 10.2 | Base64 → RGB array decoding in memory |
| Hashing | `hashlib` (stdlib) | SHA-256 template hashes; SimHash projections for LSH-based matching |

**A note on the hashing choice.** Plain SHA-256 over an embedding is privacy-perfect and matching-useless: the avalanche effect means two photos of the same person produce entirely unrelated digests, so no similarity survives. The architecture therefore permits a locality-sensitive scheme — SimHash over random hyperplanes, typically 64 bits for a 128-d embedding with a Hamming threshold near 10–15 — which keeps a well-defined relationship between Hamming distance and cosine similarity while remaining heavily underdetermined and thus non-invertible. The stored artefact is a fixed-length hex string either way.

### 3.4 Module 4 — Observability Dashboard

| Concern | Technology | Why |
|---------|-----------|-----|
| UI framework | Streamlit 1.30 | Data-app framework — an instructor portal with charts and tables in pure Python |
| Dataframes | Pandas 2.2 | Aggregation and CSV export shaping |
| Charts | Plotly 5.18 | Interactive time series, distributions, and attendance breakdowns |
| DB (read-only) | SQLAlchemy 2.0 + psycopg2 | Direct read-only queries for bulk export, bypassing API pagination |
| HTTP | requests 2.31 | Synchronous calls suit Streamlit's re-run execution model |
| Metrics | prometheus-client | PromQL queries against Prometheus for technical panels |

### 3.5 Infrastructure

| Component | Image | Host port | Role |
|-----------|-------|-----------|------|
| PostgreSQL | `postgres:15-alpine` | 5434 → 5432 | System of record, all 8 tables; healthcheck `pg_isready` |
| Redis | `redis:7-alpine` | 6380 → 6379 | Rate-limit counters with TTL; healthcheck `redis-cli ping` |
| Prometheus | `prom/prometheus:latest` | 9090 | Scrapes backend and face service `/metrics` every 15 s |
| Grafana | `grafana/grafana:latest` | 3001 → 3000 | Dashboards over Prometheus (admin/admin) |
| OTel Collector | `otel/opentelemetry-collector:latest` | 4317 gRPC, 4318 HTTP | Trace ingestion from backend and face service |
| Orchestration | Docker Compose | — | One bridge network `saiv-network`; named volumes for Postgres, Prometheus, Grafana |

> **Port note.** The host-side ports for PostgreSQL (5434) and Redis (6380) are deliberately shifted off their defaults to avoid colliding with locally installed instances. Inside the Compose network, services address each other by service name on the *container* port — `postgres:5432`, `redis:6379`, `face-recognition:8001`, `backend:8000`.

### 3.6 Test Tooling

| Tool | Role |
|------|------|
| pytest + custom scoring plugin | Runs the 90-point public suite; `@pytest.mark.points(N, category=...)` accumulates per-test scores and prints a total with a letter grade |
| httpx (test client) | Session-scoped HTTP clients against `TEST_BACKEND_URL` / `TEST_FACE_URL` |
| Pillow | Generates synthetic test images (solid colours, uniform "synthetic faces") for negative cases |
| `sample_images/` | Real face images (`obama.jpg`, `obama2.jpg`, `biden.jpg`, partial-face variants) driving same-person and different-person matching tests |

---

## 4. Module Communication

### 4.1 Communication Matrix

| Source | Destination | Protocol | Authentication | Timeout | Purpose |
|--------|-------------|----------|----------------|---------|---------|
| Frontend (M1) | Backend (M2) | HTTP/REST + JSON | JWT bearer | 30 s | All student operations |
| Dashboard (M4) | Backend (M2) | HTTP/REST + JSON | JWT bearer | 30 s | Instructor operations, stats, export |
| Backend (M2) | Face service (M3) | HTTP/REST + JSON | **None — internal trust** | 5 s | Enrollment, verification, liveness, risk fusion |
| Backend (M2) | PostgreSQL | TCP / SQLAlchemy | Connection string | 10 s | All persistence |
| Backend (M2) | Redis | TCP | Connection string | 2 s | Rate-limit counters |
| Dashboard (M4) | PostgreSQL | TCP / SQLAlchemy (read-only) | Connection string | 10 s | Bulk export dataframes |
| Dashboard (M4) | Prometheus | HTTP / PromQL | None | 5 s | Technical metric panels |
| Prometheus | M2, M3 `/metrics` | HTTP scrape | None | 15 s interval | Metric collection |
| M2, M3 | OTel Collector | OTLP (gRPC 4317 / HTTP 4318) | None | — | Distributed traces |

The face service has **no authentication of its own** — it is reachable only from inside the Compose network and trusts its caller. Its 5-second timeout is short by design: a slow ML service must degrade the check-in, not stall it past the 2-second budget.

### 4.2 Failure Semantics at the Backend → Face Boundary

The face service is a **degradable dependency**, not a hard one. When it times out or errors, the Backend does not fail the check-in; it proceeds with `liveness_passed: null` and `liveness_score: 0.0`, logs a warning, and lets the risk engine account for the missing signal. This keeps a transient ML outage from denying attendance to an entire lecture hall — while the absent liveness evidence still raises the check-in's risk.

For the direct face-enrollment endpoint (`POST /users/me/face/enroll`), where there is no partial result worth keeping, an unreachable face service surfaces honestly as **503**.

### 4.3 Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client (M1 / M4)
    participant B as Backend (M2)
    participant DB as PostgreSQL

    C->>B: POST /api/v1/auth/register {email, password, full_name, role}
    B->>B: validate (email RFC 5322, password ≥ 8)
    B->>B: bcrypt hash, cost ≥ 10
    B->>DB: INSERT users
    B->>DB: INSERT audit_logs (user_created)
    B-->>C: 201 {id, email, role, is_active, created_at}

    C->>B: POST /api/v1/auth/login {email, password}
    B->>B: Redis rate-limit check (60/hr per IP)
    B->>DB: SELECT user by email
    B->>B: bcrypt verify · assert is_active
    B->>DB: UPDATE last_login_at · INSERT audit_logs (login_success)
    B-->>C: 200 {access_token 1h, refresh_token 7d, token_type, user}

    loop authenticated requests
        C->>B: GET /api/v1/... + Authorization: Bearer <access>
        B->>B: verify HS256 signature · check exp · read role claim
        B->>B: RBAC gate for this endpoint
        B-->>C: 200 / 403
    end

    C->>B: POST /api/v1/auth/refresh {refresh_token}
    B-->>C: 200 {access_token, refresh_token}
```

The JWT payload carries `sub`, `email`, `role`, `exp`, `iat` — and nothing sensitive. Tokens are for authentication only; every authorization decision re-reads the role claim server-side on each request.

### 4.4 The Check-In Flow — the system's critical path

This is where all four modules and both data stores participate in one 2-second transaction.

```mermaid
sequenceDiagram
    participant S as Student
    participant M1 as Frontend PWA
    participant M2 as Backend API
    participant M3 as Face Service
    participant DB as PostgreSQL
    participant R as Redis

    S->>M1: open app, choose session
    M1->>M2: GET /api/v1/sessions/active  (public, no auth)
    M2-->>M1: 200 [active sessions]

    Note over M1: consent already recorded via PUT /users/me
    M1->>M1: getUserMedia() → capture frame → base64
    M1->>M1: getCurrentPosition() → lat, lng, accuracy
    M1->>M1: compute device fingerprint
    M1->>M1: track.stop() — release camera

    M1->>M2: POST /api/v1/checkins/ {session_id, lat, lng,<br/>accuracy, device_fingerprint, liveness_challenge_response}

    M2->>R: rate limit — 10 check-ins/min per user
    M2->>DB: session active? window open? enrolled? already checked in?
    M2->>DB: resolve/register device → trust score

    M2->>M3: POST /liveness/check {challenge_response, challenge_type}
    M3->>M3: MediaPipe Face Mesh — 468 landmarks, depth, texture, colour
    M3-->>M2: {liveness_passed, liveness_score, face_embedding_hash}

    opt session.require_face_match
        M2->>M3: POST /face/verify {image, reference_template_hash}
        M3-->>M2: {match_passed, match_score, current_template_hash}
    end

    M2->>M2: Haversine distance vs venue + geofence radius
    M2->>M3: POST /risk/assess {liveness, face_match, ip, user_agent, geolocation}
    M3-->>M2: {risk_score, risk_level, signal_breakdown, recommendations}

    M2->>M2: decide — approved / flagged / rejected
    M2->>DB: INSERT checkins (+ scheduled_deletion_at = +30d)
    M2->>DB: INSERT risk_signals (one row per signal)
    M2->>DB: INSERT audit_logs (checkin_attempted, then outcome)
    M2-->>M1: 201 {id, status, checked_in_at, risk_score, risk_factors, ...}
    M1-->>S: outcome screen — approved / flagged with reasons / appeal option
```

**Where the raw image goes.** The base64 frame travels browser → Backend → Face service, is decoded into a NumPy array in the face service's memory, is analyzed, and is discarded when the request returns. It is never written by any of the three. What persists is a 64-character hash.

### 4.5 Instructor Review Flow

```mermaid
sequenceDiagram
    participant I as Instructor
    participant M4 as Dashboard
    participant M2 as Backend API
    participant DB as PostgreSQL
    participant P as Prometheus

    I->>M4: login (instructor credentials)
    M4->>M2: POST /api/v1/auth/login
    M2-->>M4: 200 {access_token, ...}

    I->>M4: open session
    M4->>M2: PATCH /api/v1/sessions/{id} {status: "active"}
    M2->>DB: UPDATE sessions · INSERT audit_logs (session_updated)

    loop poll ~30s
        M4->>M2: GET /api/v1/checkins/session/{id}
        M4->>M2: GET /api/v1/stats/sessions/{id}
        M4->>P: PromQL — p95 latency, error rate
    end

    I->>M4: review flagged queue
    M4->>M2: GET /api/v1/checkins/flagged
    M2-->>M4: 200 {items: [flagged | appealed, with risk_factors]}
    I->>M4: approve with notes
    M4->>M2: POST /api/v1/checkins/{id}/review {status, review_notes}
    M2->>DB: UPDATE checkins · INSERT audit_logs (checkin_reviewed)

    I->>M4: export for gradebook
    M4->>M2: GET /api/v1/export/session/{id}?format=csv
    M2->>DB: INSERT audit_logs (data_exported)
    M2-->>M4: CSV download
```

The dashboard has a **second, narrower channel to the database**: read-only SQL for bulk export dataframes, where paging thousands of rows through the API would be wasteful. Every *mutation* still goes through the Backend API, so authorization and audit logging are never bypassed.

### 4.6 Observability Data Flow

```mermaid
flowchart LR
    m2["Backend :8000<br/>/metrics"] -->|scrape 15s| prom["Prometheus :9090"]
    m3["Face :8001<br/>/metrics"] -->|scrape 15s| prom
    m2 -.->|OTLP spans| otel["OTel Collector<br/>:4317 / :4318"]
    m3 -.->|OTLP spans| otel
    prom --> graf["Grafana :3001"]
    prom --> m4["Dashboard :8501<br/>PromQL panels"]

    classDef svc fill:#1f6feb22,stroke:#1f6feb
    classDef ob fill:#d2992222,stroke:#d29922
    class m2,m3,m4 svc
    class prom,graf,otel ob
```

Two metric families are collected. **Technical**: request duration histograms (feeding `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`), error rates, dependency health. **Business**: `checkin_attempts_total`, `checkin_success_total`, risk-score distribution, flagged-versus-approved ratio. A sharp rise in the flagged rate points at a systemic problem; a spike in failed logins points at an attack.

---

## 5. Internal Backend Architecture

The Backend is the largest module — roughly 50 endpoints — and layers cleanly:

```
┌─────────────────────────────────────────────────────────────┐
│  Middleware        CORS → rate limit (Redis) → JWT auth →   │
│                    request ID → metrics → tracing            │
├─────────────────────────────────────────────────────────────┤
│  Routers           auth · users · courses · sessions ·       │
│                    checkins · devices · enrollments ·        │
│                    stats · export · audit · admin            │
├─────────────────────────────────────────────────────────────┤
│  Schemas           Pydantic request/response models          │
│                    (the 422 validation surface)              │
├─────────────────────────────────────────────────────────────┤
│  Services          risk fusion · geofence (Haversine) ·      │
│                    face-service client (httpx) ·             │
│                    audit writer · retention job              │
├─────────────────────────────────────────────────────────────┤
│  Models            SQLAlchemy ORM — 8 tables                 │
├─────────────────────────────────────────────────────────────┤
│  Core              config · security (JWT, bcrypt) ·         │
│                    DB session · Redis client                 │
└─────────────────────────────────────────────────────────────┘
```

**Middleware ordering matters.** Rate limiting sits *before* authentication so that an unauthenticated flood of login attempts is throttled without paying bcrypt's ~100 ms cost per attempt — otherwise the rate limiter would itself be the DoS amplifier.

### 5.1 Risk Fusion

Risk scoring is split across two modules by design. The **face service** owns signal-to-risk conversion — it knows what a liveness score of 0.42 means — and returns a weighted `risk_score` with a `signal_breakdown`. The **backend** owns the *decision*: it resolves the effective threshold (session override → course setting → system default 0.5), applies the hard-rejection rules that no score can override (liveness failed; GPS beyond 2× the geofence), and persists each contributing signal as a `risk_signals` row so the instructor sees *why*, not just *how much*.

| Signal | Weight | Conversion |
|--------|-------:|-----------|
| Liveness | 25 % | risk = 1 − liveness_score |
| Face match | 25 % | risk = 1 − face_match_score |
| Device attestation | 20 % | signature validity, emulator/root flags |
| Network | 15 % | VPN / proxy / Tor heuristics |
| Geolocation | 15 % | accuracy, plausibility, impossible travel |

Levels: LOW < 0.3 ≤ MEDIUM < 0.5 ≤ HIGH < 0.7 ≤ CRITICAL.

---

## 6. Data Architecture

Eight tables, UUID (`VARCHAR(36)`) primary keys throughout.

```mermaid
erDiagram
    users ||--o{ enrollments : "enrolls in"
    users ||--o{ devices : "registers"
    users ||--o{ checkins : "submits"
    users ||--o{ audit_logs : "acts in"
    courses ||--o{ enrollments : "has"
    courses ||--o{ sessions : "schedules"
    sessions ||--o{ checkins : "receives"
    devices ||--o{ checkins : "used for"
    checkins ||--o{ risk_signals : "raises"

    users {
        varchar id PK
        varchar email UK
        varchar hashed_password
        enum role
        bool camera_consent
        bool geolocation_consent
        varchar face_embedding_hash "SHA-256 only"
        timestamp scheduled_deletion_at "30-day retention"
    }
    courses {
        varchar id PK
        varchar code UK
        float venue_latitude
        float venue_longitude
        float geofence_radius_meters
        float risk_threshold
    }
    enrollments {
        varchar id PK
        varchar student_id FK
        varchar course_id FK
        bool is_active
    }
    sessions {
        varchar id PK
        varchar course_id FK
        enum status "scheduled|active|closed|cancelled"
        timestamp checkin_opens_at
        timestamp checkin_closes_at
        bool require_liveness_check
        bool require_face_match
    }
    devices {
        varchar id PK
        varchar user_id FK
        varchar device_fingerprint UK
        text public_key
        bool attestation_passed
        varchar trust_score
    }
    checkins {
        varchar id PK
        varchar session_id FK
        varchar student_id FK
        enum status "pending|approved|flagged|rejected|appealed"
        float distance_from_venue_meters
        float liveness_score
        float face_match_score
        float risk_score
        timestamp scheduled_deletion_at
    }
    risk_signals {
        varchar id PK
        varchar checkin_id FK
        enum signal_type
        enum severity
        float confidence
        float weight
    }
    audit_logs {
        varchar id PK
        varchar user_id FK
        enum action
        varchar ip_address
        bool success
        timestamp timestamp "immutable - no updated_at"
    }
```

**Structural invariants that carry security weight**

| Invariant | Enforced by | Prevents |
|-----------|-------------|----------|
| One check-in per student per session | UNIQUE `(session_id, student_id)` | Concurrent double-submission racing past an application-level check |
| One enrollment per student per course | UNIQUE `(student_id, course_id)` | Duplicate roster entries skewing attendance rates |
| One device fingerprint system-wide | UNIQUE `devices.device_fingerprint` | The same physical device masquerading under several accounts |
| Audit immutability | No `updated_at` column; append-only writes | Tampering with the security record after the fact |
| No raw biometrics | No BLOB columns; hash-only fields | Permanent identity compromise in a breach |

**Storage tiers.** PostgreSQL is the system of record for everything above. Redis holds only ephemeral rate-limit counters keyed `rate_limit:{identifier}:{window}` with a TTL equal to the window — it is deliberately not a cache of business data, so a Redis flush costs throttling state and nothing else. Prometheus and Grafana keep their own time-series and dashboard volumes.

---

## 7. Deployment Architecture

A single `docker-compose up -d` brings up nine containers on the `saiv-network` bridge.

```
saiv-network (bridge)
│
├── saiv-postgres          postgres:15-alpine        5434→5432   healthcheck: pg_isready
├── saiv-redis             redis:7-alpine            6380→6379   healthcheck: redis-cli ping
│
├── saiv-backend           build ./module2-backend   8000        depends_on: postgres+redis healthy
├── saiv-face-recognition  build ./module3-...       8001        depends_on: redis healthy
├── saiv-frontend          build ./module1-frontend  3000        depends_on: backend
├── saiv-dashboard         build ./module4-...       8501        depends_on: backend, prometheus
│
├── saiv-prometheus        prom/prometheus           9090        mounts prometheus.yml
├── saiv-grafana           grafana/grafana           3001→3000   mounts provisioning/
└── saiv-otel-collector    otel/opentelemetry-...    4317, 4318  mounts otel-collector-config.yml

volumes: postgres_data, prometheus_data, grafana_data
```

Application containers wait on `service_healthy` conditions for their data dependencies, so the backend never starts against a database still initializing.

### 7.1 Service URLs

| Service | URL |
|---------|-----|
| Frontend PWA | http://localhost:3000 |
| Backend API (OpenAPI docs) | http://localhost:8000/docs |
| Face Recognition (OpenAPI docs) | http://localhost:8001/docs |
| Instructor Dashboard | http://localhost:8501 |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

### 7.2 Environment Configuration

**Backend (Module 2)**
```bash
DATABASE_URL=postgresql://saiv:saiv_password@postgres:5432/saiv
REDIS_URL=redis://redis:6379
SECRET_KEY=<32+ char random string>
FACE_SERVICE_URL=http://face-recognition:8001
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

**Frontend (Module 1)**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_FACE_SERVICE_URL=http://localhost:8001
```

**Face Recognition (Module 3)**
```bash
REDIS_URL=redis://redis:6379
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

**Dashboard (Module 4)**
```bash
DATABASE_URL=postgresql://saiv:saiv_password@postgres:5432/saiv
BACKEND_URL=http://backend:8000
PROMETHEUS_URL=http://prometheus:9090
```

**Optional tuning:** `ACCESS_TOKEN_EXPIRE_MINUTES` (60), `REFRESH_TOKEN_EXPIRE_DAYS` (7), `BCRYPT_ROUNDS` (10), `RISK_SCORE_THRESHOLD` (0.5), `CORS_ORIGINS`.

> Note the split: browser-facing variables use `localhost` because the *browser* resolves them; server-to-server variables use Docker service names because the *container* resolves them. Confusing the two is a classic first-run failure.

---

## 8. Folder Structure

```
SC3099-Capstone-Attendance-Application/
│
├── docker-compose.yml              # 9-service orchestration, saiv-network, volumes
├── README.md                       # Setup, test running, grading breakdown
├── requirements-test.txt           # pytest, httpx, Pillow — test-harness deps only
│
├── docs/                           # Authoritative specifications (read first)
│   ├── Briefing.md                 # Project vision, threat model, timeline
│   ├── API-SPECIFICATION.md        # ~50 endpoints, request/response schemas
│   ├── DATABASE-SCHEMA.md          # 8 tables, columns, indexes, constraints
│   ├── SECURITY-REQUIREMENTS.md    # Auth params, rate limits, thresholds, weights
│   ├── INTEGRATION-GUIDE.md        # Inter-module communication contracts
│   ├── module1.md                  # PWA, WebRTC, token storage, offline patterns
│   ├── module2.md                  # REST design, JWT, schema design, error handling
│   ├── module3.md                  # Face detection, embeddings, thresholds, SimHash
│   └── module4.md                  # Dashboard UX, dataviz, real-time, RBAC, export
│
├── new-documentations/             # Derived documentation (this folder)
│   ├── prd.md                      # Product Requirement Document
│   └── architecture.md             # This document
│
├── module1-frontend/               # ── MODULE 1: Student PWA (Next.js) ──
│   ├── Dockerfile
│   ├── package.json                # next, react, axios, jose, localforage, tailwind
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── app/                        # Next.js App Router
│       ├── layout.tsx
│       ├── page.tsx
│       ├── globals.css
│       │
│       │   ── to implement ──
│       ├── login/                  # Auth UI (register, login, refresh)
│       ├── checkin/                # Session select → camera → location → submit
│       ├── history/                # Own check-in history, appeals
│       ├── profile/                # Consent toggles, device management
│       ├── components/             # CameraCapture, LivenessChallenge, ConsentPrompt
│       ├── lib/                    # api client, token store, fingerprint, geolocation
│       └── public/                 # manifest.json, service-worker.js, icons
│
├── module2-backend/                # ── MODULE 2: Backend API (FastAPI) ──
│   ├── Dockerfile
│   ├── requirements.txt            # fastapi, sqlalchemy, alembic, jose, passlib, redis
│   └── app/
│       ├── main.py                 # App factory, CORS, /health  [skeleton provided]
│       │
│       │   ── to implement ──
│       ├── core/                   # config, security (JWT/bcrypt), db session, redis
│       ├── models/                 # SQLAlchemy: user, course, enrollment, session,
│       │                           #   checkin, device, risk_signal, audit_log
│       ├── schemas/                # Pydantic request/response models
│       ├── api/v1/                 # Routers:
│       │                           #   auth · users · courses · sessions · checkins
│       │                           #   devices · enrollments · stats · export
│       │                           #   audit · admin
│       ├── services/               # risk fusion, geofence (Haversine),
│       │                           #   face-service client, audit writer, retention
│       ├── middleware/             # rate limiting, request ID, metrics, tracing
│       └── alembic/                # Migration versions
│
├── module3-face-recognition/       # ── MODULE 3: Face & Risk (FastAPI+MediaPipe) ──
│   ├── Dockerfile
│   ├── requirements.txt            # mediapipe, opencv-python, numpy, pillow
│   └── app/
│       ├── main.py                 # App factory, /health, / endpoint list  [skeleton]
│       │
│       │   ── to implement ──
│       ├── routes/                 # /face/enroll · /face/verify · /face/match
│       │                           # /liveness/check · /risk/assess · /device/attest
│       ├── services/               # face detection, embedding, hashing (SHA-256 /
│       │                           #   SimHash), liveness scoring, risk fusion,
│       │                           #   VPN/proxy heuristics
│       └── utils/                  # base64 decode (in-memory only), image quality
│
├── module4-observability/          # ── MODULE 4: Dashboard & Monitoring ──
│   ├── Dockerfile
│   ├── requirements.txt            # streamlit, pandas, plotly, sqlalchemy, requests
│   ├── prometheus.yml              # Scrape config: backend:8000, face:8001, self
│   ├── otel-collector-config.yml   # OTLP receivers/exporters
│   ├── grafana/provisioning/
│   │   ├── datasources.yml         # Prometheus datasource
│   │   └── dashboards.yml          # Dashboard provisioning
│   └── app/
│       ├── main.py                 # Streamlit entrypoint  [skeleton provided]
│       │
│       │   ── to implement ──
│       ├── pages/                  # Sessions · Live attendance · Flagged review
│       │                           #   Analytics · Audit explorer · Export
│       ├── lib/                    # backend API client, PromQL client, read-only DB
│       └── components/             # charts, tables, metric tiles
│
├── sample_images/                  # Fixtures for face tests
│   ├── obama.jpg                   # Enrollment reference (clear frontal)
│   ├── obama2.jpg                  # Same person, different image → must match
│   ├── obama3.jpg
│   ├── biden.jpg                   # Different person → must NOT match
│   ├── obama_partial_face.jpg      # Occluded/partial face edge cases
│   └── obama_partial_face2.jpg
│
└── tests/                          # ── Black-box HTTP test suite (90 pts) ──
    ├── conftest.py                 # HTTP fixtures: users, auth headers, courses,
    │                               #   sessions, enrollments, devices, face images
    ├── _http_fixtures.py           # Lower-level API-driven fixture factories
    ├── _test_helpers.py            # Assertion helpers with actionable messages
    ├── public/
    │   ├── test_api_functional.py      # 26 pts — auth, users, courses, sessions,
    │   │                               #          check-ins, devices
    │   ├── test_face_recognition.py    # 15 pts — health, enroll, match, privacy, risk
    │   ├── test_security_basic.py      # 12 pts — auth security, RBAC, validation,
    │   │                               #          rate limiting
    │   ├── test_observability.py       # 12 pts — stats, session CRUD, enrollments,
    │   │                               #          check-in filters, export
    │   ├── test_privacy_basic.py       #  8 pts — consent, minimization, retention
    │   ├── test_frontend_dashboard.py  #  8 pts — API contract compliance
    │   ├── test_performance.py         #  5 pts — latency, concurrency, N+1
    │   └── test_integration.py         #  4 pts — end-to-end check-in flow
    └── scoring/
        ├── __init__.py
        └── plugin.py               # @pytest.mark.points accumulator, score summary
```

### 8.1 Structural Conventions

**One directory per module, one container per directory.** Each module directory holds its own `Dockerfile` and dependency manifest, and Compose builds each from its own context. A module can be rewritten in another language by replacing the directory's contents and Dockerfile — nothing outside it needs to change, because the contract is HTTP.

**Documentation is separate from implementation.** `docs/` holds the given specifications; `new-documentations/` holds derived documents. Neither is imported by code.

**Tests live outside the modules.** The suite runs against *running services* over HTTP, not against imported modules, so it sits at the repository root and reaches services through `TEST_BACKEND_URL` and `TEST_FACE_URL`.

**Skeletons mark the seams.** Each module ships a `main.py` (or `app/`) with a working `/health` endpoint and TODO comments enumerating the endpoints to implement — enough scaffolding to start the container, not enough to pass a test.

---

## 9. Cross-Cutting Concerns

### 9.1 Security Architecture

Defenses are layered so that no single bypass is sufficient:

| Layer | Control |
|-------|---------|
| Transport | HTTP only in this project; CORS restricted to `localhost:3000` and `localhost:8501` with exact-origin matching |
| Rate limiting | Redis TTL counters ahead of authentication — login 60/hr/IP, registration 10/hr/IP, API 1000/hr/user, check-in 10/min/user |
| Authentication | HS256 JWT, 1 h access / 7 d refresh, signature verified on every request, secret from environment |
| Authorization | RBAC evaluated server-side per endpoint from the token's role claim |
| Input validation | Pydantic schemas: RFC 5322 emails, UUID format, coordinate ranges, ISO 8601 timestamps, strict enums |
| Injection | ORM-only data access — parameterization by construction, never string-built SQL |
| Output | HTML escaping of user content; no user data in inline JavaScript; generic error bodies |
| Anti-fraud | Liveness, face match, geofence, device binding, network heuristics, impossible travel |
| Accountability | Immutable audit log across 18 action types |

### 9.2 Privacy Architecture

Privacy is enforced structurally rather than by policy:

1. **Consent gates capture.** `camera_consent` and `geolocation_consent` default to false and must be true before the corresponding sensor is used. Withdrawal takes effect immediately.
2. **Biometrics never land.** Images live in browser memory and face-service memory, and nowhere else. Only hashes persist. No BLOB columns exist in `users` or `checkins`.
3. **Embeddings alone are not enough.** Raw embeddings are reversible into recognizable faces by tools such as Arc2Face and IdDecoder, so the stored form must be non-invertible — SHA-256, or SimHash where matching must survive hashing.
4. **Location stays purpose-bound.** GPS is used for the geofence decision and stored with limited precision.
5. **Data expires.** `scheduled_deletion_at` drives 30-day deletion of check-ins and user PII via a scheduled cleanup job. Audit logs are exempt and permanent.
6. **Responses are minimal.** No response carries `password`, `hashed_password`, `face_image`, `image_data`, `photo`, `face_data`, `raw_image`, or a `data:image` URI.

### 9.3 Performance Architecture

| Technique | Applied where |
|-----------|--------------|
| Async IO | FastAPI + httpx keep the face-service round trip from blocking a worker |
| Connection pooling | SQLAlchemy pool size 10, max overflow 20 |
| Eager loading | Check-in list joins to users and devices — the N+1 pattern is the documented way to blow the 1 s budget |
| Indexing | Every foreign key and every filtered column (see §6) |
| Pagination | `limit`/`offset` on all list endpoints; uniform `{items, total, limit, offset}` envelope |
| Short timeouts | 5 s to the face service, 2 s to Redis — a slow dependency degrades rather than stalls |
| Graceful degradation | Face-service failure yields a null liveness result, not a failed check-in |

Budgets: login < 2 s, check-in < 2 s, list endpoints < 1 s, health < 0.5 s. Concurrency: ≥ 80 % success at 10 simultaneous logins, ≥ 90 % at 20 simultaneous check-ins, with a hidden stress target of 100 concurrent users.

---

## 10. Key Architectural Decisions

| Decision | Rationale | Trade-off accepted |
|----------|-----------|--------------------|
| All traffic through the Backend API | One trust boundary; the face service cannot mint attendance records even if reached directly | An extra network hop inside the 2 s check-in budget |
| Face service unauthenticated internally | Simplicity; it is unreachable from outside the Compose network | Depends on network isolation — would need mTLS or a shared secret in a real deployment |
| Face service degradable, not required | An ML outage must not deny attendance to a full lecture hall | A degraded check-in carries less evidence; the risk engine compensates |
| Hash-only biometric storage | A breach must not yield permanent identity compromise | Plain SHA-256 destroys matchability, forcing an LSH scheme such as SimHash |
| Risk *scoring* in M3, risk *decision* in M2 | Signal interpretation belongs with the ML; policy belongs with the authority | Two places to look when a score surprises you |
| Uniqueness enforced in the database | Concurrent submissions cannot both pass an application-level check | Duplicate handling surfaces as a constraint violation to translate into a 400 |
| Append-only audit table | Immutability is the point of an audit trail | No corrections — mistakes must be superseded, not edited |
| Dashboard reads the DB directly for export | Paging thousands of rows through the API is wasteful | A second data path to keep consistent; read-only, and all mutations still go through the API |
| Polling for dashboard freshness | ~30 s is ample for attendance; far simpler than WebSockets | Not sub-second — acceptable for the use case |
| Technology-agnostic HTTP contracts | Mirrors real engineering; frees each module's implementer | No shared type definitions across module boundaries |
