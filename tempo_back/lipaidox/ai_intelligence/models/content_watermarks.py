import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class WatermarkStatus(models.TextChoices):
    """Status of watermark processing"""
    PENDING = 'pending', 'Pending'
    APPLIED = 'applied', 'Applied'
    FAILED = 'failed', 'Failed'
    SKIPPED = 'skipped', 'Skipped'


class WatermarkPosition(models.TextChoices):
    """Positions for visible watermarks"""
    TOP_LEFT = 'top_left', 'Top Left'
    TOP_RIGHT = 'top_right', 'Top Right'
    BOTTOM_LEFT = 'bottom_left', 'Bottom Left'
    BOTTOM_RIGHT = 'bottom_right', 'Bottom Right'
    CENTER = 'center', 'Center'
    TILED = 'tiled', 'Tiled'


class ContentWatermark(TenantAwareModel):
    """
    Content Watermarks - Module 15
    Tracks watermark application for content protection
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='watermarks'
    )
    media = models.ForeignKey(
        'lipaidox_content.ContentMedia',
        on_delete=models.CASCADE,
        related_name='watermarks'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='watermarks'
    )

    # Watermark Type
    watermark_type = models.CharField(
        max_length=20,
        choices=[
            ('visible', 'Visible'),
            ('invisible', 'Invisible'),
            ('both', 'Both'),
        ],
        default='both'
    )

    # Visible Watermark Settings
    visible_enabled = models.BooleanField(default=True)
    visible_text = models.CharField(max_length=255, blank=True, null=True)
    visible_logo_url = models.TextField(blank=True, null=True)
    visible_position = models.CharField(
        max_length=20,
        choices=WatermarkPosition.choices,
        default=WatermarkPosition.BOTTOM_RIGHT
    )
    visible_opacity = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.70
    )
    visible_font_size = models.IntegerField(default=14)
    visible_color = models.CharField(max_length=20, default='#FFFFFF')
    watermarked_file_url = models.TextField(blank=True, null=True)

    # Invisible Watermark Settings
    invisible_enabled = models.BooleanField(default=True)
    invisible_payload = models.JSONField(default=dict, blank=True)
    invisible_method = models.CharField(max_length=50, default='steganography')

    # Status
    status = models.CharField(
        max_length=20,
        choices=WatermarkStatus.choices,
        default=WatermarkStatus.PENDING
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'content_watermarks'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['content'], name='idx_watermarks_content'),
            models.Index(fields=['creator'], name='idx_watermarks_creator'),
            models.Index(fields=['status'], name='idx_watermarks_status'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['media'],
                name='content_watermarks_media_unique'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(visible_opacity__isnull=True) |
                    (models.Q(visible_opacity__gte=0) & models.Q(visible_opacity__lte=1))
                ),
                name='opacity_check'
            ),
        ]

    def __str__(self):
        return f"Watermark: {self.content.title} - {self.status}"

    def start_processing(self):
        """Mark watermark processing as started"""
        from django.utils import timezone
        self.status = WatermarkStatus.PENDING
        self.save()

    def apply_watermark(self, watermarked_file_url):
        """Mark watermark as applied"""
        from django.utils import timezone
        self.status = WatermarkStatus.APPLIED
        self.watermarked_file_url = watermarked_file_url
        self.applied_at = timezone.now()
        self.save()

    def fail_watermark(self, error_message):
        """Mark watermark processing as failed"""
        from django.utils import timezone
        self.status = WatermarkStatus.FAILED
        self.error_message = error_message
        self.save()

    def skip_watermark(self, reason):
        """Skip watermark processing"""
        from django.utils import timezone
        self.status = WatermarkStatus.SKIPPED
        self.error_message = reason
        self.save()

    def generate_invisible_payload(self):
        """Generate payload for invisible watermark"""
        from django.utils import timezone
        payload = {
            'creator_id': str(self.creator.id),
            'content_id': str(self.content.id),
            'platform': 'payview',
            'timestamp': timezone.now().isoformat()
        }
        self.invisible_payload = payload
        self.save()
        return payload

    def generate_visible_text(self):
        """Generate visible watermark text"""
        if not self.visible_text:
            self.visible_text = f"@{self.creator.user.username} | payview"
            self.save()
        return self.visible_text
