import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class ScheduledMessage(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='scheduled_messages',
        null=True,
        blank=True
    )
    sender = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='scheduled_messages'
    )
    text = models.TextField()
    scheduled_for = models.DateTimeField()
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messaging_scheduled_messages'
        app_label = 'lipaidox_messaging'
        
    def __str__(self):
        return f"Schedule by {self.sender.username} for {self.scheduled_for}"
