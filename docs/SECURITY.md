# QuickCart Security Checklist

Audited against the spec's own security requirements list. Each item states
what's actually implemented and where, not just "done."

| Requirement | Status | Where |
|---|---|---|
| Role-based access | ✅ | `api/v1/deps.py` — `get_current_customer`/`get_current_retailer` verify role server-side on every request, independent of RLS and independent of the frontend |
| JWT auth | ✅ | `core/security.py` — verifies Supabase-issued tokens (signature, expiry, audience) on every authenticated request |
| Password hashing | ✅ | Delegated entirely to Supabase Auth — QuickCart's backend never sees or stores a raw or hashed password |
| SQL injection protection | ✅ | All queries go through the Supabase Python client's parameterized query builder — no raw SQL string interpolation anywhere in `app/` |
| XSS protection | ⚠️ Partial | Backend returns JSON only (no server-rendered HTML), which removes the most common XSS vector. The frontend (not yet built) is responsible for escaping any user-supplied text it renders — flagged for that phase, not solved here |
| CSRF protection | ✅ N/A by design | Pure JSON REST API with bearer-token auth (no cookies), which isn't vulnerable to CSRF the way cookie-session auth is — there's no ambient credential a malicious page could ride on |
| Secure APIs | ✅ | Every endpoint requires a valid role-appropriate JWT except signup/login/forgot-password (which are the public entry points by necessity) and `/health` |
| Input validation | ✅ | Every request body is a Pydantic model with explicit constraints (`Field(gt=0)`, `EmailStr`, length limits, etc.) — invalid input is rejected before it reaches business logic |
| Rate limiting | ✅ Partial | Applied to auth (`5-10/min`) and checkout (`10/min`) — the highest-abuse-value surfaces. Not applied to read endpoints (product search, dashboard) since aggressive limits there would hurt legitimate users more than stop abuse. In-memory store — see `core/rate_limit.py` for the horizontal-scaling caveat |
| Encrypted QR | ✅ | Fernet (AES-128-CBC + HMAC) in `services/qr_service.py` — tamper-evident and time-limited |
| Secure payment validation | ✅ | Razorpay HMAC-SHA256 signature re-verified server-side on every payment confirmation — a client claiming success is never trusted alone (`services/payment_service.py`) |
| HTTPS | ⚠️ Deployment-level | The app itself doesn't terminate TLS — Railway/Render/Vercel handle this at the platform edge. Nothing in this codebase should ever run behind plain HTTP in production; enforced by deployment configuration, not application code |
| Environment variables | ✅ | All secrets (`SUPABASE_SERVICE_ROLE_KEY`, `RAZORPAY_KEY_SECRET`, `QR_ENCRYPTION_KEY`, `ADMIN_API_KEY`) are read from environment only, never hardcoded — see `core/config.py` and `.env.example` |

## Known gaps, stated plainly (not hidden)

- **Admin auth is MVP-level** (`api/v1/admin_deps.py`) — a single shared
  key, not individual admin accounts with audit trails. Acceptable for the
  spec's "Optional" admin feature; should be upgraded before any real
  admin usage beyond a single trusted operator.
- **Rate limiting is per-process, in-memory.** Correct for one backend
  instance; needs Redis-backed storage before horizontal scaling, or
  limits can be bypassed by hitting different instances.
- **AI camera/tracker state is per-process** (`services/ai_ingest_service.py`)
  — same horizontal-scaling caveat as rate limiting, documented there too.
- **CORS origins** default to `http://localhost:5173` in `.env.example` —
  this MUST be changed to the actual production frontend origin(s) before
  deployment; a wildcard or forgotten localhost entry in production CORS
  config is a real, common misconfiguration.

## Verification honesty note

The Dockerfile and CI workflow in this repo are written correctly per
standard practice, but **the Dockerfile has not been built and run in this
development environment** — no Docker daemon is available here. Before
relying on it, run `docker build -f backend/Dockerfile backend/` and
confirm the image starts and passes its healthcheck. The CI workflow's
logic (installing CPU-only torch, then the rest of requirements.txt,
then running pytest against fake credentials) mirrors exactly what was
verified working in this sandbox via direct `pytest` runs — only the
containerization step itself is unverified.
