import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from multitenant.models import Tenant

def get_reset_expiry():
    return timezone.now() + timedelta(hours=1)

class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="password_resets", null=True, blank=True)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="password_reset_tokens")
    
    token_hash = models.TextField(unique=True)
    status = models.CharField(max_length=20, default="pending")
    
    expires_at = models.DateTimeField(default=get_reset_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_tokens"
        app_label = "lipaidox_auth"
