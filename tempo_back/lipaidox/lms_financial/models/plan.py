import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class LmsPlan(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    
    interval = models.CharField(max_length=20, choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')], default='monthly')
    features = models.JSONField(default=list) # Array of strings
    
    is_active = models.BooleanField(default=True)
    stripe_price_id = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_plans"
        app_label = "lms_financial"

    def __str__(self):
        return f"{self.name} ({self.price} {self.currency})"
