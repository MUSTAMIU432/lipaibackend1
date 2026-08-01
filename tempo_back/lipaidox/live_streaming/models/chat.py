import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ChatMessageStatus(models.TextChoices):
    """Status of chat messages"""
    VISIBLE = 'visible', 'Visible'
    DELETED = 'deleted', 'Deleted'
    FLAGGED = 'flagged', 'Flagged'
    AUTO_MODERATED = 'auto_moderated', 'Auto Moderated'


class LiveStreamChatMessage(TenantAwareModel):
    """
    Every message sent in the live stream chat
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        'lipaidox_live_streaming.LiveStream',
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='live_stream_chat_messages'
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ChatMessageStatus.choices,
        default=ChatMessageStatus.VISIBLE
    )
    is_pinned = models.BooleanField(default=False)
    is_creator_message = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_chat_messages'
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'live_stream_chat_messages'
        app_label = 'lipaidox_live_streaming'
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['live_stream'], name='idx_chat_stream'),
            models.Index(fields=['fan'], name='idx_chat_fan'),
            models.Index(fields=['status'], name='idx_chat_status'),
            models.Index(fields=['sent_at'], name='idx_chat_sent'),
        ]
        constraints = [
        ]

    def __str__(self):
        return f"Chat: {self.fan.username} in {self.live_stream.title}"

    def delete_message(self, deleted_by_user):
        """Delete a chat message"""
        from django.utils import timezone
        self.status = ChatMessageStatus.DELETED
        self.deleted_by = deleted_by_user
        self.deleted_at = timezone.now()
        self.save()

    def pin_message(self):
        """Pin a chat message"""
        self.is_pinned = True
        self.save()

    def unpin_message(self):
        """Unpin a chat message"""
        self.is_pinned = False
        self.save()
