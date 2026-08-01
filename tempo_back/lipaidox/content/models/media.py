import uuid
from django.db import models
from .content import Content

class MediaType(models.TextChoices):
    IMAGE = 'image', 'Image'
    VIDEO = 'video', 'Video'
    AUDIO = 'audio', 'Audio'
    THUMBNAIL = 'thumbnail', 'Thumbnail'
    PDF = 'pdf', 'PDF Document'
    ZIP = 'zip', 'ZIP Archive'

class MediaRole(models.TextChoices):
    MAIN = 'main', 'Main Content File'
    THUMBNAIL = 'thumbnail', 'Post Thumbnail'
    PREVIEW = 'preview', 'Video Preview (15s)'
    SLIDESHOW_IMAGE = 'slideshow_image', 'Additional Slideshow Image'

class ContentMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=20, choices=MediaType.choices)
    media_role = models.CharField(max_length=20, choices=MediaRole.choices, default=MediaRole.MAIN)
    
    file_url = models.URLField(max_length=2000)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    resolution = models.CharField(max_length=20, null=True, blank=True)

    thumbnail_url = models.URLField(max_length=2000, null=True, blank=True)

    # Optional adaptive quality renditions: [{"quality": "720p", "url": "..."}]
    renditions = models.JSONField(default=list, blank=True)
    # Optional caption tracks: [{"lang": "en", "label": "English", "url": "...vtt"}]
    captions = models.JSONField(default=list, blank=True)

    # Slideshow Specific (used when role = slideshow_image)
    sort_order = models.IntegerField(default=0)
    slide_topic = models.CharField(max_length=255, null=True, blank=True)
    slide_hint = models.TextField(null=True, blank=True)
    is_preview_slide = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "content_media"
        app_label = "lipaidox_content"
        ordering = ['sort_order', 'created_at']
        unique_together = [
            # Ensure only one main file and one thumbnail via role (conditional logic in Django is harder with UniqueTogether, 
            # but we can enforce it in clean() or just mention it's intended). 
            # Sub-optimal for Postgres 'DEFERRABLE INITIALLY DEFERRED' without custom SQL,
            # but we can do a partial unique index if needed or just handle it in mutation.
        ]
        indexes = [
            models.Index(fields=['media_role']),
            models.Index(fields=['content', 'sort_order']),
        ]

    def get_url_for_user(self, user):
        """
        Returns the appropriate URL (watermarked or original) based on user's purchase/license.
        """
        # If user is the creator, they see original
        if hasattr(user, 'creator_profile') and self.content.creator == user.creator_profile:
            return self.file_url

        from .content_license import ContentLicense
        from .content import ContentAccessType

        # If content is free, they always see watermarked (unless admin, etc)
        is_free = self.content.access_type == ContentAccessType.FREE
        
        has_license = False
        if user.is_authenticated and not is_free:
            has_license = ContentLicense.objects.filter(
                content=self.content, purchaser=user, status='active'
            ).exists()
            
        if is_free or not has_license:
            # Return watermarked url if available
            watermark = self.watermarks.filter(status='applied').first()
            if watermark and watermark.watermarked_file_url:
                return watermark.watermarked_file_url
            # Fallback
            return self.file_url + "?watermark=true"

        # Paid and licensed
        return self.file_url

    def __str__(self):
        return f"{self.media_role} ({self.media_type}) for {self.content.title}"