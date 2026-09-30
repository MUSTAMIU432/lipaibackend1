# Lipaidox Backend — Security Architecture

> Status: Draft — architecture phase. Describes the security posture of the **current**
> codebase, including known gaps (these inform the implementation phase).

## 1. Authentication

### 1.1 Identity model
- `AUTH_USER_MODEL = "lipaidox_auth.User"` — `AbstractUser` subclass (UUID PK, tenant FK,
  `role`, `status`, `email_verified`, `phone_verified`, `auth_provider`, `google_id`,
  `apple_id`). See `docs/DATABASE.md` §2.1.
- Login blocklist enforced through `lipaidox/auth/user_eligibility.py`
  (`suspended`/`banned`/`inactive`/`deleted`/`disabled` + `assert_user_may_authenticate`).

### 1.2 Access tokens (GraphQL)
- **PyJWT** (not SimpleJWT) — `lipaidox/auth/jwt_auth.py`:
  - `ACCESS_TOKEN_LIFETIME = 1h`, `REFRESH_TOKEN_LIFETIME = 30d`, `ALGORITHM = HS256`.
  - Claims: `user_id`, `username`, `role`, `tenant_id`, `exp`, `iat` (no `jti`, `iss`, `aud`, `typ`).
  - Signed with `settings.JWT_SECRET_KEY` (defaults to `SECRET_KEY`).
- `JWTGraphQLView` (`lipaidox_backend/urls.py:11-16`) calls `authenticate_request(request)`
  before resolvers run: parses `Authorization: Bearer <token>`, verifies signature/expiry,
  loads `User`. (**No** tenant binding, `is_active` re-check, or role re-check here.)

### 1.3 Refresh sessions
- Opaque refresh token = `secrets.token_hex(40)`, stored only as **SHA-256** with the
  device `User-Agent`. `refresh_access_token` does **not rotate** the refresh token.
- Session revoke (`logout_user`, `revoke_session`, `revoke_other_sessions`) flips status.

### 1.4 Social sign-in (Google / Firebase)
- `googleAuth(id_token, signup_role)` in `lipaidox/auth/mutations/user_mutation.py:302-437`.
- Issuer peek is **unverified** base64 decode; route by `iss`:
  - `securetoken.google.com` → **Firebase Admin SDK**
    `firebase_auth.verify_id_token()` (`googleOuth.py:263-316`). Requires
    `email_verified=True`.
  - else → **GIS**: `google.oauth2.id_token.verify_oauth2_token` against the configured
    Web client IDs (`GOOGLE_OAUTH_CLIENT_ID` + `_ADDITIONAL_CLIENT_IDS`), clock skew
    limited to `GOOGLE_OAUTH_CLOCK_SKEW_SECONDS` (120s), issuer must be `accounts.google.com`.
- Service-account JSON resolved from env (`FIREBASE_SERVICE_ACCOUNT_PATH`, B64/JSON, or
  auto-discovered files) — the file itself is secret and git-ignored.
- ⚠️ `DEBUG=True` permits literal test tokens (`"test-google-token"`) that bypass Firebase
  verification (`googleOuth.py:275-289`) — dev-only.

### 1.5 Password hashing
- Preferred hasher: **Argon2id** (via `argon2-cffi`), with PBKDF2-HMAC-SHA256 (600k
  iterations) as fallback and PBKDF2SHA1/BCryptSHA256 kept for verification of legacy
  hashes (`settings.py:276-289`). Existing PBKDF2 hashes re-hash to Argon2 on next login.
- Django default password validators in effect (similarity, min length, common, numeric).

## 2. Authorization (RBAC)

- Roles: `fan` (default) · `creator` · `admin`.
- Enforcement at the **GraphQL resolver** level (`lipaidox/auth/permissions.py`):
  `@require_creator`, `@require_admin`, `@require_creator_or_admin`,
  `@require_any_role(...)`; function checks `check_user_permission` /
  `check_user_any_permission`; `RolePermissions` feature gates.
- Role is read from the **DB** (`request.user.role`), not the JWT claim → role flips apply
  immediately.
- Access control matrix: `ROLE_ACCESS_CONTROL.md` (creator-only: payouts, monetization,
  KYC, content authoring, profile management; admin-only: user management, KYC admin,
  platform administration).
- Some modules define **local** `require_admin` helpers instead of sharing
  `permissions.require_admin` (admin_panel, ai_intelligence, recommendation, security, ppv)
  — a consolidation opportunity.

## 3. Password Reset / OTP

Two implementations exist; **only the Django-ORM path is wired to GraphQL**:
- `requestPasswordReset` → `PasswordResetOtp` row (`code_hash` via Django `make_password`,
  Argon2/PBKDF2 salted), TTL 10 min, max 5 attempts, previous pending rows superseded.
  `PASSWORD_RESET_INLINE_OTP=False` → code emailed via SMTP/Resend/console and **not**
  returned in GraphQL; `True` returns `inlineOtp` (must stay off on a public API).
- `verifyPasswordResetOtp` does **not** consume; `resetPassword` validates the new password
  server-side (upper+lower+digit+special, 8–128) and marks the OTP `USED`.
- Magic-link: `requestPasswordResetLink` → 32-byte token, stored SHA-256 (`PasswordResetToken`,
  1h TTL), `resetPasswordWithToken`.
- Initial-password for Google-linked accounts (OTP), email and phone verification OTPs follow
  the same pattern. Email OTP for onboarding uses `EMAIL_VERIFICATION_INLINE_OTP`.
- 2FA: TOTP (`pyotp`, `valid_window=1`) + hashed backup codes; login returns a challenge
  (10-min), fulfilled by `completeTwoFactorLogin`. Setup/disable require a live code.
- `forgotpassword_auth/` — framework-independent package (no Django imports) implementing the
  same flows with **anti-enumeration** (unknown email returns the same success shape) and
  HMAC-SHA256 OTP hashing with a pepper. It is tested standalone with `unittest` and is not
  wired to Django (see ADR-009).

## 4. Token & Secret Handling

- Access token: HS256-signed, 1h. Unrevocable while valid (revocation is refresh-token level).
- Refresh / magic-link / 2FA challenge / backup codes: stored only as SHA-256.
- OTP codes at rest: salted Django password hashes; protected by attempt caps & expiry.
- ⚠️ **Known gaps** (must be addressed before production):
  - `JWT_SECRET_KEY` defaults to `SECRET_KEY`, and `SECRET_KEY` has a hardcoded Django
    default that the shipped `.env` reproduces → HS256 tokens are **forgeable** in the
    current config. Generate a strong random `SECRET_KEY` + explicit `JWT_SECRET_KEY`.
  - `TwoFactorAuth.secret` and `SecuritySettings.two_fa_secret` stored plaintext
    (documented precedent; recommend encryption at rest / HSM).
  - OTP deep-link embeds the code in a query string (`send_password_reset_otp_email`)
    — recorded in browser history/Referer/proxy logs. Gate behind
    `PASSWORD_RESET_OTP_LINK_ENABLED` or drop the prefill param.
  - Phone OTP returned in the GraphQL response regardless of environment
    (`PhoneVerificationType.otp_code` always present) and generated with `random.randint`.

## 5. CSRF

- The GraphQL endpoint is `@csrf_exempt` (`urls.py:21`) — token-authenticated API; safe by
  design when CORS allows only trusted origins with credentials.
- REST uploads and the payments webhook are also CSRF-exempt (bearer/webhook auth).
- `CsrfViewMiddleware` present for session-authenticated surfaces (Django admin).
  `CSRF_TRUSTED_ORIGINS` derives from env (`settings.py:435-441`).

## 6. CORS

- `CORS_ALLOW_ALL_ORIGINS = DEBUG`; `CORS_ALLOW_CREDENTIALS = True`.
- Allowed headers include `authorization` and `x-tenant-id` (`settings.py:414-421`).
- Production: allow-list via `CORS_ALLOWED_ORIGINS` env (default empty → **no cross-origin
  allowed until set**).

## 7. Rate Limiting

- **None globally today.** No `django-ratelimit`, no DRF throttles. Only per-OTP attempt
  counters and the unwired `TwoFAAttempt` (5/hr) exist.
- **Recommendation:** throttle login, `requestPasswordReset`, OTP verify, `googleAuth`,
  and SMS/phone OTP before production.

## 8. Secrets Management

- `.env` next to `manage.py`, read by **python-decouple** (`AutoConfig(search_path=BASE_DIR)`,
  `settings.py:64-66`). `.env` and `*-service-account*.json` are git-ignored.
- Sensitive settings: `SECRET_KEY`, `JWT_SECRET_KEY`, `NBC_API_KEY`, `EMAIL_HOST_PASSWORD`,
  `RESEND_API_KEY`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_TRANSLATE_API_KEY`,
  `GOOGLE_MAPS_API_KEY` (`MAP_API`), `GROK_API_KEY`, `CLOUDINARY_API_SECRET`,
  `FIREBASE_SERVICE_ACCOUNT_*`, WhatsApp tokens.
- Firebase service account auto-discovery: env path → `firebase-service-account.json` /
  `secrets/…` / `lipaidox/auth/googleOuth/…`, with strict validation (`type`,
  `private_key`, `client_email`, `project_id`). ADC support via
  `FIREBASE_ALLOW_APPLICATION_DEFAULT_CREDENTIALS`.
- Cloudinary credentials detected by presence of all three; names logged only, never secrets.
- Payment gateway secret (`NBC_API_KEY`) lives only on the server (`settings.py:564-567`).

## 9. Transport & Hardening Flags

- `SecurityMiddleware` present; WhiteNoise serves static.
- **Missing** (recommend for prod): `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`,
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF`,
  `SECURE_BROWSER_XSS_FILTER`, `X_FRAME_OPTIONS` beyond Django defaults.
- `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` = 25 MB (configurable);
  REST upload views enforce per-type caps (≤ 500 MB video).
- Path traversal blocked in `ranged_media_serve` (normalized path must stay under
  `MEDIA_ROOT`; `media_serve.py:39-46`) and DB connections are closed before streaming
  long video responses to avoid exhausting Postgres connections.

## 10. Threat & Mitigation Matrix

| # | Threat | Current state | Mitigation plan |
|---|---|---|---|
| 1 | Forged JWT (default/shared HS256 key) | `JWT_SECRET_KEY` falls back to a non-random default | Require env-supplied random `SECRET_KEY`/`JWT_SECRET_KEY`; fail fast in non-DEBUG |
| 2 | Brute-force login / OTP / social auth | No global throttle | Add per-IP/per-user rate limits on auth + OTP endpoints |
| 3 | Cross-tenant token use | `authenticate_request` ignores tenant | Bind user→tenant in the auth layer (token v user.tenant) or enforce in each resolver |
| 4 | OTP leakage via query-string link / inline OTP | Prefill URL embeds code; `inlineOtp` flags | Keep flags False in prod; drop query-string code from emails |
| 5 | OTP/verification rows exposed unauthenticated | `all_users`, `user_by_id`, `all_email_verifications`, `all_phone_verifications`, `all_password_resets` un-gated | Gate behind auth + role checks; never expose `otp_code`/`token` fields |
| 6 | TOTP secrets at rest (plaintext) | Two tables store secrets plaintext | Encrypt at rest / rotate model (ADR later) |
| 7 | Banned/suspended but JWT-signed earlier | Resolver-level status checks exist but auth entry is partial | Enforce status in `authenticate_request`; re-check role from DB (already done at resolver) |
| 8 | Replay of payment webhook | `fulfill_charge` idempotent + row-locked | Verify webhook signature/secret per gateway (NBC: key-based auth) |
| 9 | Debug backdoors | `DEBUG=True` enables Firebase test tokens | Enforce `DEBUG=False` in any non-local env |
| 10 | Log/proxy exposure of secrets/OTP | Names-only logging; OTP in URLs | Central logging filter; redact `otp`, tokens, keys |

Positive controls already in place: OTPs hashed at rest, attempt caps + supersede/expiry,
anti-enumeration shape for forgot-password, email-verified enforcement on social sign-in,
opaque refresh tokens (SHA-256 only), 2FA confirm/disable requires live codes, tenant-aware
data access, Argon2 default hashing, server-side age gate, and DB constraints on money movement.