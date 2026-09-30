# Lipaidox Backend — System Architecture

> Status: Draft — **architecture phase**. Models, resolvers, features and migrations
> referenced below describe the *current* codebase; do not implement new business logic
> until this documentation is approved.

## 1. Overview

Lipaidox is a single **Django 4.2** backend (`Python 3.12` virtualenv in `./myenv`) that
powers three product surfaces from one codebase:

1. **Creator monetization platform** — creators publish content (posts, galleries,
   audio, live streams, PPV) and monetize via subscriptions, tips, pay-per-view, credit
   gifts and a fan wallet funded through payment gateways.
2. **E-learning / LMS platform** (14 `lms_*` modules) — courses, lessons, enrollments,
   certification, cohorts, study rooms, career features, running on the same GraphQL schema.
3. **Lost & Found / Discover** — AI-powered item matching (visual search, AI/deepfake
   detection, QR scanning, price comparison) exposed over a **REST** API, plus community
   Q&A and polls on GraphQL.

The system resolves one tenant per request (`X-Tenant-ID` header or a `Tenant.domain`
host match) and serves all tenants from shared tables that carry a nullable `tenant` FK
(`TenantAwareModel`).

The project root is `tempo_back/` (it holds `manage.py`). All paths in this document are
relative to that root unless noted.

```
lipaibackend/
├── tempo_back/                  # Django project root (this documentation's root)
│   ├── manage.py
│   ├── lipaidox_backend/        # project package: settings, urls, root GraphQL schema
│   ├── lipaidox/                # all feature modules (platform + LMS + lost_found)
│   ├── multitenant/             # tenancy: middleware + TenantAwareModel
│   ├── media_processor/         # media pipeline (Celery task placeholder)
│   ├── forgotpassword_auth/     # framework-independent password-reset reference package
│   ├── myenv/                   # virtualenv (git-ignored)
│   ├── media/                   # local upload root (git-ignored)
│   └── docs/                    # this documentation set
```

## 2. High-Level Request Flow

```
 Browser / SPA / Tauri app
        │  GraphQL mutations/queries  +  REST calls
        ▼
   Django (WSGI, gunicorn) ── Middleware ──────────────────────────────┐
   lipaidox_backend/urls.py                                            │
   ├── /graphql/      → Strawberry GraphQLView (JWTGraphQLView,        │
   │                    csrf_exempt; Bearer token → request.user)      │
   ├── /api/          → creator_profile upload endpoints (REST)        │
   ├── /payments/     → gateway webhook/callback + health/status       │
   ├── /              → lost_found REST API (root mount)               │
   └── /media/        → ranged_media_serve (206 Partial Content)       │
                                                                       │
   Middleware order: Security → WhiteNoise → Sessions → CORS → Common →│
                     CSRF → Auth → Messages → XFrameOptions → Tenant   │
                                                                       ▼
   PostgreSQL  ── SQLite (USE_SQLITE=True, dev/tests)
```

All data access goes through Django ORM; there is no separate API gateway or cache layer
in the request path today (Redis/Celery libraries are installed but **no broker-backed
worker is configured**).

## 3. Architectural Principles

1. **GraphQL-first.** The primary API is a single Strawberry endpoint. REST exists only
   where the frontend needs file uploads, payment webhooks, or AI/media streaming
   (see §7, and ADR-001).
2. **One feature = one app package.** Every feature module follows the same layout
   (`models/`, `queries/`, `mutations/`, `schema/`, `migrations/`) and is registered in
   `INSTALLED_APPS`; its GraphQL `Query`/`Mutation` classes are mixed into the root schema
   (`lipaidox_backend/schema.py`) by multiple inheritance.
3. **Money moves through one choke point.** All wallet/ledger mutation happens in
   `lipaidox/wallet/services.py` (`settle`, `credit_fan_wallet`, `spend_fan_to_platform`,
   `credit_creator_from_credits`) and is atomic + row-locked. Feature modules never touch
   a provider or wallet directly (see ADR-004).
4. **Top-up-then-spend.** Fans fund a wallet first; every purchase (PPV, live entry,
   subscription, credits, tips) spends from the fan wallet and credits the creator wallet
   net of the platform fee.
5. **Tenancy is applied, not assumed.** `TenantMiddleware` resolves the tenant and
   `TenantAwareModel` spreads a nullable `tenant` FK; resolvers must scope queries to the
   request tenant. (Known weakness: some modules — `lost_found`, several LMS light tables —
   are **not** tenant-scoped; see `docs/DATABASE.md` §8.)
6. **Append-only ledgers.** Every financial/audit ledger (`WalletTransaction`,
   `FinancialAuditLog`, `AdminAction`, `FanCreditLedger`, `LiveBillingEvent`, `VoteChange`)
   is insert-only; balances are derived, never edited in place, and cross-checked by DB
   constraints (see `docs/DATABASE.md` §6).
7. **Graceful degradation in AI services.** Identity/vision/price services (YOLOv8+CLIP+Faiss,
   Gemini, Groq, Google Places, Wikimedia) return fallbacks or `None` when models or keys
   are unavailable; adapters never forward raw errors to the frontend.
8. **Framework-independent auxiliary packages.** `forgotpassword_auth/` is tested with
   plain `unittest` and fakes and must stay free of Django imports.

## 4. Application & Domain Boundaries

### 4.1 Creator-platform modules (`lipaidox/<module>`)

| Domain | App | Core responsibilities |
|---|---|---|
| Tenancy | `multitenant`, `lipaidox` | `Tenant` model, `TenantMiddleware`, `TenantAwareModel` |
| Identity & auth | `lipaidox.auth` (`lipaidox_auth`) | `User` model, JWT issue/verify, RBAC, OAuth (Firebase/GIS), email/phone OTP, password reset, refresh tokens, TOTP 2FA |
| Onboarding | `lipaidox.onboarding` | Creator onboarding status/step log |
| Creator profile | `lipaidox.creator_profile` | Profiles, follows, memberships, reviews, username history; REST upload views |
| Content | `lipaidox.content` | Content/media/comment/like/bookmark/view/review/report/license; product metadata |
| Classification | `lipaidox.content_classification` | Platform categories + content classification for targeting |
| Monetization | `lipaidox.monetization` | Monetization settings, price history |
| Payments | `lipaidox.payment` | `Charge`, gateways (`simulated`, `nbc`), webhook, health, `PaymentMethod` |
| Wallet | `lipaidox.wallet` | Fan/creator wallets, platform `Transaction` ledger, `WalletTransaction`, payouts, clearing jobs |
| Subscriptions | `lipaidox.subscriptions` | Paid subscriptions + `SubscriptionPayment` |
| Creator plans | `lipaidox.creator_plans` | Tiered creator plans (feature caps, fees, annual pricing) |
| PPV | `lipaidox.ppv` | Per-view purchase with timed expiry |
| Tips | `lipaidox.tips` | Tips (fixed 15% platform fee) |
| Credits & live billing | `lipaidox.credits` | Credit wallets/ledgers, live-stream per-second billing engine, credit packages, audit log |
| Live streaming | `lipaidox.live_streaming` | Lives, entries, chat, viewers, credit gifts |
| Messaging | `lipaidox.messaging` | DMs, attachments, reactions, auto-DM rules, broadcasts, translate |
| Notifications | `lipaidox.notifications` | Notifications, preferences, push tokens, queues, templates |
| AI intelligence | `lipaidox.ai_intelligence` | Watermarks, fingerprinting, scans, analytics, content scores |
| Recommendation | `lipaidox.recommendation` | Interactions, scores, feed recs, trending, suggested creators, promoted content (ads) |
| KYC | `lipaidox.kyc` | KYC status, documents, business verification |
| Admin | `lipaidox.admin_panel` | Admin accounts, actions (append-only), flags, announcements, system settings, refunds |
| Analytics | `lipaidox.analytics` | Installed; **no models** today |
| Feedback | `lipaidox.feedback` | `AppFeedback` + GraphQL `FeedbackQuery/Mutation` |
| Security | `lipaidox.security` | Security events, login history, device sessions, 2FA settings (not wired into root schema) |
| Media pipeline | `lipaidox/media_processor` | Celery task placeholder for transcode/poster/HLS (not in `INSTALLED_APPS`) |

### 4.2 LMS modules (`lipaidox/lms_*`)

| App | Domain |
|---|---|
| `lms_identity` | Student/instructor profiles, roles, work/education, reviews, preferences, privacy |
| `lms_content` | Courses, categories, sections, lessons, labs, learning paths, resources, tags |
| `lms_learning` | Enrollments, notes, lesson progress, Q&A, wishlists |
| `lms_community` | Accountability groups, check-ins, study rooms/channels/messages |
| `lms_certification` | Skill badges/endorsements, certifications, certificates (verification codes, blockchain hash) |
| `lms_skills` | Skill categories, student skills, assessments |
| `lms_performance` | Activity logs, streaks, quiz attempts, assignments |
| `lms_financial` | Plans, subscriptions, payments, invoices, payment methods (Stripe-oriented) |
| `lms_careers` | Job listings, applications, talent pool |
| `lms_messages` | Course-scoped conversations/messages |
| `lms_notifications` | LMS notifications |
| `lms_cohorts` | Cohorts |
| `lms_employer` | Employer profiles |
| `lms_onboarding` | Student onboarding progress |

### 4.3 Cross-domain boundaries

- `lipaidox_auth.User` is the identity anchor **everywhere** (charges, transactions, tips,
  subscriptions, conversations, notifications, lost_found, LMS, admin actions).
- `lipaidox_creator_profile.CreatorProfile` is the creator anchor for content, wallets,
  subscriptions, PPV, tips, lives, analytics. `lms_identity.InstructorProfile` FK-links back
  to it, bridging the creator and LMS worlds.
- `lipaidox_wallet.Transaction` is the pivot row that joins a *fan* (`fan → User`) and a
  *creator* (`creator → CreatorProfile`) for any money flow.
- Ledgers reference origin rows by **UUID column, not FK** (e.g. `ppv_purchase_id`),
  keeping append-only ledgers independent of their source rows.

## 5. Dependency Flow

```
Tenant ──────► User (tenant FK, AUTH_USER_MODEL) ──► CreatorProfile (O2O)
                  │                                      │
                  ▼                                      ▼
          RefreshToken / OTP / 2FA /           Content / LiveStream / ContentSeries
          DeviceSession / Security*
                  │                                      │
                  ▼                                      ▼
  FanWallet ◄── Charge (gateway)          CreatorWallet ─► WalletTransaction (append-only)
      │          (top-up)                     ▲                 │
      ▼                                      │                 ▼
  settle()  ─────────►(fee split)────────────┘          Transaction (platform ledger)
      │
      ▼
  PPVPurchase · SubscriptionPayment · Tip · LiveStreamEntry · CreditPurchase
      │
      ▼
  Credits engine (live billing) ──► FanCreditWallet / CreatorCreditWallet / Ledgers
```

- **Who may call what** is enforced at the resolver with `@require_creator`,
  `@require_admin`, `@require_any_role(...)`, `@require_creator_or_admin`
  (`lipaidox/auth/permissions.py`; per-feature matrix in `ROLE_ACCESS_CONTROL.md`).
- **Feature modules depend on `wallet.services` and `payment` gateways**, never on a
  provider directly ("gateway seam" — `lipaidox/payment/gateways/`).
- **Tenancy**: middleware in `multitenant/middleware.py:9-34`; models inherit
  `multitenant.models.TenantAwareModel` (`tenant` nullable FK, `related_name="%(class)s_instances"`).

## 6. GraphQL Composition

`lipaidox_backend/schema.py` builds the root `Query` and `Mutation` by multiply inheriting
the per-module classes. MRO order matters and is the documented resolution mechanism for
name collisions — e.g. `NotificationQuery` must stay ahead of `LmsNotificationQueries`
because both define `my_notifications` (`schema.py:100-153`), and the same applies to
`mark_notification_read` etc. on the mutation side.

To add a module: create the standard layout, register the app, mix its Query/Mutation
classes into `schema.py`.

## 7. REST Surfaces

GraphQL is the default, but four non-GraphQL surfaces exist (see `docs/API.md` for detail):

| Mount | Purpose | Notes |
|---|---|---|
| `/api/` | Creator-profile file uploads (`upload/profile-photo/`, `upload/content-media/`, …) | DRF views, CSRF-exempt, `csrf_exempt` |
| `/payments/` | `/payments/callback/<gateway>/` webhook, `/payments/status/<ref>/`, `/payments/health/` | Webhook is auth-free, idempotent, always 200 |
| `/` (root) | Lost & Found REST API (`/items/…`, `/analyze/`, `/search/similar/`, `/discover/…`, `/system/…`, community) | The one module that deliberately breaks GraphQL-first (ADR-006) |
| `/media/` | `ranged_media_serve` with HTTP **Range/206** so mobile `<video>` plays | Registered in DEBUG **and** production (`urls.py:31-42`) |

## 8. Asynchronous Processing

- **Celery is not operational.** `celery`, `django-celery-beat`, `django-celery-results`,
  `kombu`, `billiard` are pinned in `requirements.txt`, but there is **no `celery.py`, no
  `CELERY_*` settings, no broker config**. Two consumers exist:
  - `lipaidox/media_processor/tasks.py::process_media_pipeline_task` — placeholder no-op;
    enqueued by `ContentMutation` via `.delay()` with a synchronous fallback
    (`lipaidox/content/mutations/content_mutation.py::_schedule_main_video_processing`).
  - `lipaidox/lost_found/tasks.py` — `@shared_task` definitions (`process_ai_features_async`,
    `scrape_prices_async`, etc.) and periodic-task comments; require a broker to run.
- Redis is installed but unused in the request path; the price-comparison cache and Faiss
  index are conceptual (see §9).
- `requirements-minimal.txt` exists at the project root as a lean alternative.

## 9. Data & Intelligence Services

`lipaidox/lost_found/services/` provides swappable, fallback-capable integrations:

- **Vision/verify/price** — `vision_service.py` (Groq `Llama 4 Scout`, read via
  `GROK_API_KEY` in `.env`), `gemini_vision_service.py`, `places_service.py`
  (`GOOGLE_MAPS_API_KEY`), `wikimedia_service.py`.
- **Visual search / detection** — `visual_search_service.py` (YOLOv8 + CLIP + Faiss),
  `ai_detection_service.py`, `deepfake_service.py`, `qr_scanner_service.py`,
  `price_compare_service.py`, orchestrated by `ai_service_manager.py`.

`discover_adapters.py` reshapes raw service output into the exact TypeScript shapes the
frontend `/discover` page expects; adapters return `None` on unusable results.

Media uploads go to Cloudinary when `CLOUDINARY_*` credentials are present
(`settings.py:342-394`), else to `MEDIA_ROOT`.

## 10. Major Architectural Decisions (Index)

Full write-ups live in `docs/ADR/`:

| ADR | Decision |
|---|---|
| 001 | GraphQL-first API — single Strawberry schema with per-module Query/Mutation mixins |
| 002 | Per-module package layout convention (`models/`, `queries/`, `mutations/`, `schema/`) |
| 003 | Custom `User` model (`lipaidox_auth`, UUID PK, tenant FK, `role`) + PyJWT bearer auth |
| 004 | Wallet choke point — top-up-then-spend with atomic, row-locked money movement |
| 005 | Header/host-based multi-tenancy with `TenantAwareModel` |
| 006 | Lost & Found exposed as a REST API; graceful AI service fallbacks |
| 007 | Schema-isolated Postgres test runner (no `CREATE DATABASE` privilege needed) |
| 008 | Off-box media (Cloudinary) + Range-aware media serving on ephemeral hosts |
| 009 | Framework-independent password-reset package (`forgotpassword_auth`) |
| 010 | Argon2id-first password hashing with PBKDF2 fallback |

## 11. Related Documents

- `CLAUDE.md` — developer cheat-sheet (commands, testing, conventions). Keep in sync.
- `ROLE_ACCESS_CONTROL.md` — role/feature access control matrix.
- `lipaidox/lost_found/README.md` — lost & found / AI feature detail.
- `docs/DATABASE.md`, `docs/SECURITY.md`, `docs/API.md`, `docs/DEVELOPMENT.md`,
  `docs/DEPLOYMENT.md`.