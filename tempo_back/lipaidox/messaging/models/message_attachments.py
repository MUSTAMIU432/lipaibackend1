import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class AttachmentMediaType(models.TextChoices):
    """Attachment media types"""
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'
    AUDIO = 'audio', 'Audio'
    DOCUMENT = 'document', 'Document'
    ARCHIVE = 'archive', 'Archive'


class MessageAttachment(TenantAwareModel):
    """
    Message Attachments - Module 20
    File attachments for messages
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    media_type = models.CharField(
        max_length=10,
        choices=AttachmentMediaType.choices
    )
    file_url = models.TextField()
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    thumbnail_url = models.TextField(null=True, blank=True)
    is_expired = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_attachments'
        app_label = 'lipaidox_messaging'
        indexes = [
            models.Index(fields=['message'], name='idx_msg_attachments_message'),
            models.Index(fields=['conversation'], name='idx_msg_attachments_conv'),
            models.Index(fields=['media_type'], name='idx_msg_attachments_media'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(file_size_bytes__isnull=True) | models.Q(file_size_bytes__gt=0),
                name='file_size_check'
            ),
        ]

    def __str__(self):
        return f"Attachment: {self.file_name or 'Unknown'} for message {self.message.id}"

    def is_image(self):
        """Check if attachment is an image"""
        return self.media_type == AttachmentMediaType.IMAGE

    def is_video(self):
        """Check if attachment is a video"""
        return self.media_type == AttachmentMediaType.VIDEO

    def is_audio(self):
        """Check if attachment is audio"""
        return self.media_type == AttachmentMediaType.AUDIO

    def is_document(self):
        """Check if attachment is a document"""
        return self.media_type == AttachmentMediaType.DOCUMENT

    def is_archive(self):
        """Check if attachment is an archive"""
        return self.media_type == AttachmentMediaType.ARCHIVE

    def get_display_size(self):
        """Get human-readable file size"""
        if not self.file_size_bytes:
            return "Unknown size"
        
        if self.file_size_bytes < 1024:
            return f"{self.file_size_bytes} B"
        elif self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.1f} KB"
        elif self.file_size_bytes < 1024 * 1024 * 1024:
            return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def mark_expired(self):
        """Mark attachment as expired"""
        from django.utils import timezone
        
        self.is_expired = True
        self.expires_at = timezone.now()
        self.save()

    @classmethod
    def create_attachment(cls, message, conversation, media_type, file_url, **kwargs):
        """Create a new attachment"""
        return cls.objects.create(
            message=message,
            tenant=message.tenant,
            conversation=conversation,
            media_type=media_type,
            file_url=file_url,
            **kwargs
        )

    @classmethod
    def get_message_attachments(cls, message):
        """Get all attachments for a message"""
        return cls.objects.filter(message=message).order_by('created_at')

    @classmethod
    def get_conversation_attachments(cls, conversation, media_type=None):
        """Get all attachments for a conversation"""
        queryset = cls.objects.filter(conversation=conversation)
        
        if media_type:
            queryset = queryset.filter(media_type=media_type)
        
        return queryset.order_by('-created_at')

    @classmethod
    def cleanup_expired_attachments(cls):
        """Clean up expired attachments"""
        from django.utils import timezone
        
        return cls.objects.filter(
            is_expired=True,
            expires_at__lte=timezone.now()
        ).delete()[0]
