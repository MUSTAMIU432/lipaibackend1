# Lipaidox Backend — API Architecture

> Companion to `docs/ARCHITECTURE.md`. Describes the **current** API surfaces, their
> conventions, and known limitations (architecture phase — no code changes).

## 1. Overview

The backend exposes one GraphQL endpoint plus two REST namespaces and a media streamer.
REST is used for file uploads, payment webhooks/status, the Lost & Found/Discover module,
and media playback — GraphQL is the default client API. There is **no** OpenAPI/Swagger
schema for GraphQL (drf-yasg is installed but unused).

| Surface | Mount | Transport |
|---|---|---|
| GraphQL | `/graphql/` | POST (JSON), GraphiQL enabled |
| Uploads (creator profile) | `/api/` | DRF REST |
| Payments | `/payments/` | DRF REST (webhook, status, health) |
| Lost & Found / Discover | `/` (root) | DRF REST |
| Static | `/static/` | WhiteNoise |
| Media (Range) | `/media/` | `ranged_media_serve` |

## 2. GraphQL Endpoint

- **Stack:** Strawberry GraphQL 0.215 (`strawberry-graphql-django`), a single composed
  schema built in `lipaidox_backend/schema.py` (`Query`/`Mutation` multiple inheritance).
- **View:** `JWTGraphQLView` (csrf-exempt) — authenticates `request.user` from the Bearer
  token via PyJWT **before** resolvers run (`lipaidox_backend/urls.py:11-24`).
- **Entrypoints:** `query <field>` / `mutation <field>`; `hello` is a smoke-test field.
- **Naming:** module-prefixed fields and types (e.g. `myWallet`, `topUpWallet`,
  `requestPasswordReset`, `purchaseCreditPack`); resolver-level guards enforce roles.

### 2.1 Authentication
- Header: `Authorization: Bearer <access-token>` (HS256 JWT, 1h; claims `user_id`,
  `username`, `role`, `tenant_id`). Issued by `loginUser`, `registerUser`, `googleAuth`,
  `refreshAccessToken`.
- Errors: 401-style failures surface as resolver errors (null field + message) when no
  token/invalid token; `request.user` may be anonymous.

### 2.2 Authorization
- Decorator/caller checks per role (`@require_creator`, `@require_admin`, …) — see
  `docs/SECURITY.md` §2 and `ROLE_ACCESS_CONTROL.md`.

### 2.3 Versioning
- **No formal GraphQL versioning.** The schema is evolvable additive (fields/mutations);
  breaking changes should land as superseding fields with deprecated aliases. Client-facing
  contract is effectively enforced by the frontend's generated types.

### 2.4 Errors
- Standard GraphQL error envelope (`errors[]` with `message`).
- Domain errors surface as `message` strings from resolvers (e.g. `InsufficientFunds`,
  invalid OTP, weak password). Specific error *typing* per operation is a
  **future improvement** (typed error unions / `errors` field on mutations).

### 2.5 Pagination
- Manual `offset`/`limit` on list queries (e.g. `allPublicContent(offset, limit)`,
  `myCreditTransactions(page, pageSize)`).
- No Relay connection/cursor convention — consistent offset pagination is recommended
  going forward.

## 3. REST API — `/api/` (creator profile uploads)

- DRF views under `lipaidox/creator_profile/views.py`.
- Endpoints: `upload/profile-photo/`, `upload/content-media/` (+ related media classifiers).
- Auth: DRF `JWTAuthentication` (SimpleJWT classes configured in
  `REST_FRAMEWORK`/`settings.py:446-453`) — **note:** the GraphQL layer uses its own PyJWT;
  harmonizing REST + GraphQL auth is a pending decision.
- Files streamed to Cloudinary when `CLOUDINARY_*` are set; otherwise `MEDIA_ROOT`.
- Per-type size caps (image/video) with 25 MB global body/memory cap defaults (configurable).

## 4. REST API — `/payments/`

- `GET /payments/health/` — gateway probe (read-only nonexistent-reference lookup; cached 60s).
- `POST /payments/callback/<gateway>/` — provider webhook; **auth-free by design**,
  idempotent, always returns 200 after processing; routes to the gateway's
  `handle_callback` → verify → `fulfill_charge`.
- `GET /payments/status/<order_reference>/` — client status poll; re-verifies against the
  provider; 404 for unknown references; no secrets in the response.
- NBC/Haminass Pay: `POST /api/v1/payments`, `GET /api/v1/payments/<ref>`,
  `POST /api/v1/payments/<ref>/refund`, `POST /api/v1/payouts`, `GET /api/v1/payouts/<ref>`.
- Webhook + polling are race-safe: fulfillment is atomic + row-locked (see
  `docs/DATABASE.md` §6).

## 5. REST API — `/` (Lost & Found / Discover)

Root-mount REST under `lipaidox/lost_found/urls.py` (NOT under a version prefix):

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/items/`, `/items/create/` | List / create items (with AI analysis) |
| GET/PATCH/DELETE | `/items/<uuid>/`, `/items/<uuid>/update-status/`, `/items/<uuid>/delete/` | Item CRUD |
| POST | `/analyze/` | Run all AI services on an image |
| POST | `/search/similar/` | Visual similarity search |
| GET | `/compare-prices/` | Price comparison (cached) |
| POST | `/items/<uuid>/vote/`, `/items/<uuid>/report/` | Community voting / reporting |
| GET | `/items/<uuid>/consensus/`, `/user/voting-history/`, `/trending/` | Community features |
| POST | `/reports/<uuid>/moderate/` | Moderation |
| GET | `/system/health/`, `/system/statistics/` | Service health / stats |
| POST | `/discover/analyze/`, `/discover/similar-place/` | `/discover` page AI |
| GET | `/features/…` | Legacy per-feature entrypoints |
| — | `api/v1/lost-found/…` | Versioned patterns **defined but not mounted** |

- Shaping: `discover_adapters.py` converts raw service results into the exact TypeScript
  shapes the frontend expects; unusable results → `None` (a gap flag in the view response).
- Community (polls, Q&A) lives on GraphQL (`LostFoundCommunityQuery/Mutation`) while the
  AI features above are REST (ADR-006).

## 6. Media Streaming — `/media/`

- `ranged_media_serve` serves uploads with HTTP **Range** support (`206 Partial Content`)
  so Android/mobile `<video>` plays and seeks; registered in DEBUG **and** production
  (`urls.py:31-42`).
- Path-traversal guarded; DB connection closed before long streams.

## 7. API Conventions (Current & Recommended)

| Concern | Today | Recommended |
|---|---|---|
| Auth header | `Authorization: Bearer <JWT>` (GraphQL) / DRF JWT (REST) | Single shared token path across GraphQL + REST |
| Tenant | `X-Tenant-ID` header or host match | Keep header; enforce user↔tenant binding centrally |
| Errors | GraphQL `errors[]` + message strings | Typed error unions; structured REST error envelope |
| Pagination | offset/limit | Consistent offset/limit contract; cursor for high-volume lists |
| Idempotency | Keys on charges/purchases | Extend to all state-changing ops |
| Rate limits | none | Per-endpoint throttles (see `docs/SECURITY.md` §7) |
| Versioning | none | Additive-only; document deprecations in changelog |

## 8. Related

- GraphQL schema composition & module layout: `docs/ARCHITECTURE.md` §6.
- Auth, RBAC, CSRF/CORS detail: `docs/SECURITY.md`.
- Lost & Found module behavior: `lipaidox/lost_found/README.md`, `docs/ARCHITECTURE.md` §9.