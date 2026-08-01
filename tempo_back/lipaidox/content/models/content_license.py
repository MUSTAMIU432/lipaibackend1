import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class LicenseStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    REVOKED = 'revoked', 'Revoked'
    EXPIRED = 'expired', 'Expired'

class ContentLicense(TenantAwareModel):
    """
    License granted to a user who purchased content.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='issued_licenses'
    )
    purchaser = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='content_licenses'
    )
    
    license_key = models.CharField(max_length=255, unique=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=LicenseStatus.choices,
        default=LicenseStatus.ACTIVE
    )
    
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'content_licenses'
        app_label = 'lipaidox_content'
        
    def save(self, *args, **kwargs):
        if not self.license_key:
            self.license_key = f"LPDX-{self.content.id.hex[:8]}-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"License {self.license_key} for {self.purchaser.username}"
