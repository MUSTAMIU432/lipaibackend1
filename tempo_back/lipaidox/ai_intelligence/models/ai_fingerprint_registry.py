import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class AIFingerprintRegistry(TenantAwareModel):
    """
    Registry for content fingerprints.
    Persists even if the original content is deleted to track true ownership.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.SET_NULL,
        null=True,
        related_name='registered_fingerprints'
    )
    
    # Fingerprints
    sha256_hash = models.CharField(max_length=64, unique=True)
    phash_hash = models.CharField(max_length=64, blank=True, null=True)
    
    # Metadata
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_fingerprint_registry'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['sha256_hash']),
            models.Index(fields=['phash_hash']),
        ]

    def __str__(self):
        return f"Fingerprint Registry ({self.sha256_hash})"
