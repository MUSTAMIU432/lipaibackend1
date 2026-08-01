import uuid
from django.db import models
from .content import Content

class AttachmentType(models.TextChoices):
    PDF = 'pdf', 'PDF'
    ZIP = 'zip', 'ZIP'
    RAR = 'rar', 'RAR'
    VIDEO = 'video', 'Video'
    OTHER = 'other', 'Other'

class ContentAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="attachments")
    attachment_type = models.CharField(max_length=20, choices=AttachmentType.choices)
    file_url = models.URLField(max_length=2000)
    file_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    thumbnail_url = models.URLField(max_length=2000, null=True, blank=True)
    download_count = models.IntegerField(default=0)

    # Optional adaptive quality renditions: [{"quality": "720p", "url": "..."}]
    renditions = models.JSONField(default=list, blank=True)
    # Optional caption tracks: [{"lang": "en", "label": "English", "url": "...vtt"}]
    captions = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_attachments"
        app_label = "lipaidox_content"

    def __str__(self):
        return f"{self.file_name} ({self.attachment_type})"
