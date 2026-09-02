# Module 3 — Face Recognition & Risk Service: Implementation Plan

**Service:** `module3-face-recognition` · FastAPI · port `8001`
**Status:** skeleton only — every endpoint raises `501 Not Implemented`
**Points at stake:** 15 public (`tests/public/test_face_recognition.py`) + 13 hidden (10 "Face Recognition Advanced — anti-spoofing with real attack images", 3 "Liveness")

---

## 1. The core design problem

`POST /face/verify` receives **only** the new image and the **reference hash**. It never sees the enrolled embedding. A plain SHA-256 template is therefore useless for comparison — `docs/module3.md` states this outright (the avalanche effect means two photos of the same person hash to totally unrelated digests).

The service must also stay **stateless**: it has no database, and caching embeddings in Redis would (a) break on restart/flush and (b) store recoverable biometric material, which is precisely what the hidden Privacy Audit tests look for.

### Chosen scheme: 256-bit SimHash, emitted as 64 lowercase hex characters

```
image ──► dlib 128-d face embedding ──► L2 normalise ──► sign(H · v) ──► 256 bits ──► 64 hex chars
                                                         H = 256×128 fixed random hyperplanes
```

This single choice satisfies four constraints simultaneously:

| Constraint | How it is met |
|---|---|
| API spec: "64-char hex string" | 256 bits = exactly 64 hex chars |
| DB schema: `users.face_embedding_hash VARCHAR(64)` | fits exactly |
| Verify needs a continuous `match_score` from the hash alone | SimHash is locality-sensitive — Hamming distance estimates cosine similarity |
| Privacy: no raw images, no reversible embeddings stored | one-way lossy projection; keyed (see §1.3) |

**Documented deviation:** the value is a *SimHash*, not a literal SHA-256 digest. It is format-indistinguishable from one (64 lowercase hex chars), so every consumer — DB column, backend, tests — is unaffected. This deviation is mandatory: no non-LSH hash can implement `/face/verify` as specified.

### 1.1 The Hamming ↔ cosine relationship

For random hyperplanes through the origin, the probability that two vectors land on opposite sides is `θ/π`, where `θ = arccos(cos_sim)`. So with `f = hamming_distance / 256`:

```
cos_estimate = cos(π · f)
```

dlib's canonical decision boundary is Euclidean distance `0.6` on near-unit-norm descriptors, i.e. `cos ≈ 0.82`, i.e. **`f ≈ 0.195` (≈ 50 of 256 bits)**.

Expected separation:

| Case | typical cos | expected `f` | bits differing |
|---|---|---|---|
| Same image | 1.00 | 0.000 | 0 |
| Same person, different photo | ~0.94 | ~0.11 | ~28 |
| Different person | ~0.59 | ~0.30 | ~77 |

Sampling noise on `f` at n=256 is `√(p(1−p)/n) ≈ 0.025`. The intra/inter gap of ~0.19 is therefore **~7.6σ** — comfortable. At 64 bits (the variant taught in `docs/module3.md`) the noise doubles to ~0.049 and the margin drops to ~3.9σ, which is why 256 bits is the right width here as well as the right length.

### 1.2 Mapping Hamming distance to `match_score`

Raw cosine must **not** be used as `match_score` — different-person cosine lands around 0.6–0.75, uncomfortably close to the mandated 0.70 pass mark. Instead use a piecewise-linear calibration that puts the decision boundary *exactly* at 0.70:

```python
F_MATCH  = 0.195   # calibrated boundary (see Phase 1)
F_CHANCE = 0.50    # coin-flip: unrelated vectors differ in half the bits

if f <= F_MATCH:
    score = 0.70 + 0.30 * (F_MATCH - f) / F_MATCH
else:
    score = 0.70 * max(0.0, (F_CHANCE - f) / (F_CHANCE - F_MATCH))
match_passed = score >= 0.70
```

Monotone decreasing, bounded to `[0, 1]`, crosses 0.70 at `F_MATCH`. Same image → `f = 0` → score `1.0`. `F_MATCH` is env-tunable (`FACE_MATCH_HAMMING_FRACTION`) and set by the calibration spike.

### 1.3 Keyed hyperplanes = cancelable biometrics

Be honest about the limit: 256 sign-bit constraints on a 128-d unit vector confine its direction to a narrow cone, so the template is **not** strongly irreversible if the hyperplane matrix `H` is public. Mitigation, which also upgrades the design to the "cancelable biometrics" tier `docs/module3.md` flags as a good extension:

- `H = np.random.default_rng(SIMHASH_SEED).standard_normal((256, 128))`
- `SIMHASH_SEED` comes from the environment (a secret in deployment; a documented default for dev/test).
- Rotating the seed **revokes every enrolled template at once** — the revocability property a raw embedding can never offer.
- Use `default_rng` (PCG64), **not** legacy `RandomState` — PCG64's stream is guaranteed stable across NumPy versions, so a rebuilt container reproduces identical templates.

**Hard invariant:** `/face/enroll`, `/face/verify`, and `/liveness/check` must all emit templates from the *same* pipeline. The public test fixture `enrolled_hash` falls back to `/liveness/check`'s `face_embedding_hash` when enrollment fails, then verifies against it — so a divergent liveness pipeline silently breaks the matching tests.

---

## 2. Defects in the skeleton and test-contract traps

These are exact-match failures that will cost points despite "correct-looking" code. Fix them first.

| # | Location | Problem | Fix |
|---|---|---|---|
| T1 | `GET /health` | Returns `{"status": "healthy"}` only; `test_health_check` asserts `"service" in data` | Add a `service` field (and `version`) |
| T2 | `GET /` | `test_root_endpoint_lists_endpoints` does `"/face/enroll" in endpoints` — **list membership needs an exact element**. The skeleton's `"POST /face/enroll - Enroll a face..."` strings fail | Include bare paths as elements, e.g. `["/face/enroll", "/face/verify", "/face/match", "/liveness/check", "/risk/assess", "/health"]` |
| T3 | `POST /face/match` | Spec's legacy contract uses `reference_hash` (request) and `face_embedding_hash` (response); skeleton reuses `FaceVerifyRequest` → a spec-shaped call 422s | Accept a model with **both** field names optional; return **both** response key names |
| T4 | `LivenessResponse` | Missing `challenge_type`, which the API spec's response includes | Add it |
| T5 | `POST /face/enroll` | `test_enroll_requires_consent` sends a synthetic (faceless) image with `camera_consent=false` | Validate consent **before** face detection so the 400 reports the consent reason |
| T6 | `requirements.txt` | `numpy>=1.24.3` is unpinned and can resolve to NumPy 2.x, which breaks `mediapipe 0.10.9` and dlib wheels | Pin `numpy>=1.24.3,<2` |
| T7 | Risk levels | `docs/module3.md` slide 6 says MEDIUM 0.3–0.6 / HIGH 0.6–0.8 / CRITICAL >0.8. `API-SPECIFICATION.md` and `SECURITY-REQUIREMENTS.md` both say **0.3 / 0.5 / 0.7** | Follow the API spec (CLAUDE.md rule 2). The slide is stale |
| T8 | Geolocation risk | Skeleton hint says accuracy `< 10m` "might be spoofed", but `test_high_scores_produce_low_risk` sends `accuracy: 10` and demands low risk | Treat the suspicion threshold as `< 5m`, not `< 10m` |

---

## 3. Target architecture

```
module3-face-recognition/
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI app, routes, wiring only
│   ├── config.py       # env-driven settings: thresholds, seed, size limits
│   ├── schemas.py      # pydantic request/response models
│   ├── imaging.py      # base64 decode, validation, downscale, secure cleanup
│   ├── detection.py    # dlib + MediaPipe wrappers, model singletons, thread pools
│   ├── embedding.py    # 128-d descriptor extraction
│   ├── template.py     # SimHash hyperplanes, hex encode, Hamming, score mapping
│   ├── quality.py      # sharpness / brightness / size / confidence metrics
│   ├── liveness.py     # depth, mesh completeness, texture, colour, blink, head_turn
│   ├── risk.py         # signal scoring, weighted fusion, recommendations
│   └── telemetry.py    # OpenTelemetry setup
├── scripts/
│   └── calibrate.py    # calibration spike over sample_images/
├── Dockerfile
└── requirements.txt

new-tests/               # per CLAUDE.md rule 3
└── test_face_module3.py
```

### 3.1 Concurrency and model lifecycle

Both stress tiers (10 concurrent public, 100 concurrent hidden) and the `< 2s` check-in latency budget hinge on this:

- **Endpoints must be `def`, not `async def`.** The work is CPU-bound; `async def` would block the event loop and serialise every request. Plain `def` handlers let FastAPI run them in its threadpool.
- **Load dlib models once at startup** via a lazy singleton — never per request.
- **MediaPipe solution objects are not thread-safe.** Use thread-local instances or a small guarded pool; do not share one `FaceMesh` across threads.
- **Downscale before detection.** `sample_images/*.jpg` are 180–600 KB; cap the longest side at ~1024 px before running the HOG detector. This is the single biggest latency lever.
- Use dlib's **HOG** detector (`model="hog"`), not CNN.

---

## 4. Implementation phases

### Phase 0 — Foundations & the two free points *(~1h)*

1. Create the module layout in §3; move the pydantic models into `schemas.py`.
2. Fix **T1** and **T2** — these are 2 public points for pure plumbing.
3. `config.py`: env-driven `FACE_MATCH_THRESHOLD=0.70`, `LIVENESS_THRESHOLD=0.60`, `RISK_THRESHOLD=0.50`, `SIMHASH_SEED`, `FACE_MATCH_HAMMING_FRACTION`, `MAX_IMAGE_BYTES`, `MAX_IMAGE_DIM`.
4. `imaging.decode_base64_image()`: strip any `data:image/...;base64,` prefix defensively, enforce a byte cap **before** decode, `PIL.Image.open` → `convert("RGB")` → `np.array`, downscale to `MAX_IMAGE_DIM`. Raise a typed `InvalidImageError` → HTTP 400. Never log the payload.

> **Checkpoint:** `pytest tests/public/test_face_recognition.py::TestFaceServiceHealth` → 2/2.

### Phase 1 — Embedding + template + the calibration spike *(~3h)*

1. `requirements.txt`: uncomment `face-recognition==1.3.0`, apply the NumPy pin (**T6**). `face_recognition_models` resolves from PyPI, and the Dockerfile already has `build-essential` + `cmake` on Python 3.11, so dlib compiles. **Expect a slow first build (5–10 min).**
2. `detection.py`: `detect_face()` returns `{detected, confidence, bbox}`. Use dlib's HOG detector for locating faces; run MediaPipe `FaceDetection(min_detection_confidence=0.5)` alongside it, since the API's `face_detection_confidence` field and the ≥0.7 enrollment criterion are defined in MediaPipe terms and dlib's HOG returns no calibrated score.
3. `embedding.py`: `face_recognition.face_encodings(rgb, known_face_locations=[box], num_jitters=1)` → 128-d vector. Raise `NoFaceError` on empty.
4. `template.py`: hyperplane matrix from `SIMHASH_SEED`; `simhash_hex(embedding)`, `hamming_hex(a, b)` (XOR bytes + `int.bit_count()`), `match_score(f)` per §1.2. Reject reference hashes that aren't 64 hex chars with a 400.
5. **`scripts/calibrate.py` — do not skip this.** Compute pairwise `f` across `sample_images/`:
   - intra-person: obama × {obama2, obama3, obama_partial_face, obama_partial_face2}
   - inter-person: obama × biden, obama2 × biden, …

   Print the max intra and min inter fractions, then set `F_MATCH` midway. **Gate:** if intra-max ≥ inter-min, the embedding pipeline is broken — stop and fix before continuing.

> **Checkpoint:** obama→obama2 scores ≥ 0.70 and obama→biden scores < 0.70, with real margin on both sides.

### Phase 2 — `/face/enroll` *(~2h, 4 public points)*

Order of operations matters:

1. `camera_consent is not True` → **400** (**T5**).
2. Decode image; failure → 400.
3. Detect face; none, or confidence < 0.7 → **400 "No face detected"**.
4. Extract embedding → SimHash → 64 hex chars.
5. Quality score — weighted, all components normalised to `[0, 1]`:

   | Component | Weight | Measure |
   |---|---|---|
   | Detection confidence | 0.35 | MediaPipe score |
   | Face size ratio | 0.25 | bbox area ÷ image area, saturating around 0.10–0.35 |
   | Sharpness | 0.20 | variance of Laplacian on the face crop, normalised |
   | Resolution | 0.10 | min(w,h) against a 256 px reference |
   | Brightness/contrast | 0.10 | mean and std of luma vs. an ideal band |

   `sample_images/obama.jpg` must clear the `>= 0.5` assertion — verify empirically, then tune weights, not the threshold.
6. Quality < 0.5 → 400. Otherwise **201** with `details: {face_detected, face_detection_confidence, image_quality: "good"|"fair"|"poor"}`.
7. `del` intermediates and drop references to image arrays before returning.

> **Checkpoint:** `TestFaceEnrollment` → 4/4.

### Phase 3 — `/face/verify` and `/face/match` *(~1.5h, 4 public points)*

1. Validate `reference_template_hash` is 64 hex.
2. No face detected → **200** with `face_detected: false`, `match_passed: false`, `match_score: 0.0`, `current_template_hash: ""`. (The test accepts 400 too, but 200 is the friendlier contract for the backend.)
3. Otherwise embed → SimHash → Hamming → `match_score` per §1.2 → `match_passed`.
4. Always return `match_threshold: 0.70` and `current_template_hash`.
5. Implement `/face/match` per **T3**: accept `reference_hash` *or* `reference_template_hash`; return `match_passed`, `match_score`, **and both** `face_embedding_hash` and `current_template_hash`.

> **Checkpoint:** `TestFaceMatching` → 4/4, `TestPrivacyCompliance` → 2/2.

### Phase 4 — `/risk/assess` *(~2h, 3 public points)*

Weights are fixed by `SECURITY-REQUIREMENTS.md` and the API spec: liveness 0.25, face match 0.25, device 0.20, network 0.15, geolocation 0.15.

**Missing signals score 0.5 (neutral), not 1.0.** Absence of device attestation is mildly suspicious, not maximally so — and 1.0 would push benign requests toward the fail line.

Per-signal risk (0 = safe, 1 = risky):

- **Liveness / face match:** `1 - score`, clamped.
- **Device:** missing → 0.5; signature present but malformed → 0.8; well-formed signature + PEM public key → 0.1.
- **Network:** private ranges (`10/8`, `172.16/12`, `192.168/16`), loopback (`127/8`, `::1`), link-local → 0.85; VPN/proxy/tor keywords in `user_agent` → 0.9; headless/bot UA → 0.7; ordinary public IP + browser UA → 0.1. Combine by max, not sum.
- **Geolocation:** missing → 0.5; lat/lng out of range → 1.0; `accuracy > 5000 m` → 0.8; `accuracy > 500 m` → 0.4; `accuracy < 5 m` → 0.35 (implausible precision — **T8**: `accuracy == 10` must stay benign); otherwise 0.1.

Verify the arithmetic against all three tests before writing code:

| Test | liveness | face | device | network | geo | **total** | required |
|---|---|---|---|---|---|---|---|
| `response_format` (0.8 / 0.9, 192.168.1.1) | .05 | .025 | .10 | .128 | .075 | **0.378** MEDIUM | format only ✓ |
| `high_scores_produce_low_risk` (0.95 / 0.95, 8.8.8.8, acc 10) | .0125 | .0125 | .10 | .015 | .015 | **0.155** LOW | `< 0.5`, pass ✓ |
| `low_scores_produce_high_risk` (0.2 / 0.3, 10.0.0.1, "vpn-client") | .20 | .175 | .10 | .135 | .075 | **0.685** HIGH | `>= 0.5`, fail ✓ |

Both margins exceed 0.3 — robust to weight tweaks.

Levels per **T7**: LOW `< 0.3`, MEDIUM `< 0.5`, HIGH `< 0.7`, CRITICAL `>= 0.7`. `pass_threshold = risk_score < 0.50`. `signal_breakdown` returns *weighted contributions* (they sum to `risk_score`) — matching the spec's example, where the five values total 0.25. Emit a recommendation for any signal whose raw risk exceeds ~0.4, using the spec's exact strings.

> **Checkpoint:** `TestRiskAssessment` → 3/3. **All 15 public points now green.**

### Phase 5 — Liveness & anti-spoofing *(~4h, 13 hidden points)*

The spec's weighting is depth 30% / mesh completeness 25% / texture 25% / colour 20%. Implement it as specified — but understand where the real discriminative power is:

> **Reality check on `nose_tip_z`.** MediaPipe FaceMesh infers z from a canonical 3D model, so it returns plausible depth even for a *flat photo of a face*. The spec's "real faces have z < −0.05" rule will not, by itself, separate a genuine capture from a printed photo. Implement it for spec compliance and score contribution, but do not rely on it.

The signals that actually catch print/screen attacks are texture and colour:

- **Texture (25%):** variance of Laplacian (print/screen re-captures are softer); FFT radial energy profile to catch **moiré** banding from screen displays; local binary pattern uniformity for halftone print structure.
- **Colour (20%):** per-channel histogram spread and skin-tone chroma variance. Screens compress gamut; prints shift it. A uniform synthetic image collapses to near-zero variance — this is what drives the spec's "synthetic/uniform faces should score < 0.5" target.
- **Mesh completeness (25%):** all 468 landmarks present, landmark spread plausible, no degenerate geometry.
- **Depth (30%):** `|nose_tip_z|` bands (>0.03 good, >0.01 moderate, else poor), plus landmark z-variance across the mesh as a secondary cue.

Challenge types:

- `passive` (default): the four signals above.
- `blink`: Eye Aspect Ratio from FaceMesh eye landmarks; low EAR = closed eye. Single-image EAR is a weak proxy — return it as a component and document the limitation.
- `head_turn`: yaw estimated from left/right facial-landmark asymmetry.

Response must carry `challenge_type` (**T4**), the spec's full `details` object, and a `face_embedding_hash` **from the same SimHash pipeline as enrollment** (§1.3 invariant).

Calibration targets:

- `sample_images/obama.jpg` and friends → **≥ 0.60** (they are ordinary photos of real people; failing them breaks the enrollment fallback fixture).
- Uniform skin-tone synthetic (no face detected) → **0.0**.
- Any face-bearing but texture-degenerate input → **< 0.5**.

### Phase 6 — Observability & hardening *(~1.5h)*

- `telemetry.py`: OTel SDK + `FastAPIInstrumentor`, OTLP exporter to `OTEL_EXPORTER_OTLP_ENDPOINT` (already set to `http://otel-collector:4317` in `docker-compose.yml`). Degrade gracefully when the collector is absent.
- Span attributes: `face.detected`, `face.confidence`, `match.score`, `liveness.score`, `risk.level`, latency. **Never** an image, embedding, or template.
- Structured JSON logging with a scrubber that drops any field over ~256 chars or matching base64 shape — belt-and-braces against a stray `logger.info(request)`.
- Request size cap (`MAX_IMAGE_BYTES`, default 8 MB) rejected **before** decode — a decompression-bomb guard.
- Tighten CORS from `allow_origins=["*"]`: the face service is called service-to-service by the backend, so allow only the frontend origin (or nothing) via env.
- Optional `/device/attest` (specified but untested): verify the signature against the PEM key, return `attestation_score` and a `device_fingerprint`.

### Phase 7 — Module 2 backend wiring *(~2h)*

`module2-backend` is currently **auth-only** (`/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me`) with **no `/api/v1` prefix**, while the tests call `/api/v1/...`. That prefix gap is module 2's own defect; note it, but do not fix it here.

What module 2 must add for face:

1. **`POST /api/v1/users/me/face/enroll`** (auth required)
   - 400 if `current_user.camera_consent` is false — check before calling out.
   - `httpx.AsyncClient(timeout=5.0)` → `POST {FACE_SERVICE_URL}/face/enroll` with `{user_id, image, camera_consent: true}`.
   - On success: persist `users.face_embedding_hash = face_template_hash`, `users.face_enrolled = True`; write a `face_enrolled` audit-log row.
   - Map errors: face-service 400 → 400; timeout/connect error → **503** (the spec names 503 explicitly).
   - Return `{success, message, face_enrolled, quality_score}` — **never** echo the image or the hash.

2. **Check-in flow** (`INTEGRATION-GUIDE.md`, "Integration in Check-in Endpoint")
   - If `liveness_challenge_response` present → `POST /liveness/check`.
   - If the session sets `require_face_match` and the user has a hash → `POST /face/verify` with the stored `face_embedding_hash`.
   - Feed both scores plus device/IP/UA/geolocation into `POST /risk/assess`.
   - Persist `liveness_passed`, `liveness_score`, `liveness_challenge_type`, `face_match_passed`, `face_match_score`, `face_embedding_hash`, `risk_score`, `risk_factors` on the check-in row; explode `signal_breakdown` into `risk_signals`.
   - `status = "approved" if risk_score < session.risk_threshold else "flagged"`.
   - **Fail open, never hang:** on face-service timeout, record `liveness_passed: None`, `liveness_score: 0.0` and continue — the 2 s check-in latency budget covers the *whole* request.

3. `FACE_SERVICE_URL` is already wired in `docker-compose.yml` (`http://face-recognition:8001`). Reuse one module-level `AsyncClient` rather than constructing one per request.

---

## 5. New tests (`./new-tests/`, per CLAUDE.md rule 3)

Public tests cover the happy paths; these cover what they miss and what the hidden suite probes:

1. **Same person, different photo** — obama vs obama2/obama3 must score ≥ 0.70. *The public suite never tests this; it only re-submits the identical image, which passes trivially.* Highest-value gap.
2. **Partial/occluded face** — `obama_partial_face.jpg` should degrade quality gracefully, not crash.
3. **Template determinism** — the same image enrolled twice yields byte-identical hashes; hash matches `^[0-9a-f]{64}$`.
4. **Cross-endpoint template consistency** — the hash from `/liveness/check` verifies successfully against the hash from `/face/enroll` for the same image.
5. **Seed rotation revokes templates** — changing `SIMHASH_SEED` makes an old reference hash stop matching (proves the cancelable-biometric property).
6. **Score monotonicity** — `match_score` decreases monotonically as synthetic Hamming distance grows; the boundary sits exactly at 0.70 for `F_MATCH`.
7. **Risk fusion boundaries** — parametrised sweep asserting the LOW/MEDIUM/HIGH/CRITICAL cutoffs at 0.3 / 0.5 / 0.7, and that `signal_breakdown` values sum to `risk_score`.
8. **Malformed input** — non-base64, truncated base64, zero-byte, oversized, 1×1 pixel, non-image bytes, `data:` URI prefix → 400 with no stack-trace leak.
9. **Privacy** — no response field over 128 chars other than the template; no temp files created during a request (snapshot the working dir and temp dir around a call).
10. **Concurrency** — 20 parallel `/face/verify` calls all return correctly within the latency budget (guards the thread-safety of the MediaPipe singletons).

---

## 6. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| dlib build fails or is very slow in Docker | Blocks everything | Build early in Phase 1; `build-essential` + `cmake` already present on Python 3.11. Fall back to a FaceMesh-geometry embedding behind the same `embedding.py` interface — the SimHash layer above is unchanged |
| Local dev is Python **3.12**; `face-recognition` is flagged incompatible | Can't run the service outside Docker | **Develop and test against the container** (`docker compose up -d face-recognition`); tests are black-box HTTP, so this costs nothing |
| NumPy 2.x resolved into the image | MediaPipe/dlib import errors | Pin `<2` (**T6**) |
| `F_MATCH` mis-calibrated | Both matching tests fail | The calibration spike is a hard gate at the end of Phase 1 |
| `nose_tip_z` doesn't separate real from printed faces | Hidden anti-spoofing points lost | Weight texture/moiré and colour analysis as the real discriminators; keep depth for spec compliance |
| CPU-bound work on the event loop | Latency and stress tests fail | Sync `def` handlers, startup-loaded models, pre-detection downscale |
| Liveness pipeline diverges from enrollment | Public matching fixture breaks via its fallback path | Single shared `template.py`; covered by new-test #4 |

---

## 7. Execution order

```
Phase 0  Foundations, T1/T2 fixes          →   2 public pts
Phase 1  Embedding + SimHash + calibration →   (gate)
Phase 2  /face/enroll                      →   4 public pts
Phase 3  /face/verify + /face/match        →   4 + 2 public pts
Phase 4  /risk/assess                      →   3 public pts   ── 15/15 public
Phase 5  Liveness + anti-spoofing          →  13 hidden pts
Phase 6  Observability + hardening
Phase 7  Module 2 wiring                   →  unlocks integration & privacy suites
```

Run after every phase:

```bash
docker compose up -d --build face-recognition
```

```bash
TEST_FACE_URL=http://localhost:8001 python -m pytest tests/public/test_face_recognition.py -v
```

---

## 8. Decisions on record

| Decision | Choice | Rationale |
|---|---|---|
| Template scheme | 256-bit SimHash → 64 hex chars | The only stateless scheme satisfying the verify contract, the API's hex format, and `VARCHAR(64)` at once |
| Embedding backend | dlib / `face-recognition`, 128-d | Robust same-person-different-photo matching; the public suite's identical-image test hides this weakness, the hidden tests will not |
| Hyperplane seed | Env secret, `default_rng` (PCG64) | Makes templates keyed and revocable; PCG64 guarantees cross-version reproducibility |
| Missing risk signal | 0.5 neutral | Absence is mildly suspicious, not maximally so; keeps both risk tests well clear of the boundary |
| Risk level cutoffs | 0.3 / 0.5 / 0.7 | API spec + `SECURITY-REQUIREMENTS.md`; `docs/module3.md` slide 6 is stale |
| Liveness weighting | Spec's 30/25/25/20, texture-led in practice | Spec compliance without depending on a depth cue that cannot separate flat photos |
