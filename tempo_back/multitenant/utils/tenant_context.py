from ..middleware import _thread_locals
from django.core.exceptions import ImproperlyConfigured

class TenantContext:
    @staticmethod
    def get_tenant_object():
        """Retrieve the tenant from thread-local storage."""
        return getattr(_thread_locals, "tenant", None)

def get_current_tenant():
    tenant = TenantContext.get_tenant_object()
    if not tenant:
        raise ImproperlyConfigured(
            "Tenant not found in context. Did you set the X-Tenant-ID header?"
        )
    return tenant
