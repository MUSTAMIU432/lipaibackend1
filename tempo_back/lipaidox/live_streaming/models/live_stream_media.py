import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class MediaType(models.TextChoices):
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'
    AUDIO = 'audio', 'Audio'
    PDF   = 'pdf',   'PDF'


class LiveStreamMedia(TenantAwareModel):
    """
    Files uploaded by the host for sharing during a live stream session.
    Scoped to one stream — not reused across sessions.
    Max 10 MB enforced at the API layer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    live_stream = models.ForeignKey(
        'lipaidox_live_streaming.LiveStream',
        on_delete=models.CASCADE,
        related_name='media_files',
    )
    uploaded_by = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='live_stream_media_uploads',
    )
    name       = models.CharField(max_length=255)
    file_url   = models.TextField()
    mime_type  = models.CharField(max_length=100)
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    size_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'live_stream_media'
        app_label = 'lipaidox_live_streaming'
        ordering  = ['created_at']
        indexes   = [
            models.Index(fields=['live_stream'], name='idx_lsmedia_stream'),
            models.Index(fields=['media_type'],  name='idx_lsmedia_type'),
        ]

    def __str__(self):
        return f"{self.media_type}: {self.name} in {self.live_stream_id}"
