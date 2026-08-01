import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from multitenant.models import Tenant

def get_email_expiry():
    return timezone.now() + timedelta(hours=24)

class EmailVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="email_verifications", null=True, blank=True)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="email_verifications")
    
    email = models.CharField(max_length=255)
    token = models.CharField(max_length=255, unique=True)
    otp_code = models.CharField(max_length=10, blank=True, null=True)
    status = models.CharField(max_length=20, default="pending")
    
    expires_at = models.DateTimeField(default=get_email_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_verifications"
        app_label = "lipaidox_auth"
