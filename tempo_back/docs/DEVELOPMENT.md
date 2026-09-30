# Lipaidox Backend — Development Guide

> Status: Draft — architecture phase. The **current** local-development workflow and tooling.

## 1. Prerequisites

- Python 3.12 (`.python-version`), PostgreSQL 13+ (for Postgres-backed suites), SQLite
  works for DB-free local dev.
- The project virtualenv lives at `./myenv` and is **not always activated** — run Python
  through it explicitly:
  ```bash
  ./myenv/bin/python manage.py runserver
  ./myenv/bin/pip install -r requirements.txt
  ```

## 2. Environment Setup

```bash
cd tempo_back
./myenv/bin/pip install -r requirements.txt     # or install into myenv from scratch
cp .env.example .env                             # then fill values; NEVER commit .env
```

`.env` sits next to `manage.py` (python-decouple `AutoConfig(search_path=BASE_DIR)`).
Key switches:

| Variable | Effect |
|---|---|
| `USE_SQLITE=True` | Use `db.sqlite3` instead of Postgres |
| `DATABASE_URL` | Managed Postgres (Render/Herkou/Fly); parsed locally with `sslmode=require` |
| `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` | Discrete Postgres config (defaults `lipaidox2`/`lipaiduser`/…) |
| `DEBUG` | Dev mode: `ALLOWED_HOSTS=["*"]`, CORS all origins |
| `PAYMENT_GATEWAY_DEFAULT` | `simulated` (default, settles instantly) or `nbc` |
| `EMAIL_*` / `RESEND_API_KEY` | Email backend: Resend (HTTPS) → SMTP → console |
| `CLOUDINARY_*` | Off-box media storage (else local `MEDIA_ROOT`) |
| `FIREBASE_*`, `GOOGLE_OAUTH_*` | Social sign-in keys/redirect |

See `.env.example` (heavily commented) for the full checklist — including SMTP pitfalls
(TLS+SSL together, port 465 vs 587) and Firebase service-account handling.

## 3. Running the Server

```bash
./run.sh            # frees port 8000 first, binds 0.0.0.0:8000 (reachable from devices)
./run.sh 8001       # custom port
./myenv/bin/python manage.py runserver          # plain
```

- `run.sh` kills any stale process holding the port, then starts `manage.py runserver`
  on `0.0.0.0`.
- GraphiQL UI: <http://localhost:8000/graphql/>.
- Android emulator reaches the host via `10.0.2.2` (already in default `ALLOWED_HOSTS`);
  physical devices need your LAN IP in `ALLOWED_HOSTS`.

## 4. Docker

- **Not present.** There is no `Dockerfile`, `docker-compose.yml`, or container tooling in
  the repository today; deployment is host/Process-based (see `docs/DEPLOYMENT.md`).
- PostgreSQL/Redis/Celery: no compose services are provided. Local Postgres is expected to
  be installed/run by the developer.

## 5. Database

```bash
./myenv/bin/python manage.py makemigrations <app_label>   # label ≠ module path (see below)
./myenv/bin/python manage.py migrate
```

- App labels differ from module paths: `lipaidox.auth` → `lipaidox_auth`,
  `lipaidox.messaging` → `lipaidox_messaging`, `lipaidox.payment` → `lipaidox_payment`,
  `lipaidox.credits` → `lipaidox_credits`, etc.
- Seeding (creator plans): `./myenv/bin/python manage.py seed_plans` /
  `./myenv/bin/python seed_plans.py`; credits packages self-seed when none exist.
- Postgres-only column types (`live_billing.py`, some credits models) cannot be built with
  SQLite — see Testing.

## 6. Redis / Celery

- **Redis** is installed (`redis`, `django-redis`, `channels-redis`) but unused in the
  request path today.
- **Celery** libraries are pinned but **no Celery app is configured** — no `celery.py`,
  no `CELERY_*` settings. `ContentMutation` tries `.delay()` and falls back to running the
  media-pipeline task synchronously; lost_found `tasks.py` defines `@shared_task`s that need
  a broker. Introducing a worker is a future decision — do not assume one is running.

## 7. Testing

### Entry point
```bash
./test.sh                        # everything (DB-free first, then Postgres-backed)
./test.sh --keepdb               # reuse migrated schema — fast after first run
./test.sh quick                  # DB-free suites only (SQLite)
./test.sh db [labels…]            # Postgres-backed suites / given labels
```

Two suite families (`test.sh`):

- **DB-free** (`FAST=(lipaidox.creator_plans.tests lipaidox.payment.tests lipaidox.media_processor.tests)`)
  — mocks/fakes, run with `USE_SQLITE=True`.
- **Postgres-backed** (`DB=(lipaidox.credits.tests lipaidox.feedback.tests lipaidox.content.tests)`)
  — need the real schema (Postgres-only column types). Run with
  `--settings=lipaidox_backend.test_settings`. New DB-free suites → `FAST=(…)`;
  new Postgres schemes → `DB=(…)`.

### Schema-isolated runner
`lipaidox_backend/test_runner.py::SchemaIsolatedRunner` creates a **schema** inside the
existing DB, confines `search_path` to it (never touches `public`), migrates into it, and
drops it afterwards (`--keepdb` keeps `lipaidox_test`). Requires `CREATE` on the DB, **not**
`CREATEDB`.

```bash
TEST_DB_SCHEMA=my_schema ./test.sh db --keepdb   # custom schema name
# Drop a stale kept schema:
DROP SCHEMA lipaidox_test CASCADE;
```

Single-test targeting:
```bash
./myenv/bin/python manage.py test lipaidox.<module>[:TestCase.method]
./myenv/bin/python -m unittest forgotpassword_auth.tests.test_service   # standalone (no Django)
```

Time is injected (`now=`) in the billing engine so tests don't sleep.

## 8. Linting, Formatting & Type Checking

| Tool | Version (pinned) | Status |
|---|---|---|
| `black` | 23.11.0 | Available in `requirements.txt`; run `./myenv/bin/black lipaidox/` (no repo config found) |
| `flake8` | 6.1.0 | Available; run `./myenv/bin/flake8 lipaidox/` (no config found) |
| `isort` | 5.12.0 | Available |
| `mypy` | — | **Not configured** (only `mypy_extensions` is pinned); add when a type contract is adopted |
| `pytest` | 7.4.3 | Available (`pytest-django`); the project currently drives tests via `manage.py`/`test.sh` |

There is no CI lint gate wired up — recommended before the implementation phase.

## 9. Module Scaffolding Convention

Every feature module follows the same layout (see `docs/ARCHITECTURE.md` §6):

```
lipaidox/<module/​>
├── models/          # one file per model, re-exported in __init__.py
├── queries/         # @strawberry.type Query class (+ resolvers)
├── mutations/       # @strawberry.type Mutation class
├── schema/          # strawberry types for the module
├── migrations/
└── apps.py
```

Register in `INSTALLED_APPS`, mix Query/Mutation classes into
`lipaidox_backend/schema.py` (watch MRO when names collide).

## 10. Configuration Summary

- All config is env-driven via `.env` (uses `Search`: `lipaidox_backend/settings.py:64-66`).
- Startup checks: `payment.W001` (simulation mode on non-DEBUG) and `payment.W002`
  (`PAYMENT_GATEWAY_DEFAULT=nbc` without `NBC_API_KEY`) — surfaced by
  `manage.py check` / `runserver`.