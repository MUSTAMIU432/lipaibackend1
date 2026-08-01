import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class RoleName(models.TextChoices):
    VIEWER = 'viewer', 'Viewer'
    STUDENT = 'student', 'Student'
    CREATOR = 'creator', 'Creator'
    INSTRUCTOR = 'instructor', 'Instructor'

class ProductDomain(models.TextChoices):
    PREMIUM_CONTENT = 'premium_content', 'Premium Content'
    ELEARNING = 'elearning', 'E-Learning'

class RoleStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    SUSPENDED = 'suspended', 'Suspended'

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=RoleName.choices, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_roles"
        app_label = "lms_identity"

class UserRole(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lms_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    domain = models.CharField(max_length=50, choices=ProductDomain.choices, default=ProductDomain.ELEARNING)
    status = models.CharField(max_length=20, choices=RoleStatus.choices, default=RoleStatus.ACTIVE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "lms_user_roles"
        app_label = "lms_identity"
        unique_together = ('user', 'role', 'domain')
