import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class MessageReaction(TenantAwareModel):
    """Emoji reactions on a direct message."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='message_reactions'
    )
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_reactions'
        app_label = 'lipaidox_messaging'
        unique_together = ('message', 'user', 'emoji')
        indexes = [
            models.Index(fields=['message'], name='idx_msg_reactions_message'),
        ]
