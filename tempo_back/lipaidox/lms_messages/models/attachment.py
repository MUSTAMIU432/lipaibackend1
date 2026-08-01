import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class MessageAttachment(TenantAwareModel):
    """
    File attachments for LMS messages
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "lipaidox.Tenant",
        on_delete=models.CASCADE,
        related_name="lms_messageattachment_instances"
    )
    
    # Message relationship
    message = models.ForeignKey(
        "Message",
        on_delete=models.CASCADE,
        related_name="attachments"
    )
    
    # File information
    file_url = models.URLField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)  # MIME type
    file_size = models.BigIntegerField()  # Size in bytes
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "lms_message_attachments"
        app_label = "lms_messages"
        indexes = [
            models.Index(fields=['message'], name='idx_attachment_message'),
            models.Index(fields=['-uploaded_at'], name='idx_attachment_uploaded'),
        ]
    
    def __str__(self):
        return f"Attachment: {self.file_name} for message {self.message.id}"
    
    @classmethod
    def create_attachment(cls, message, file_url, file_name, file_type, file_size):
        """Create a new attachment"""
        return cls.objects.create(
            message=message,
            file_url=file_url,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            tenant=message.tenant
        )
