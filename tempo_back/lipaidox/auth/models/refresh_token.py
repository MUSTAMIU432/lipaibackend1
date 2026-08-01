import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from multitenant.models import Tenant

def get_refresh_expiry():
    return timezone.now() + timedelta(days=30)

class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="refresh_tokens", null=True, blank=True)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="refresh_tokens")
    
    token_hash = models.TextField(unique=True)
    status = models.CharField(max_length=20, default="active")
    
    device_name = models.CharField(max_length=255, blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(default=get_refresh_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"
        app_label = "lipaidox_auth"
