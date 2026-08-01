import uuid
from django.db import models
from .content import Content

class ContentAccessRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.OneToOneField(Content, on_delete=models.CASCADE, related_name="access_rules")
    
    # Restrictions
    geo_restrictions = models.JSONField(default=list, blank=True) # or ArrayField for Postgres
    subscriber_only_preview = models.BooleanField(default=False)

    # Previews
    preview_duration_seconds = models.IntegerField(null=True, blank=True)
    preview_slide_count = models.IntegerField(null=True, blank=True)

    # Rules
    allow_download = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "content_access_rules"
        app_label = "lipaidox_content"

    def __str__(self):
        return f"Access Rules for {self.content.title}"
