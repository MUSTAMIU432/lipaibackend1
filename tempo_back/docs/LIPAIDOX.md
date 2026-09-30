# Lipaidox Backend — Architecture & Operations (Single Compilation)

> **Scope:** Creator-monetization platform only. E-learning (`lms_*` modules) and
> Lost & Found / Discover are **out of scope** for this document.
> **Status:** Draft — **architecture phase.** Models, resolvers and migrations referenced
> below describe the current codebase. No implementation work until approved.

See also: `CLAUDE.md` (developer cheat-sheet), `ROLE_ACCESS_CONTROL.md` (RBAC matrix).

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [REST vs GraphQL — Usage Mapping](#2-rest-vs-graphql--usage-mapping)
3. [API Architecture](#3-api-architecture)
4. [Database Architecture](#4-database-architecture)
5. [Security Architecture](#5-security-architecture)
6. [Development Guide](#6-development-guide)
7. [Deployment Guide](#7-deployment-guide)
8. [Architecture Decision Records](#8-architecture-decision-records)

---

## 1. System Architecture

### 1.1 Overview

Lipaidox is a single **Django 4.2** backend (`Python 3.12`, virtualenv `./myenv`) powering
one creator-monetization product: creators publish content (posts, galleries, audio, live
streams, PPV) and monetize via subscriptions, tips, pay-per-view, credit gifts and a fan
wallet funded through pluggable payment gateways. It serves all tenants from shared tables
carrying a nullable `tenant` FK (`TenantAwareModel`).

The project root is `tempo_back/` (holds `manage.py`). All paths below are relative to it.

```text
lipaibackend/
├── tempo_back/                  # Django project root
│   ├── manage.py
│   ├── lipaidox_backend/        # project package: settings, urls, root GraphQL schema
│   ├── lipaidox/                # all feature modules
│   ├── multitenant/             # tenancy: middleware + TenantAwareModel
│   ├── media_processor/         # media pipeline (Celery task placeholder)
│   ├── forgotpassword_auth/     # framework-independent password-reset reference package
│   ├── myenv/                   # virtualenv (git-ignored)
│   ├── media/                   # local upload root (git-ignored)
│   └── docs/                    # this documentation set
```

### 1.2 High-Level Request Flow

```text
 Browser / SPA / mobile app
        │  GraphQL  +  REST calls
        ▼
  Django (WSGI, gunicorn) ── Middleware ────────────────────────────┐
  lipaidox_backend/urls.py                                         │
  ├── /graphql/   → Strawberry JWTGraphQLView (csrf_exempt;        │
  │                 Bearer token → request.user before resolvers)  │
  ├── /api/       → creator_profile upload endpoints (REST)        │
  ├── /payments/  → gateway webhook/callback + health + status     │
  └── /media/     → ranged_media_serve (206 Partial Content)       │
                                                                    │
  Middleware: Security → WhiteNoise → Sessions → CORS → Common →   │
              CSRF → Auth → Messages → XFrameOptions → Tenant      │
                                                                    ▼
  PostgreSQL ── SQLite (USE_SQLITE=True, dev/tests)
```

All data access goes through the Django ORM. There is no API gateway or cache layer in the
request path today (Redis/Celery libraries are installed but **no broker-backed worker is
configured**).

### 1.3 Architectural Principles

1. **GraphQL-first.** The primary API is a single Strawberry endpoint. REST exists only
   where GraphQL is ill-suited: multipart file uploads, payment-provider webhooks,
   long-lived media streaming, and ops health probes.
2. **One feature = one app package.** Every module follows the same layout
   (`models/`, `queries/`, `mutations/`, `schema/`, `migrations/`), is registered in
   `INSTALLED_APPS`, and its `Query`/`Mutation` classes are mixed into the root schema
   (`lipaidox_backend/schema.py`) by multiple inheritance.
3. **Money moves through one choke point.** All wallet/ledger mutation happens in
   `lipaidox/wallet/services.py` (`settle`, `credit_fan_wallet`,
   `spend_fan_to_platform`, `credit_creator_from_credits`) and is atomic + row-locked.
4. **Top-up-then-spend.** Fans fund a wallet first; every purchase (PPV, live entry,
   subscription, credits, tips) spends from the fan wallet and credits the creator wallet
   net of the platform fee.
5. **Tenancy is applied, not assumed.** `TenantMiddleware` resolves the tenant from
   `X-Tenant-ID` (or a `Tenant.domain` host match) and `TenantAwareModel` spreads a
   nullable `tenant` FK; resolvers must scope to the request tenant.
6. **Append-only ledgers.** Every financial/audit ledger (`WalletTransaction`,
   `FinancialAuditLog`, `AdminAction`, `FanCreditLedger`, `LiveBillingEvent`) is
   insert-only; balances are derived and DB-checked.
7. **Framework-independent auxiliary packages.** `forgotpassword_auth/` is tested with
   plain `unittest` + fakes and must stay free of Django imports.

### 1.4 Module & Domain Boundaries

| Domain | App | Core responsibilities |
|---|---|---|
| Tenancy | `multitenant`, `lipaidox` | `Tenant` model, `TenantMiddleware`, `TenantAwareModel` |
| Identity & auth | `lipaidox.auth` (`lipaidox_auth`) | `User` model, JWT issue/verify, RBAC, Firebase/GIS OAuth, email/phone OTP, password reset, refresh tokens, TOTP 2FA |
| Onboarding | `lipaidox.onboarding` | Creator onboarding status/step log |
| Creator profile | `lipaidox.creator_profile` | Profiles, follows, memberships, reviews, username history; REST upload views |
| Content | `lipaidox.content` | Content/media/comment/like/bookmark/view/review/report/license |
| Classification | `lipaidox.content_classification` | Platform categories + content classification |
| Monetization | `lipaidox.monetization` | Monetization settings, price history |
| Payments | `lipaidox.payment` | `Charge`, gateways (`simulated`, `nbc`), webhook, health, `PaymentMethod` |
| Wallet | `lipaidox.wallet` | Fan/creator wallets, `Transaction` ledger, `WalletTransaction`, payouts, clearing jobs |
| Subscriptions | `lipaidox.subscriptions` | Paid subscriptions + `SubscriptionPayment` |
| Creator plans | `lipaidox.creator_plans` | Tiered creator plans (feature caps, fees, annual pricing) |
| PPV | `lipaidox.ppv` | Per-view purchase with timed expiry |
| Tips | `lipaidox.tips` | Tips (fixed 15% platform fee) |
| Credits & live billing | `lipaidox.credits` | Credit wallets/ledgers, live-stream per-second billing engine, credit packages, audit log |
| Live streaming | `lipaidox.live_streaming` | Lives, entries, chat, viewers, credit gifts |
| Messaging | `lipaidox.messaging` | DMs, attachments, reactions, auto-DM rules, broadcasts, translate |
| Notifications | `lipaidox.notifications` | Notifications, preferences, push tokens, queues, templates |
| AI intelligence | `lipaidox.ai_intelligence` | Watermarks, fingerprinting, scans, analytics, content scores |
| Recommendation | `lipaidox.recommendation` | Interactions, scores, feed recs, trending, suggested creators, promoted content |
| KYC | `lipaidox.kyc` | KYC status, documents, business verification |
| Admin | `lipaidox.admin_panel` | Admin accounts, actions (append-only), flags, announcements, system settings, refunds |
| Analytics | `lipaidox.analytics` | Installed; **no models** today |
| Feedback | `lipaidox.feedback` | `AppFeedback` + GraphQL `FeedbackQuery/Mutation` |
| Security | `lipaidox.security` | Security events, login history, device sessions, 2FA settings (not wired into root schema) |
| Media pipeline | `lipaidox/media_processor` | Celery task placeholder (not in `INSTALLED_APPS`) |

### 1.5 Dependency Flow

```text
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

- **Access control** is enforced at the resolver with `@require_creator`, `@require_admin`,
  `@require_any_role(...)`, `@require_creator_or_admin`
  (`lipaidox/auth/permissions.py`; matrix in `ROLE_ACCESS_CONTROL.md`).
- **Feature modules depend on `wallet.services` and `payment` gateways, never a provider
  directly** (gateway seam — `lipaidox/payment/gateways/`).

### 1.6 Async Processing

- **Celery is not operational** — no `celery.py`, no `CELERY_*` settings. `media_processor`
  defines a placeholder task (`process_media_pipeline_task`) that `ContentMutation`
  enqueues via `.delay()` with a synchronous fallback. Redis is installed but unused in the
  request path.

---

## 2. REST vs GraphQL — Usage Mapping

### 2.1 GraphQL — `/graphql/` (the default client API)

Everything a first-party client does goes through GraphQL (`strawberry.Schema`):

| Area | Operations |
|---|---|
| Auth & identity | `loginUser`, `registerUser`, `googleAuth`, `refreshAccessToken`, `logoutUser`, `requestPasswordReset` / verify / reset (OTP + magic link), email & phone verification, 2FA setup/verify/disable, TOTP/backup codes |
| Profiles & onboarding | `myProfile`, profile updates, follow/unfollow, memberships, reviews, username check/change, onboarding steps, content classification |
| Content | publish/update content+media, comments, likes, bookmarks, views (`recordContentView`), reviews, reports, licenses, series, tag |
| Monetization | monetization settings, price history |
| Payments | `topUpWallet` (creates a `Charge`), payment methods (bank/mobile-money), mobile money providers |
| Wallet | `myFanWallet`, fan transactions, creator payout **request**, admin payout approve/cancel/complete/reverse, wallet bonus, clearing jobs |
| Credits & live billing | credit packages + `purchaseCreditPack` (wallet/gateway), gifts, `liveBillingHeartbeat`, billing status, admin adjust/terminate, credit reports |
| Subscriptions / PPV / Tips / Plans | subscribe (wallet/gateway), cancel, PPV purchase, tips, creator plan choose/limits |
| Live streaming | live CRUD, entries, chat messages, viewers |
| Messaging | conversations, DMs, reactions, auto-DM rules, quick replies, scheduled messages, broadcasts |
| Notifications | list/mark read, preferences, push tokens |
| AI & recommendation | content scores, feed recommendations, suggested creators, interactions |
| Feedback | app feedback submit/list |
| Admin | user management (create/update/delete), KYC admin, announcements, platform posts, system settings |
| Tenancy | tenant-scoped queries |

### 2.2 REST — non-GraphQL surfaces (where and why)

REST is used where GraphQL is a poor fit — raw multipart bodies, provider-initiated
callbacks, long-running streams, and ops probes:

| Mount | Endpoints | Why REST (not GraphQL) |
|---|---|---|
| `/api/` | `upload/profile-photo/`, `upload/content-media/` (DRF) | Multipart file upload; streams to Cloudinary when configured |
| `/payments/` | `POST /payments/callback/<gateway>/` (provider webhook), `GET /payments/status/<order_reference>/` (client poll), `GET /payments/health/` (ops probe) | Provider-initiated HTTP callback + long-poll status; webhook is auth-free, idempotent, always 200 |
| `/media/` | served by `ranged_media_serve` | HTTP **Range/206** streaming for mobile `<video>` playback |
| `/admin/` | Django admin site | Session-based backoffice (not an API surface) |

### 2.3 Decision summary

- **GraphQL:** all interactive feature CRUD, auth, payments UX, wallet/ledger reads, admin
  tooling consumed by the app. Single schema, resolver-level RBAC, `X-Tenant-ID` scoping.
- **REST:** uploads, gateway/webhook I/O, media streaming, health probes. Auth: DRF JWT for
  uploads (SimpleJWT classes configured), webhook unauthenticated by design, media
  anonymous (URL-based).
- No formal GraphQL versioning; additive-only evolution. REST paths avoid version prefixes
  (an `api/v1/lost-found/` pattern exists but is not mounted — out of scope here).

---

## 3. API Architecture

### 3.1 GraphQL endpoint

- Strawberry GraphQL 0.215, single composed schema in `lipaidox_backend/schema.py`.
- `JWTGraphQLView` (csrf-exempt) authenticates `request.user` from `Authorization: Bearer`
  **before** resolvers run (`lipaidox_backend/urls.py:11-24`).
- Auth header: `Authorization: Bearer <access-token>` — HS256 JWT, 1h; claims `user_id`,
  `username`, `role`, `tenant_id`. Issued by `loginUser`, `registerUser`, `googleAuth`,
  `refreshAccessToken`.
- Authorization: resolver decorators (`@require_creator`, `@require_admin`, …) — see
  `docs/SECURITY.md` equivalent below (§5) and `ROLE_ACCESS_CONTROL.md`.
- Errors: standard GraphQL `errors[]` with message strings (typed error unions are a
  future improvement).
- Pagination: manual `offset`/`limit`; no Relay cursor convention yet.

### 3.2 REST endpoints

**`/api/` (uploads):** DRF `JWTAuthentication`; per-type size caps; streams to Cloudinary
(`CLOUDINARY_*`) or `MEDIA_ROOT`; global 25 MB body/memory cap defaults (configurable).

**`/payments/`:**
- `GET /payments/health/` — gateway probe (read-only; cached 60s).
- `POST /payments/callback/<gateway>/` — provider webhook; auth-free, idempotent, always
  200; routes to gateway `handle_callback` → verify → `fulfill_charge`.
- `GET /payments/status/<order_reference>/` — client status poll; re-verifies with the
  provider; 404 on unknown refs; no secrets in response.
- NBC/Haminass Pay client: `POST /api/v1/payments`, `GET /api/v1/payments/<ref>`,
  `POST /api/v1/payments/<ref>/refund`, `POST /api/v1/payouts`, `GET /api/v1/payouts/<ref>`.

**`/media/`:** `ranged_media_serve` — Range/206, path-traversal guarded, DB connection
released before long streams.

---

## 4. Database Architecture

### 4.1 Engine & configuration

- **PostgreSQL** default (`settings.py:214-250`): (1) `USE_SQLITE=True` → SQLite `db.sqlite3`
  (dev/DB-free tests); (2) `DATABASE_URL` → Postgres, `sslmode=require`; (3) discrete
  `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` (defaults
  `lipaidox2`/`lipaiduser`/`lipai123`/`localhost:5432`).
- Tenancy root: `lipaidox/models.py::Tenant` (db `tenants`, UUID PK, `domain` unique +
  indexed). `TenantAwareModel` adds nullable `tenant` FK.

### 4.2 Entities by domain

All models use `UUIDField(primary_key=True)` unless stated; money is `DecimalField`;
cross-app references are string FKs.

**Identity / Auth (`lipaidox_auth`, db `users`)**
- `User(AbstractUser)` — UUID PK, `tenant` FK, `phone_number`/`phone_country_code`, `role`
  (`fan` default/`creator`/`admin`), `status` (default `pending`), `email_verified`,
  `phone_verified`, `date_of_birth`, `auth_provider`, `google_id`, `apple_id`, `module`,
  `profile_title`, `staff_capabilities` (JSON), `is_first_login`. Partial unique per tenant:
  `unique_phone_per_tenant`, `unique_google_per_tenant`, `unique_apple_per_tenant`
  (conditioned on non-null).
- `RefreshToken` (`token_hash` unique, 30-day TTL), `TwoFactorAuth` (`secret` plaintext,
  `is_enabled`), `BackupCode` (`code_hash`), `TwoFactorLoginChallenge` (10-min),
  `EmailVerification`, `PhoneVerification`, `PasswordResetToken`, `PasswordResetOtp`
  (`code_hash` hashed, `attempts`, `is_used`, `expires_at`).

**Admin & Security**
- `admin_panel`: `AdminAccount` (O2O user, `admin_role`, permission flags), `AdminAction`
  (append-only audit; `reversal_check` constraint), `AccountFlag`, `PlatformAccount`,
  `Announcement`, `PlatformPost`, `SystemAlert`, `PlatformSetting`, `EmailCampaign`,
  `Refund`. (`AuditLog` defined but unused.)
- `security`: `SecurityEvent`, `SecuritySettings` (`two_fa_secret` plaintext, `backup_codes_hash`
  ArrayField, risk 0–1), `LoginHistory`, `DeviceSession` (unique user+device_fingerprint),
  `TwoFAAttempt` (unique `code_hash`, 5/hr). Not wired into the root schema.

**Profiles / Onboarding / KYC**
- `CreatorProfile` (db `profiles`, O2O user, `username` unique, `account_kind`,
  `creator_tier`, `is_verified`), `Follow`, `MembershipSubscription`, `Review` +
  `ReviewHelpful`/`ReviewReport`, `UsernameHistory`.
- `CreatorOnboardingStatus` (O2O; 8-step enum), `OnboardingStepLog` (append-only).
- `KYCStatus` (O2O), `VerificationDocument`, `BusinessVerification`, `KYCRejectionReason`.
- `PlatformCategory` (slug unique), `ContentClassification` (O2O creator, targeting fields).

**Content**
- `Content` (db `contents`) → `CreatorProfile`, `ContentSeries` (self-FK `parent`),
  `ContentMedia`, `ContentTag`, `ContentAttachment`, `ContentAccessRule`, `ContentComment`
  (`deleted_at`), `ContentLike`/`ContentBookmark`/`ContentView`/`ContentReview`/
  `ContentReport`/`ContentModerationLog`/`ContentAppeal`, `ContentLicense` (auto `LPDX-…`).

**Payments / Wallet**
- `Charge` — user FK, gateway (default `simulated`), `purpose`
  (wallet_topup/ppv/credits/live_entry/subscription), `amount` Decimal(10,2), `currency`,
  `status`, `method`, `idempotency_key`, `metadata`.
- `PaymentMethod` — unique `(user, type, identifier…)` per tenant; `deleted_at`.
  (`bank_account_number_encrypted` is plaintext despite the name.)
- `MobileMoneyProvider` — unique `(provider_name, country_code)`.
- `FanWallet` — unique `(user, currency)`, balance ≥ 0.
- `CreatorWallet` (db `creator_wallets`, unique `(creator, currency)`) — pending/available/
  on_hold balances, lifetime stats, earnings buckets, 6 ≥ 0 CheckConstraints.
- `Transaction` (db `transactions`, platform ledger) — `fan → User`, `creator →
  CreatorProfile`, type/status, `gross`/`platform_fee_percent`/`platform_fee`/`net`,
  source UUIDs, payment_method (SET_NULL), refund fields, `ip_address`. Constraint
  `txn_net_calculation`: `net = gross − fee`.
- `WalletTransaction` (db `wallet_transactions`, append-only) — `balance_before`/
  `balance_after`, `balance_type`, 7-day clearing. Constraint
  `wallet_txn_balance_consistency`: `balance_after = balance_before + amount`.
- `PayoutTransaction` — payment_method FK **PROTECT**; tax fields; `retry_count < 3`;
  reversal/admin-approval fields. Constraint `payout_net_calculation`.
- `WalletClearingJob` — clearing batch tracking.

**Subscriptions / Plans / PPV / Tips / Monetization**
- `Subscription` (fee 20%); `SubscriptionPayment`; `CreatorPlan` (tier unique; `None` =
  unlimited, `0` = not allowed); `CreatorPlanSubscription`, `CreatorPlanPayment`,
  `CreatorLiveCreditUsage`, `CreatorPurchasedCredits`; `PPVPurchase` (fee 15%, timed expiry);
  `Tip` (fixed 15%); `MonetizationSettings` + `MonetizationPriceHistory`.

**Credits & Live Billing**
- `CreatorCreditWallet` (Decimal(20,6) buckets), `FanCreditWallet` (integer buckets),
  `FanCreditLedger` (append-only), `FanCreditGiftSent`.
- `LiveCreditReservation` (wallet FK PROTECT, live_stream O2O), `LiveBillingEvent`
  — `(reservation, sequence)` unique → replay-safe heartbeat ledger.
- `CreditPackage`, `CreditPurchase` (idempotency_key + unique constraint),
  `CreditGift`, `FinancialAuditLog` (append-only).

**Live streaming** — `LiveStream`, `LiveStreamEntry` (unique stream+fan), `LiveStreamChatMessage`,
`LiveStreamViewer`, `LiveStreamCreditTransaction`, `LiveStreamMedia`.

**Messaging / Notifications** — `Conversation`, `Message` (rich message_type, `reply_to`),
`MessageAttachment`, `MessageReaction`, `AutoDMRule`, `QuickReply`, `ScheduledMessage`,
`Broadcast`, `StarredMessage`, `ConversationReport`; `Notification`,
`NotificationPreference`, `NotificationDeliveryLog`, `NotificationQueue`, `NotificationTemplate`,
`PushToken`.

**AI / Recommendation / Feedback** — `ai_intelligence` (`AIMediaIntelligence`,
`ContentWatermark`, `AIScanQueue`, `AIFingerprintRegistry`, analytics, `ContentScore`,
`FeedRecommendation`, `SuggestedCreator`); `recommendation` (`UserInteraction`, `ContentScore`,
`FeedRecommendation`, `TrendingContent`, `SuggestedCreator`, `UserInterestProfile`,
`PromotedContent`); `feedback` (`AppFeedback`, rating 1–5 constraint).

### 4.3 Relationship patterns

1. String cross-app FKs (User, CreatorProfile, PaymentMethod, AdminAccount, LiveStream,
   FanCreditGiftSent).
2. O2O profile anchors: `User↔CreatorProfile`, `User↔KYCStatus`,
   `CreatorProfile↔ContentClassification`, `User↔CreatorOnboardingStatus`.
3. `TenantAwareModel` spreads `tenant` on most tables.
4. Self-references: `ContentSeries.parent`, `Message.reply_to`, etc.
5. Ledgers reference origin rows by **UUID column, not FK** (keeps append-only ledgers
   independent).

### 4.4 Transaction strategy & integrity

- **Choke point** — `lipaidox/wallet/services.py`; atomic + `select_for_update`; fixed lock
  order (wallet → reservation) to avoid deadlocks (`lipaidox/credits/live_billing.py`).
- **Top-up-then-spend** — gateway only credits `FanWallet` (`payment/fulfillment.py`);
  purchases spend via `settle()` which row-locks both wallets, writes one `Transaction`,
  credits creator net of platform fee.
- **Exactly-once fulfillment** — `fulfill_charge` atomic + row-locked, PENDING → SUCCEEDED
  once; webhook always 200; races between webhook and polling are safe.
- **Idempotency keys** — `charge-<charge.id>`, `payout-<txn.id>`, credit purchases
  (DB unique backstop). No FX internally: charge currency == wallet currency.
- **Append-only ledgers** — never update/delete; balances derived.
- **Credit math** — 100 credits = $10 = 15 min ⇒ 1 credit per 9 s, fixed-point
  `DECIMAL(20,6)`; engine functions take `now=` for deterministic tests; a sweeper settles
  dropped sessions.

---

## 5. Security Architecture

### 5.1 Authentication

- `AUTH_USER_MODEL = "lipaidox_auth.User"`; status blocklist via
  `lipaidox/auth/user_eligibility.py`.
- **Access tokens (GraphQL):** PyJWT HS256, 1h, claims `user_id`/`role`/`tenant_id`;
  `JWTGraphQLView` authenticates `request.user` pre-resolver.
- **Refresh sessions:** opaque token (`secrets.token_hex(40)`), stored SHA-256 only, with
  device User-Agent; not rotated on refresh; revocable.
- **Social sign-in:** `googleAuth(id_token)` → Firebase Admin (`verify_id_token`, requires
  `email_verified=True`) or GIS Web-client ID verification (clock-skew-limited, issuer
  `accounts.google.com`). ⚠️ `DEBUG=True` allows literal test tokens.
- **Passwords:** Argon2id primary (PBKDF2 600k fallback), Django validators active.

### 5.2 Authorization (RBAC)

- Roles `fan`/`creator`/`admin`; resolver decorators `@require_creator`, `@require_admin`,
  `@require_any_role`, `@require_creator_or_admin` read role from the **DB** (instant role
  flips). Matrix in `ROLE_ACCESS_CONTROL.md`.

### 5.3 Password reset / OTP

- ORM path wired to GraphQL: `PasswordResetOtp` (`code_hash` via Django `make_password`),
  10-min TTL, max 5 attempts, supersede-on-new. `PASSWORD_RESET_INLINE_OTP=False` → code
  emailed only; magic-link via sha-256'd token (1h). 2FA TOTP (`pyotp`, `valid_window=1`)
  + hashed backup codes; login challenge 10-min.
- `forgotpassword_auth/` — framework-independent reference implementation
  (anti-enumeration, HMAC-SHA256 pepper); not wired to Django (ADR-009).

### 5.4 Token & secret handling

- Access token unrevocable statelessly; refresh/magic-link/2FA/backup stored SHA-256; OTP
  hashes salted.
- Secrets live in `.env` next to `manage.py` (python-decouple) — `.env` and
  `*-service-account*.json` git-ignored. Firebase service-account auto-discovery with
  strict validation; Cloudinary/NBC keys server-only.
- ⚠️ Gaps to close before prod: `SECRET_KEY`/`JWT_SECRET_KEY` default to a known value
  (forgeable HS256); TOTP secrets plaintext; OTP prefill code in query string; phone OTP
  exposed in GraphQL response.

### 5.5 CSRF / CORS

- GraphQL & uploads & webhook: CSRF-exempt (token/webhook-method auth by design); Django
  admin session-authenticated (CSRF intact; `CSRF_TRUSTED_ORIGINS` from env).
- CORS: `CORS_ALLOW_ALL_ORIGINS = DEBUG`; credentials allowed; headers include
  `authorization`, `x-tenant-id`; product allow-list via `CORS_ALLOWED_ORIGINS` (empty by
  default → no cross-origin until set).

### 5.6 Rate limiting

- **None globally** — recommend throttling login, OTP request/verify, `googleAuth`,
  phone OTP before production.

### 5.7 Transport & hardening

- `SecurityMiddleware` + WhiteNoise present; **missing** `SECURE_SSL_REDIRECT`, HSTS,
  secure cookies, nosniff, XSS filter.
- Upload caps: 25 MB global JSON/memory defaults (configurable); per-type REST caps up to
  500 MB video. Media streaming closes DB connections to avoid exhausting Postgres.

### 5.8 Threat & mitigation matrix

| # | Threat | Current state | Mitigation |
|---|---|---|---|
| 1 | Forged JWT (default key) | `JWT_SECRET_KEY` falls back to default | Require random `SECRET_KEY`/`JWT_SECRET_KEY` in prod |
| 2 | Brute-force auth/OTP | No global throttle | Per-IP/per-user rate limits |
| 3 | Cross-tenant token use | No user↔tenant binding at auth | Bind in auth layer / enforce per resolver |
| 4 | OTP leakage (URL / inline) | Query-string prefill; inline flags | Keep flags False; drop URL codes from emails |
| 5 | Unauthenticated read queries | `all_users`, `user_by_id`, verification lists un-gated | Gate behind auth + role checks |
| 6 | TOTP secrets at rest | Plaintext in two tables | Encrypt at rest |
| 7 | Banned/suspended user mid-session | Partial resolver checks | Enforce status at `authenticate_request` |
| 8 | Webhook replay | Idempotent fulfillment | Verify gateway signature/secret |
| 9 | Debug backdoors | Test tokens when `DEBUG=True` | Force `DEBUG=False` in prod |
| 10 | Secret/OTP log exposure | Names-only logging | Central redaction filter |

---

## 6. Development Guide

### 6.1 Prerequisites & setup

- Python 3.12 (`.python-version`), PostgreSQL 13+ (for Postgres-backed suites).
- Virtualenv at `./myenv` (not always activated — call `./myenv/bin/python` explicitly).
- `cp .env.example .env`, then fill values. Never commit `.env`. Key switches:
  `USE_SQLITE`, `DATABASE_URL` / `DB_*`, `DEBUG`, `PAYMENT_GATEWAY_DEFAULT`, `EMAIL_*` /
  `RESEND_API_KEY`, `CLOUDINARY_*`, `FIREBASE_*` / `GOOGLE_OAUTH_*`.

### 6.2 Running the server

```bash
./run.sh                       # frees port 8000, binds 0.0.0.0:8000
./run.sh 8001                  # custom port
```
GraphiQL: <http://localhost:8000/graphql/>. Android emulator → `10.0.2.2`; physical
devices need LAN IP in `ALLOWED_HOSTS`.

### 6.3 Docker

**Not present** — no `Dockerfile`/compose; no Redis/Celery containers provided. Local
Postgres is expected.

### 6.4 Database

```bash
./myenv/bin/python manage.py makemigrations <app_label>   # label ≠ module path!
./myenv/bin/python manage.py migrate
```
App labels differ: `lipaidox.auth` → `lipaidox_auth`, `lipaidox.messaging` →
`lipaidox_messaging`, etc. Seeding: `manage.py seed_plans`; credits packages self-seed.

### 6.5 Redis / Celery

- Redis installed, **unused in request path**. Celery pinned but **no app configured**;
  `ContentMutation` falls back to running the media task synchronously. Do not assume a
  worker is running.

### 6.6 Testing

```bash
./test.sh                       # DB-free first, then Postgres-backed
./test.sh --keepdb              # reuse migrated schema
./test.sh quick                 # DB-free suites only (USE_SQLITE=True)
./test.sh db [labels…]           # Postgres-backed suites / labels
```

- Two families (`test.sh`): `FAST=(creator_plans payment media_processor)` DB-free;
  `DB=(credits feedback content)` need Postgres and run via
  `--settings=lipaidox_backend.test_settings`.
- `SchemaIsolatedRunner` creates a schema in the existing DB, confines `search_path` to it,
  migrates, drops (or keeps with `--keepdb`, schema `lipaidox_test`). Needs `CREATE
  SCHEMA`, not `CREATEDB`.
- Single tests: `manage.py test lipaidox.<module>…`; framework-independent:
  `python -m unittest forgotpassword_auth.tests.test_service`.
- Billing tests inject time via `now=`.

### 6.7 Linting / formatting / typing

- Pinned in `requirements.txt`: `black` 23.11, `flake8` 6.1, `isort` 5.12, `pytest` 7.4 —
  no config files or CI gate in the repo yet. `mypy` not configured.

### 6.8 Module scaffolding

```text
lipaidox/<module>/ : models/ (one file per model) · queries/ · mutations/ · schema/ · migrations/
```
Register in `INSTALLED_APPS`, mix Query/Mutation into `lipaidox_backend/schema.py` (watch
MRO on name collisions, e.g. `NotificationQuery` before `LmsNotificationQueries`).

---

## 7. Deployment Guide

### 7.1 Production topology

```text
 Internet → Render (gunicorn workers) → PostgreSQL (managed, DATABASE_URL, sslmode=require)
   ├─ wsgi application (ASGI present but unused)
   ├─ whitenoise serves /static/ (collectstatic at build)
   ├─ ranged_media_serve → /media/ from MEDIA_ROOT (Disk) or Cloudinary URLs
   ├─ /graphql/ · /payments/ · /api/ · / (see §1.2)
   └─ user media lives OFF-BOX: Cloudinary (recommended) or Render Disk
```
No Docker; Render builds from `requirements.txt`. No front web server/CDN for static.

### 7.2 Environment configuration (production)

`DEBUG=False`; strong `SECRET_KEY` + explicit `JWT_SECRET_KEY`; `ALLOWED_HOSTS`
(Render host auto-appended via `RENDER_EXTERNAL_HOSTNAME` + `.onrender.com` wildcard);
`CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS`; `DATABASE_URL`; `MEDIA_ROOT` (Disk);
`CLOUDINARY_*`; payment vars (`PAYMENT_GATEWAY_DEFAULT=nbc`, `NBC_*`, `NBC_REDIRECT_URL`);
email (`RESEND_API_KEY` preferred — Render blocks SMTP ports); `FRONTEND_ORIGIN` &
password-reset path; `GOOGLE_OAUTH_*`/`FIREBASE_*`; gunicorn tuning
(`GUNICORN_TIMEOUT=300` for uploads, `WEB_CONCURRENCY`).

### 7.3 Deploy steps

1. `pip install -r requirements.txt` (build)
2. `manage.py collectstatic --noinput` (build)
3. `manage.py migrate` (pre-start)
4. `manage.py check` (surfaces `payment.W001` simulation / `payment.W002` NBC-missing-key)
5. Start gunicorn on `$PORT` with `gunicorn.conf.py` (bind left to Render's `$PORT`)
6. Attach a Render Disk → set `MEDIA_ROOT` (or set Cloudinary creds)
7. Verify `/payments/health/`, a `/media/` Range request returns 206, GraphiQL reachable

### 7.4 Health checks

`GET /payments/health/`, `GET /system/health/` (lost&found — out of scope but present),
`manage.py check_payment_gateway`, `manage.py check`.

### 7.5 Runbook / caveats

- Uploads 404 after redeploy → media was in the app dir; fix `MEDIA_ROOT`/Cloudinary.
- Email hanging → Render blocks outbound SMTP; use Resend HTTP API.
- Payment 502s → NBC settlement currency mismatch (`NBC_SETTLEMENT_CURRENCY`).
- NBC card 403 → return host not approved on the key; leave `NBC_REDIRECT_URL` empty until
  approved.
- Keep `PASSWORD_RESET_INLINE_OTP` / `EMAIL_VERIFICATION_INLINE_OTP` **False** in prod.
- Redis/Celery not operational — media-pipeline work is synchronous until a broker exists.

---

## 8. Architecture Decision Records

Full ADRs live in `docs/ADR/` (each with Context / Decision / Consequences). Summary:

| # | Decision |
|---|---|
| 001 | GraphQL-first API — single Strawberry schema; REST only for uploads, webhooks, media, probes |
| 002 | Per-module package layout convention (`models/`, `queries/`, `mutations/`, `schema/`) |
| 003 | Custom `User` (`lipaidox_auth`, UUID PK, tenant FK, role) + PyJWT bearer auth |
| 004 | Wallet choke point — top-up-then-spend, atomic + row-locked money movement |
| 005 | Header/host multi-tenancy with `TenantAwareModel` |
| 006 | (Lost & Found REST — **out of scope** for this compilation) |
| 007 | Schema-isolated Postgres test runner (no `CREATEDB` needed) |
| 008 | Off-box media (Cloudinary) + Range-aware serving |
| 009 | Framework-independent password-reset package |
| 010 | Argon2id-first password hashing with PBKDF2 fallback |

---

*This is the single compilation for the creator-monetization platform. LMS
(`lms_*`) and Lost & Found documentation are deliberately excluded by request.*