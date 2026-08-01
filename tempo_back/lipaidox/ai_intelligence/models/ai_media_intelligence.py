import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class AIScanStatus(models.TextChoices):
    """Status of AI scan operations"""
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    SKIPPED = 'skipped', 'Skipped'


class AIDuplicateAction(models.TextChoices):
    """Actions for duplicate content detection"""
    NONE = 'none', 'None'
    FLAGGED = 'flagged', 'Flagged'
    BLOCKED = 'blocked', 'Blocked'
    WARNING_ISSUED = 'warning_issued', 'Warning Issued'
    ADMIN_REVIEW = 'admin_review', 'Admin Review'


class WatermarkType(models.TextChoices):
    """Types of watermarks"""
    VISIBLE = 'visible', 'Visible'
    INVISIBLE = 'invisible', 'Invisible'
    BOTH = 'both', 'Both'


class FingerprintMethod(models.TextChoices):
    """Methods for content fingerprinting"""
    SHA256 = 'sha256', 'SHA-256'
    PHASH = 'phash', 'pHash'
    DHASH = 'dhash', 'dHash'
    COMBINED = 'combined', 'Combined'


class ReverseScanStatus(models.TextChoices):
    """Status of reverse image search"""
    NOT_SCANNED = 'not_scanned', 'Not Scanned'
    SCANNING = 'scanning', 'Scanning'
    CLEAN = 'clean', 'Clean'
    MATCHES_FOUND = 'matches_found', 'Matches Found'
    FAILED = 'failed', 'Failed'


class AIMediaIntelligence(TenantAwareModel):
    """
    AI Media Intelligence - Module 15
    Stores all AI analysis results for media content
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='ai_intelligence'
    )
    media = models.ForeignKey(
        'lipaidox_content.ContentMedia',
        on_delete=models.CASCADE,
        related_name='ai_intelligence'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='ai_intelligence'
    )

    # Fingerprinting
    fingerprint_method = models.CharField(
        max_length=20,
        choices=FingerprintMethod.choices,
        default=FingerprintMethod.COMBINED
    )
    sha256_hash = models.CharField(max_length=64, blank=True, null=True)
    phash_hash = models.CharField(max_length=64, blank=True, null=True)
    dhash_hash = models.CharField(max_length=64, blank=True, null=True)
    combined_fingerprint = models.TextField(blank=True, null=True)
    fingerprint_generated_at = models.DateTimeField(null=True, blank=True)

    # Duplicate Detection
    is_duplicate = models.BooleanField(default=False)
    duplicate_of_content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates'
    )
    duplicate_of_media = models.ForeignKey(
        'lipaidox_content.ContentMedia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates'
    )
    duplicate_similarity_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True
    )
    duplicate_action = models.CharField(
        max_length=20,
        choices=AIDuplicateAction.choices,
        default=AIDuplicateAction.NONE
    )
    duplicate_detected_at = models.DateTimeField(null=True, blank=True)

    # Reverse Image Search
    reverse_scan_status = models.CharField(
        max_length=20,
        choices=ReverseScanStatus.choices,
        default=ReverseScanStatus.NOT_SCANNED
    )
    reverse_scan_matches_count = models.IntegerField(default=0)
    reverse_scan_results = models.JSONField(default=dict, blank=True)
    reverse_scanned_at = models.DateTimeField(null=True, blank=True)

    # Authenticity
    authenticity_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True
    )
    authenticity_note = models.TextField(blank=True, null=True)

    # Price Benchmark
    price_benchmark_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    price_benchmark_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    price_benchmark_avg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    price_benchmark_currency = models.CharField(max_length=10, default='USD')
    price_benchmarked_at = models.DateTimeField(null=True, blank=True)

    # Overall Scan Status
    scan_status = models.CharField(
        max_length=20,
        choices=AIScanStatus.choices,
        default=AIScanStatus.PENDING
    )
    scan_started_at = models.DateTimeField(null=True, blank=True)
    scan_completed_at = models.DateTimeField(null=True, blank=True)
    scan_error = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_media_intelligence'
        app_label = 'lipaidox_ai_intelligence'
        indexes = [
            models.Index(fields=['content'], name='idx_ai_intelligence_content'),
            models.Index(fields=['creator'], name='idx_ai_intelligence_creator'),
            models.Index(fields=['sha256_hash'], name='idx_ai_intelligence_sha256'),
            models.Index(fields=['phash_hash'], name='idx_ai_intelligence_phash'),
            models.Index(fields=['dhash_hash'], name='idx_ai_intelligence_dhash'),
            models.Index(fields=['is_duplicate'], name='idx_ai_intel_duplicate'),
            models.Index(fields=['scan_status'], name='idx_ai_intel_scan_status'),
            models.Index(fields=['duplicate_action'], name='idx_ai_intel_dup_action'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['media'],
                name='ai_media_intelligence_media_unique'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(duplicate_similarity_score__isnull=True) |
                    (models.Q(duplicate_similarity_score__gte=0) & models.Q(duplicate_similarity_score__lte=1))
                ),
                name='similarity_score_check'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(authenticity_score__isnull=True) |
                    (models.Q(authenticity_score__gte=0) & models.Q(authenticity_score__lte=1))
                ),
                name='authenticity_score_check'
            ),
            models.CheckConstraint(
                check=models.Q(reverse_scan_matches_count__gte=0),
                name='reverse_scan_matches_check'
            ),
        ]

    def __str__(self):
        return f"AI Intelligence: {self.content.title} - {self.scan_status}"

    def start_scan(self):
        """Start the AI scan process"""
        from django.utils import timezone
        self.scan_status = AIScanStatus.PROCESSING
        self.scan_started_at = timezone.now()
        self.save()

    def complete_scan(self):
        """Mark scan as completed"""
        from django.utils import timezone
        self.scan_status = AIScanStatus.COMPLETED
        self.scan_completed_at = timezone.now()
        self.save()

    def fail_scan(self, error_message):
        """Mark scan as failed"""
        from django.utils import timezone
        self.scan_status = AIScanStatus.FAILED
        self.scan_error = error_message
        self.scan_completed_at = timezone.now()
        self.save()

    def mark_duplicate(self, duplicate_content, duplicate_media, similarity_score, action):
        """Mark content as duplicate"""
        from django.utils import timezone
        self.is_duplicate = True
        self.duplicate_of_content = duplicate_content
        self.duplicate_of_media = duplicate_media
        self.duplicate_similarity_score = similarity_score
        self.duplicate_action = action
        self.duplicate_detected_at = timezone.now()
        self.save()

    def update_reverse_scan(self, status, matches_count=0, results=None):
        """Update reverse image scan results"""
        from django.utils import timezone
        self.reverse_scan_status = status
        self.reverse_scan_matches_count = matches_count
        if results:
            self.reverse_scan_results = results
        if status in [ReverseScanStatus.CLEAN, ReverseScanStatus.MATCHES_FOUND, ReverseScanStatus.FAILED]:
            self.reverse_scanned_at = timezone.now()
        self.save()

    def set_price_benchmark(self, min_price, max_price, avg_price):
        """Set price benchmark analysis"""
        from django.utils import timezone
        self.price_benchmark_min = min_price
        self.price_benchmark_max = max_price
        self.price_benchmark_avg = avg_price
        self.price_benchmarked_at = timezone.now()
        self.save()
