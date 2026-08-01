# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project virtualenv lives at `./myenv` and is not always activated — always run Python through it:

```bash
./myenv/bin/python manage.py runserver          # or: ./run.sh [port] — frees the port first, binds 0.0.0.0:8000
./myenv/bin/python manage.py makemigrations <app_label>
./myenv/bin/python manage.py migrate
./myenv/bin/python manage.py test lipaidox.<module>              # Django tests
./myenv/bin/python -m unittest forgotpassword_auth.tests.test_service   # standalone (non-Django) tests
./myenv/bin/pip install -r requirements.txt
```

**App labels differ from module paths** — use the label with `makemigrations`/`test`:
- `lipaidox.auth` → app label `lipaidox_auth`
- `lipaidox.messaging` → app label `lipaidox_messaging`

Configuration comes from `.env` next to `manage.py` (python-decouple; see `.env.example`). Database is PostgreSQL by default (`DB_NAME`/`DB_USER`/... vars); set `USE_SQLITE=True` to use `db.sqlite3` instead.

## Architecture

Django 4.2 backend exposing a single **Strawberry GraphQL** endpoint at `/graphql/` (GraphiQL enabled). Two REST surfaces exist alongside it, both mounted in `lipaidox_backend/urls.py`: `api/` for creator_profile file uploads (`upload/profile-photo/`, `upload/content-media/`), and the lost_found REST API at the URL root (see below).

### GraphQL schema composition

`lipaidox_backend/schema.py` builds the root `Query` and `Mutation` classes by multiply inheriting from per-module query/mutation classes. **Every feature module follows the same package layout** under `lipaidox/<module>/`:

```
models/       # one file per model, re-exported in __init__.py
queries/      # @strawberry.type Query class with resolvers
mutations/    # @strawberry.type Mutation class
schema/       # strawberry types for the module
migrations/
```

To add a new module: create it with that layout, register it in `INSTALLED_APPS` (`lipaidox_backend/settings.py`), and mix its Query/Mutation classes into `lipaidox_backend/schema.py`.

There are two module families sharing the one schema: the creator-platform modules (content, subscriptions, payment, wallet, ppv, tips, kyc, monetization, admin_panel, messaging, ...) and the LMS modules (`lms_*`: identity, content, learning, certification, cohorts, employer, ...).

### Authentication

- Custom user model: `AUTH_USER_MODEL = "lipaidox_auth.User"` (in `lipaidox/auth/models/`).
- GraphQL auth uses **PyJWT directly** (`lipaidox/auth/jwt_auth.py`), not simplejwt: `JWTGraphQLView` in `lipaidox_backend/urls.py` calls `authenticate_request()` to set `request.user` from the Bearer token before resolvers run. Tokens carry `user_id`, `role`, and `tenant_id`.
- Roles are `fan` (default), `creator`, `admin`. Resolver-level guards live in `lipaidox/auth/permissions.py` (`@require_creator`, `@require_admin`, `RolePermissions`). See `ROLE_ACCESS_CONTROL.md` for which features belong to which role.
- Google/Firebase sign-in is handled in `lipaidox/auth/googleOuth/` (Firebase Admin verifies ID tokens; service-account JSON auto-discovered by `settings.py`).
- `forgotpassword_auth/` (project root) is a **framework-independent** password-reset/OTP package tested with plain `unittest` and fakes — keep it free of Django imports.

### Multi-tenancy

`multitenant.middleware.TenantMiddleware` resolves the tenant from the `X-Tenant-ID` header (or request host matched against `Tenant.domain`) and sets both `request.tenant` and a thread-local readable via `multitenant.middleware.get_current_tenant()`. The `Tenant` model itself lives in `lipaidox/models.py`; tenant-scoped models inherit `multitenant.models.TenantAwareModel` (nullable `tenant` FK).

### Lost & Found / Discover

`lipaidox/lost_found/` is the exception to the GraphQL-first rule: its AI features are exposed as a **REST API** (`lipaidox/lost_found/urls.py`, mounted at the URL root), alongside GraphQL community features (polls, Q&A). The AI work lives in `lipaidox/lost_found/services/` — visual search (YOLOv8 + CLIP + Faiss), AI-generation detection, deepfake detection, QR scanning, price comparison, Gemini vision, Google Places, Wikimedia — and each service degrades to fallbacks when models or API keys are unavailable (details in the module's own `README.md`). `discover_adapters.py` reshapes raw service output into the exact TypeScript result shapes the frontend `/discover` page expects; adapters return `None` on unusable results so views report a gap instead of forwarding empty/error data.

### Media

Uploads go to `media/`. In DEBUG, `lipaidox_backend/media_serve.ranged_media_serve` serves them with HTTP Range support (206 responses) so mobile video playback works — don't replace it with plain `static()` serving.

`lipaidox/media_processor/tasks.py` defines the Celery media pipeline task `process_media_pipeline_task`, enqueued by `ContentMutation` when main video media is created; it is currently a logging no-op placeholder — extend it for transcoding/poster frames/HLS rather than adding a second pipeline. Note **no Celery app is configured** (no `celery.py`, no `CELERY_*` settings): `_schedule_main_video_processing` in `lipaidox/content/mutations/content_mutation.py` tries `.delay()` and falls back to calling the task synchronously, so don't assume a worker is running.
