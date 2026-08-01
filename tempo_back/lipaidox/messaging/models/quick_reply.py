import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class QuickReply(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='quick_replies'
    )
    title = models.CharField(max_length=40, blank=True, null=True)
    text = models.CharField(max_length=500)
    usage_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messaging_quick_replies'
        app_label = 'lipaidox_messaging'
        ordering = ['-usage_count']

    def __str__(self):
        return f"QuickReply: {self.title or 'Untitled'} by {self.creator.username}"
