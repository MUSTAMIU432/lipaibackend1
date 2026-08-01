from django.db import models
from multitenant.models import Tenant as CoreTenant

Tenant = CoreTenant


class RecommendationTenantAwareModel(models.Model):
    """Custom TenantAwareModel for Recommendation module to avoid conflicts"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_rec_instances", null=True, blank=True)

    class Meta:
        abstract = True
