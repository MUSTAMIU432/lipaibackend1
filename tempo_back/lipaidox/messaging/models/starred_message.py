import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class StarredMessage(TenantAwareModel):
    """A user's own star on a direct message.

    Mirrors WhatsApp's star: it's per-viewer, not a shared/broadcast reaction —
    starring a message doesn't notify or change anything for the other side of
    the conversation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='stars'
    )
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='starred_messages'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'starred_messages'
        app_label = 'lipaidox_messaging'
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['user'], name='idx_starred_messages_user'),
        ]
