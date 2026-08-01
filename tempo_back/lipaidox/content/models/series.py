import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class ContentSeries(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="series")
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    thumbnail_url = models.URLField(max_length=1000, null=True, blank=True)
    episode_count = models.IntegerField(default=0)
    is_complete = models.BooleanField(default=False)
    
    # Nested Hierarchy Support
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='sub_series'
    )
    sort_order = models.IntegerField(default=0)
    series_type = models.CharField(
        max_length=20, 
        choices=[
            ('collection', 'Collection/Course'),
            ('chapter', 'Chapter'),
            ('sub_topic', 'Sub-Topic')
        ],
        default='collection'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "content_series"
        app_label = "lipaidox_content"
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['creator']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f"{self.title} by {self.creator}"