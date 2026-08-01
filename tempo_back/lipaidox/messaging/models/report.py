import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ConversationReport(TenantAwareModel):
    """A report filed against a conversation (spam / abuse)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='reports'
    )
    reporter = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='filed_conversation_reports'
    )
    category = models.CharField(max_length=40, default='spam')   # spam|abuse|other
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conversation_reports'
        app_label = 'lipaidox_messaging'
