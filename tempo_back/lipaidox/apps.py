import logging

from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


def _ensure_default_tenant(sender, **kwargs):
    """After `migrate`, a brand-new database still gets the app's tenant."""
    from lipaidox.tenant_setup import ensure_tenant

    try:
        tenant, created = ensure_tenant()
    except Exception:  # e.g. migrating the tenants table away; never block migrate
        logger.warning("Could not ensure default tenant", exc_info=True)
        return
    if created:
        logger.info("Created default tenant %s (%s)", tenant.id, tenant.domain)


class LipaidoxConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lipaidox"

    def ready(self):
        from lipaidox.cache import register_catalog_invalidation

        register_catalog_invalidation()
        post_migrate.connect(_ensure_default_tenant, sender=self)
