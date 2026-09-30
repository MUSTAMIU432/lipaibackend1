# ADR-005 — Header/host-based multi-tenancy with TenantAwareModel

- **Status:** Accepted

## Context

Lipaidox serves multiple tenants (organizations/domains) from one deployment. Tenant data
must be isolated per request without running separate databases.

## Decision

- `Tenant` model (UUID PK, unique indexed `domain`) is the tenancy root
  (`lipaidox/models.py`).
- `multitenant.middleware.TenantMiddleware` resolves the tenant from the `X-Tenant-ID`
  header first, then falls back to a `Tenant.domain` host match; it sets `request.tenant`
  and a thread-local (`get_current_tenant`).
- `multitenant.models.TenantAwareModel` spreads a nullable `tenant` FK
  (`related_name="%(class)s_instances"`) on tenant-scoped tables.

## Consequences

- (+) Shared schema, low ops overhead; tenant known at request start.
- (+) Nullable FK keeps legacy/global rows simple.
- (-) Tom enforcement is per-resolver — queries must scope by tenant or data leaks across
  tenants (risk; `authenticate_request` does not bind user→tenant).
- (-) Some modules (lost_found, several LMS tables) are **not** tenant-aware — an accepted
  exception that must be revisited.
- (-) `X-Tenant-ID` is trust-on-wire; binding and validation belong in the auth layer.