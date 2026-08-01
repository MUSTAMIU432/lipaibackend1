import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class QueueJobStatus(models.TextChoices):
    """Status of queue jobs"""
    QUEUED = 'queued', 'Queued'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    RETRYING = 'retrying', 'Retrying'
    DEAD = 'dead', 'Dead'


class QueueJobType(models.TextChoices):
    """Types of AI processing jobs"""
    FINGERPRINT = 'fingerprint', 'Fingerprint'
    DUPLICATE_CHECK = 'duplicate_check', 'Duplicate Check'
    WATERMARK = 'watermark', 'Watermark'
    REVERSE_SEARCH = 'reverse_search', 'Reverse Search'
    PRICE_BENCHMARK = 'price_benchmark', 'Price Benchmark'
    FULL_PIPELINE = 'full_pipeline', 'Full Pipeline'


class AIScanQueue(TenantAwareModel):
    """
    AI Scan Queue - Module 15
    Background job queue for processing uploaded media through AI pipeline
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='scan_queue_jobs'
    )
    media = models.ForeignKey(
        'lipaidox_content.ContentMedia',
        on_delete=models.CASCADE,
        related_name='scan_queue_jobs'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='scan_queue_jobs'
    )

    job_type = models.CharField(
        max_length=20,
        choices=QueueJobType.choices,
        default=QueueJobType.FULL_PIPELINE
    )
    status = models.CharField(
        max_length=20,
        choices=QueueJobStatus.choices,
        default=QueueJobStatus.QUEUED
    )
    priority = models.IntegerField(default=5)  # 1-10, higher = more priority
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_scan_queue'
        app_label = 'lipaidox_ai_intelligence'
        ordering = ['-priority', 'queued_at']
        indexes = [
            models.Index(fields=['status'], name='idx_ai_scan_queue_status'),
            models.Index(fields=['job_type'], name='idx_ai_scan_queue_job_type'),
            models.Index(fields=['-priority'], name='idx_ai_scan_queue_priority'),
            models.Index(fields=['queued_at'], name='idx_ai_scan_queue_queued_at'),
            models.Index(fields=['next_retry_at'], name='idx_ai_scan_queue_next_retry'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(priority__range=(1, 10)),
                name='priority_check'
            ),
            models.CheckConstraint(
                check=models.Q(attempts__gte=0),
                name='attempts_check'
            ),
        ]

    def __str__(self):
        return f"Queue Job: {self.job_type} - {self.content.title} ({self.status})"

    def start_processing(self):
        """Mark job as processing"""
        from django.utils import timezone
        self.status = QueueJobStatus.PROCESSING
        self.started_at = timezone.now()
        self.save()

    def complete_job(self):
        """Mark job as completed"""
        from django.utils import timezone
        self.status = QueueJobStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save()

    def fail_job(self, error_message):
        """Mark job as failed and schedule retry if possible"""
        from django.utils import timezone
        import datetime
        
        self.attempts += 1
        self.error_message = error_message
        
        if self.attempts >= self.max_attempts:
            self.status = QueueJobStatus.DEAD
            self.completed_at = timezone.now()
        else:
            self.status = QueueJobStatus.RETRYING
            # Exponential backoff: 5min, 15min, 45min
            retry_delay = datetime.timedelta(minutes=5 * (3 ** (self.attempts - 1)))
            self.next_retry_at = timezone.now() + retry_delay
        
        self.save()

    def retry_job(self):
        """Retry a failed job"""
        from django.utils import timezone
        self.status = QueueJobStatus.QUEUED
        self.started_at = None
        self.next_retry_at = None
        self.save()

    def can_retry(self):
        """Check if job can be retried"""
        return (
            self.status == QueueJobStatus.RETRYING and
            self.attempts < self.max_attempts and
            self.next_retry_at and
            self.next_retry_at <= timezone.now()
        )

    @classmethod
    def get_pending_jobs(cls, job_type=None):
        """Get pending jobs ready for processing"""
        from django.utils import timezone
        
        queryset = cls.objects.filter(
            status=QueueJobStatus.QUEUED
        )
        
        if job_type:
            queryset = queryset.filter(job_type=job_type)
        
        return queryset.order_by('-priority', 'queued_at')

    @classmethod
    def get_retry_jobs(cls):
        """Get jobs ready for retry"""
        from django.utils import timezone
        
        return cls.objects.filter(
            status=QueueJobStatus.RETRYING,
            next_retry_at__lte=timezone.now()
        ).order_by('-priority', 'next_retry_at')

    @classmethod
    def get_next_job(cls, job_type=None):
        """Get the next job to process"""
        from django.utils import timezone
        
        # First check for retry jobs
        retry_job = cls.get_retry_jobs().first()
        if retry_job:
            return retry_job
        
        # Then get pending jobs
        return cls.get_pending_jobs(job_type).first()

    def set_high_priority(self):
        """Set job to high priority"""
        self.priority = 9
        self.save()

    def set_low_priority(self):
        """Set job to low priority"""
        self.priority = 2
        self.save()
