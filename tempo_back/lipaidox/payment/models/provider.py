import uuid
from django.db import models

class MobileMoneyProvider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_name = models.CharField(max_length=100)
    country_name = models.CharField(max_length=100)
    country_code = models.CharField(max_length=10)
    dial_code = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mobile_money_providers"
        app_label = "lipaidox_payment"
        unique_together = ('provider_name', 'country_code')

    def __str__(self):
        return f"{self.provider_name} ({self.country_name})"
