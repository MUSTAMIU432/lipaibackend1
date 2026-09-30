# ADR-001 — GraphQL-first API with a single composed Strawberry schema

- **Status:** Accepted
- **Date:** Architecture phase record (current codebase)

## Context

The backend serves a mobile/Web SPA plus a desktop (Tauri) client and must expose dozens of
feature domains (auth, content, payments, wallet, credits, messaging, LMS, community).
Early work considered a pure REST API and separate per-feature GraphQL servers.

## Decision

Use **one** Strawberry GraphQL endpoint at `/graphql/` as the primary client API. The root
`Query` and `Mutation` (in `lipaidox_backend/schema.py`) multiply inherit from per-module
`...Query`/`...Mutation` classes, so each feature contributes fields without a central
registry. REST is reserved for cases GraphQL is ill-suited to: file/multipart uploads
(`/api/`), payment provider webhooks (`/payments/`), long-lived media streaming (`/media/`),
and the AI-heavy Lost & Found surface (`/`, see ADR-006).

## Consequences

- (+) One endpoint, one schema — easy discovery via GraphiQL and codegen for clients.
- (+) Additive evolution: new fields/modules do not break existing clients.
- (-) Name collisions between modules must be resolved by base-class order (MRO) and are
  easy to get wrong (documented for `my_notifications` and `mark_notification_read`).
- (-) Multipart uploads, file streaming and webhooks need bespoke REST views.
- (-) No formal schema versioning; breaking changes must be additive-only.