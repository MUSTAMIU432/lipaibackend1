import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class AppealStatus(models.TextChoices):
    SUBMITTED = 'submitted', 'Submitted'
    IN_REVIEW = 'in_review', 'In Review'
    APPROVED = 'approved', 'Approved (Restored)'
    DENIED = 'denied', 'Denied (Permanently Blocked)'

class ContentAppeal(TenantAwareModel):
    """
    Case Management for Creators to claim/bargain for blocked content.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='appeals'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='content_appeals'
    )
    original_report = models.ForeignKey(
        'lipaidox_content.ContentReport',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appeals'
    )
    
    # Appeal Details
    reason = models.TextField(help_text="Creator's bargaining/claim reason")
    evidence_urls = models.JSONField(default=list, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=AppealStatus.choices,
        default=AppealStatus.SUBMITTED
    )
    
    # Case Management / Admin review
    reviewed_by = models.ForeignKey(
        'lipaidox_admin_panel.AdminAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_appeals'
    )
    admin_notes = models.TextField(blank=True, null=True, help_text="Internal notes during case management")
    resolution_reason = models.TextField(blank=True, null=True, help_text="Reason given to creator upon resolution")
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "content_appeals"
        app_label = "lipaidox_content"
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Appeal on {self.content.id} by {self.creator.username}"
