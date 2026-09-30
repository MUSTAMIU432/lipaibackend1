# Architecture Decision Records (ADR)

Each ADR below captures a significant architectural decision for the Lipaidox backend.
Use the `YYYY-MM-DD` counter only for future additions; existing records keep their number
for stable cross-referencing.

| # | Title | Status |
|---|---|---|
| 001 | [GraphQL-first API with a single composed Strawberry schema](001-graphql-first-strawberry-schema.md) | Accepted |
| 002 | [Per-module package layout convention](002-module-layout-convention.md) | Accepted |
| 003 | [Custom User model + PyJWT bearer authentication](003-custom-user-and-pyjwt-auth.md) | Accepted |
| 004 | [Wallet choke point — top-up-then-spend money movement](004-wallet-choke-point.md) | Accepted |
| 005 | [Header/host-based multi-tenancy with TenantAwareModel](005-multi-tenancy.md) | Accepted |
| 006 | [Lost & Found exposed as REST with graceful AI fallbacks](006-lost-found-rest-and-ai-fallbacks.md) | Accepted |
| 007 | [Schema-isolated PostgreSQL test runner](007-schema-isolated-test-runner.md) | Accepted |
| 008 | [Off-box media storage and Range-aware serving](008-media-storage-and-range-serving.md) | Accepted |
| 009 | [Framework-independent password-reset package](009-framework-independent-password-reset.md) | Accepted |
| 010 | [Argon2id-first password hashing with PBKDF2 fallback](010-argon2id-password-hashing.md) | Accepted |