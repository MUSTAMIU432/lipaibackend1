# ADR-003 — Custom User model + PyJWT bearer authentication

- **Status:** Accepted

## Context

Auth spans three roles (`fan`/`creator`/`admin`), per-tenant uniqueness, social sign-in
(Google/Firebase), 2FA, and stateless API requests. Django's stock `User` lacks tenant and
role fields; SimpleJWT brought unneeded DB-backed behavior for the GraphQL path.

## Decision

- Custom `User(AbstractUser)` with **UUID PK**, `tenant` FK, `role`, `status`,
  `auth_provider`, `google_id`/`apple_id`, and per-tenant partial-unique constraints on
  phone/google/apple (`lipaidox/auth/models/user.py`).
- GraphQL auth uses **PyJWT directly** (`lipaidox/auth/jwt_auth.py`): HS256 access tokens
  (1h) carrying `user_id`/`role`/`tenant_id`; opaque refresh tokens stored only as SHA-256;
  `JWTGraphQLView` authenticates `request.user` before resolvers run.

## Consequences

- (+) Full control over claims and token lifecycle; no heavy dependency for GraphQL.
- (+) Resolver-level RBAC reads role from the DB, so role flips are instant (ADR/RBAC).
- (-) Two JWT implementations coexist (DRF REST uses SimpleJWT) — harmonize later.
- (-) Stateless access tokens are unrevocable; revocation is refresh-token level.
- (-) HS256 requires strong `SECRET_KEY`/`JWT_SECRET_KEY` management (see `docs/SECURITY.md` §4).