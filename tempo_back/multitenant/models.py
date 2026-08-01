from django.db import models
from lipaidox.models import Tenant as CoreTenant

Tenant = CoreTenant

class TenantAwareModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_instances", null=True, blank=True)

    class Meta:
        abstract = True
