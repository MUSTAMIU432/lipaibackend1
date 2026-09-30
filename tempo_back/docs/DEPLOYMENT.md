# Lipaidox Backend — Deployment Guide

> Status: Draft — architecture phase. Documents the **current** production topology
> (Render-hosted, WSGI, gunicorn) and the deployment procedure.

## 1. Production Architecture

```
 Internet
   │  HTTPS
   ▼
 Render (gunicorn workers)              PostgreSQL (managed, DATABASE_URL)
   ├─ lipaidox_backend.wsgi:application   ├─ sslmode=require
   ├─ gunicorn  (workers from WEB_CONCURRENCY, default 2)
   ├─ whitenoise → /static/ (collectstatic at build)
   ├─ ranged_media_serve → /media/ (local MEDIA_ROOT, disk-backed)
   ├─ /graphql/  → Strawberry (JWT auth)
   ├─ /payments/ → gateway webhooks (NBC)
   ├─ /api/      → uploads → Cloudinary (off-box)
   └─ /          → lost_found REST

 Ephemeral disk, so user media lives OFF-BOX:
   • Cloudinary (recommended: CLOUDINARY_* set)  OR
   • Render Disk mounted at MEDIA_ROOT on the service
```

Observations about the current setup:
- **WSGI** (`wsgi.py`); ASGI is present but is not used for channels today (`asgi.py` is
  plain `get_asgi_application` and `channels` is not in `INSTALLED_APPS`).
- **No Docker** anywhere: Render deploys the repo's Python buildpack (requirements.txt is
  at the project root and is what a typical Render build reads).
- **No web server/CDN in front of Django for static**: WhiteNoise
  (`CompressedStaticFilesStorage`) serves `/static/` from the app process — no nginx/CDN
  needed for admin/GraphiQL assets.
- PostgreSQL and any future Redis are managed separately (Redis currently unused; Celery
  is not configured — see `docs/DEVELOPMENT.md` §6).

## 2. Environment Configuration

All runtime config comes from the service's environment (`.env` only for local dev).
Required/important variables for production:

| Variable | Notes |
|---|---|
| `DEBUG` | must be `False` |
| `SECRET_KEY` | **long random string**; never the Django default (see `docs/SECURITY.md` §10) |
| `JWT_SECRET_KEY` | set explicitly to a distinct strong secret |
| `ALLOWED_HOSTS` | frontend/API host list; Render host is auto-appended (`RENDER_EXTERNAL_HOSTNAME`) |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | frontend origins (scheme+host) |
| `DATABASE_URL` | managed Postgres; `sslmode=require` |
| `MEDIA_ROOT` | path to a mounted Render Disk in production |
| `CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET/FOLDER` | required for persistent uploads |
| `PAYMENT_GATEWAY_DEFAULT` | `nbc` (or `simulated` — see warnings below) |
| `NBC_API_KEY`, `NBC_API_BASE`, `NBC_CURRENCY`, `NBC_SETTLEMENT_CURRENCY`, `NBC_USD_TO_TZS`, `NBC_REDIRECT_URL` | NBC/Haminass Pay gateway |
| `EMAIL_*` / `RESEND_API_KEY` / `DEFAULT_FROM_EMAIL` | email delivery (Render blocks outbound SMTP ports — prefer Resend HTTP API) |
| `FRONTEND_ORIGIN`, `PASSWORD_RESET_FRONTEND_PATH`, `PASSWORD_RESET_*` | password-reset links/OTP |
| `GOOGLE_OAUTH_*`, `FIREBASE_*` | social sign-in |
| `GROK_API_KEY`, `MAP_API`, `GOOGLE_TRANSLATE_API_KEY` | AI/discover services |
| `GUNICORN_TIMEOUT` / `GUNICORN_GRACEFUL_TIMEOUT` / `GUNICORN_KEEPALIVE` / `WEB_CONCURRENCY` | gunicorn tuning (defaults 300/300/30/2 — uploads need the long timeout) |
| `MEDIA_ROOT` | Render Disk mount (e.g. `/var/data/media`) |

`ALLOWED_HOSTS` falls back to `["*"]` only when `DEBUG=True`; production must list hosts
explicitly (Render's hostname is appended automatically, plus `.onrender.com` wildcard).

## 3. Migrations & Startup

```bash
./myenv/bin/python manage.py migrate              # run at deploy, before serving
./myenv/bin/python manage.py collectstatic --noinput   # at build; required for /static/
./myenv/bin/python manage.py check                # surfaces W001/W002 gateway warnings
```

- Postgres migration runs inside the deploy step (schema changes are additive-safe for
  a single-service deploy).
- `seed_plans` (creator plans) and credits package seeding run idempotently.

## 4. Static & Media Handling

- **Static:** `STATIC_ROOT=staticfiles/`, `STORAGES["staticfiles"]=whitenoise.storage.CompressedStaticFilesStorage`
  (compressed, not manifest — avoids build failure on missing references).
- **Media (uploads):**
  1. **Cloudinary** — with `CLOUDINARY_*` set, `/api/upload/*` streams files off-box and
     stores the HTTPS URL (free plan: 10 MB/image, 100 MB/video). **Recommended on Render**
     because the container disk is wiped on every restart.
  2. **Render Disk** — set `MEDIA_ROOT` to a Disk mount path so uploads persist across
     deploys.
  3. Local-only fallback (ephemeral, lossy) — with neither configured, production logs a
     loud warning (`settings.py:330-340`) and uploads vanish on redeploy.
- Serving: `ranged_media_serve` is registered in production too (not just DEBUG) so
  `/media/` answers `206 Partial Content` for mobile `<video>`; it closes DB connections
  before long streams.

## 5. Health Checks

| Endpoint | Purpose |
|---|---|
| `GET /payments/health/` | Payment-gateway probe (verify with `manage.py check_payment_gateway`) |
| `GET /system/health/` | Lost & Found service health/statistics |
| `manage.py check` | Startup checks: `payment.W001` (simulation on prod), `payment.W002` (NBC configured without key) |

Heartbeat endpoints should be pointed at the app root (`/`) or `/graphql/` for liveness.

## 6. Deployment Process (Render)

1. Push to the deploy branch (`lipaibackend`).
2. Render build: install `requirements.txt`, run `collectstatic --noinput`, `migrate`.
3. Start command runs gunicorn on `$PORT` with `gunicorn.conf.py` options
   (e.g. `gunicorn lipaidox_backend.wsgi:application` — `bind` left to Render's `$PORT`).
4. Attach a Render Disk and set `MEDIA_ROOT` to its mount (or set Cloudinary creds).
5. Verify: `/payments/health/` healthy; upload a photo (Cloudinary/disk); confirm a
   `/media/` Range response returns 206; GraphiQL reachable only per `ALLOWED_HOSTS`.
6. Post-deploy: set `DEBUG=False`, confirm `SECRET_KEY`/`JWT_SECRET_KEY` are rotated and
   never the defaults.

## 7. Runbooks / Caveats

- **Uploads 404 after redeploy** → `MEDIA_ROOT` was inside the app dir; move to a Disk or
  Cloudinary (this is the #1 cause of “feed media won't play”).
- **Outbound email timing out** → Render blocks SMTP (25/587/465); set `RESEND_API_KEY`
  (Anymail Resend backend) instead of SMTP.
- **Payment 502s** → NBC key provisioned for another settlement currency; align
  `NBC_SETTLEMENT_CURRENCY`/`NBC_CURRENCY` with the provisioned market.
- **NBC card redirect 403** → the returning host must be pre-approved on the API key;
  leave `NBC_REDIRECT_URL` empty until approved.
- Do **not** enable `PASSWORD_RESET_INLINE_OTP` / `EMAIL_VERIFICATION_INLINE_OTP` on a
  public API.
- Redis/Celery: none operational — treat lost_found/media pipeline tasks as synchronous
  until a broker is provisioned.

## 8. Current Gaps (Deployment)

- No Docker images / IaC (Render config is dashboard-driven).
- No automated deploy verification (smoke tests) wired into CI.
- No HSTS/secure-cookie flags yet (`docs/SECURITY.md` §9).