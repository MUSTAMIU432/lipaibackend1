import threading
from lipaidox.models import Tenant

_thread_locals = threading.local()

def get_current_tenant():
    return getattr(_thread_locals, "tenant", None)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = None
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id, is_active=True)
            except (Tenant.DoesNotExist, ValueError):
                pass
        
        if not tenant:
            host = request.get_host().split(":")[0]
            try:
                tenant = Tenant.objects.get(domain=host, is_active=True)
            except Tenant.DoesNotExist:
                pass
                
        request.tenant = tenant
        _thread_locals.tenant = tenant
        response = self.get_response(request)
        if hasattr(_thread_locals, "tenant"):
            del _thread_locals.tenant
        return response
