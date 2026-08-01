import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from multitenant.models import Tenant

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="users", null=True, blank=True)
    
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    phone_country_code = models.CharField(max_length=10, blank=True, null=True)
    role = models.CharField(max_length=20, default="fan")
    status = models.CharField(max_length=20, default="pending")
    
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(blank=True, null=True)
    
    # Social Sign in
    auth_provider = models.CharField(max_length=20, default="local")
    google_id = models.CharField(max_length=255, blank=True, null=True)
    apple_id = models.CharField(max_length=255, blank=True, null=True)

    # Staff / workspace context
    module = models.CharField(max_length=50, blank=True, null=True)
    profile_title = models.CharField(max_length=255, blank=True, null=True)
    staff_capabilities = models.JSONField(default=list, blank=True)
    is_first_login = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        app_label = "lipaidox_auth"
        constraints = [
            models.UniqueConstraint(
                fields=["phone_number", "tenant"],
                name="unique_phone_per_tenant",
                condition=models.Q(phone_number__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["google_id", "tenant"],
                name="unique_google_per_tenant",
                condition=models.Q(google_id__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["apple_id", "tenant"],
                name="unique_apple_per_tenant",
                condition=models.Q(apple_id__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.username} [{self.role}]"
