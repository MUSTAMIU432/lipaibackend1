"""Make sure the app's tenant row exists.

A fresh database has no tenant, so every request fails with "Tenant not found in
context". The mobile app sends a fixed `X-Tenant-ID` (its `EXPO_PUBLIC_TENANT_ID`);
this creates that tenant. Configure with environment variables:

    DEFAULT_TENANT_ID      UUID the app sends          (default: the production app's)
    DEFAULT_TENANT_NAME    display name                (default: Lipaidox)
    DEFAULT_TENANT_DOMAIN  unique domain of the tenant (default: backlipaidox.eopsprimax.com)
"""
import os
import uuid

DEFAULT_ID = "2328123c-621f-4a73-a5fc-8b8a5ebcb39f"
DEFAULT_NAME = "Lipaidox"
DEFAULT_DOMAIN = "backlipaidox.eopsprimax.com"


def configured_tenant():
    return {
        "id": uuid.UUID(os.environ.get("DEFAULT_TENANT_ID", "").strip() or DEFAULT_ID),
        "name": os.environ.get("DEFAULT_TENANT_NAME", "").strip() or DEFAULT_NAME,
        "domain": os.environ.get("DEFAULT_TENANT_DOMAIN", "").strip() or DEFAULT_DOMAIN,
    }


def ensure_tenant():
    """Create the configured tenant if missing. Returns (tenant, created)."""
    from lipaidox.models import Tenant

    cfg = configured_tenant()
    tenant = Tenant.objects.filter(id=cfg["id"]).first()
    if tenant:
        if not tenant.is_active:
            tenant.is_active = True
            tenant.save(update_fields=["is_active", "updated_at"])
        return tenant, False
    # `domain` is unique: a different tenant already owning it must not be hijacked.
    if Tenant.objects.filter(domain=cfg["domain"]).exists():
        cfg["domain"] = f"{cfg['id']}.{cfg['domain']}"
    return Tenant.objects.create(**cfg), True
