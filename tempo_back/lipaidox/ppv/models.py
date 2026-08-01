import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class PPVAccessType(models.TextChoices):
    """Access types for PPV content"""
    ONE_TIME = 'one_time', 'One Time'
    TIMED = 'timed', 'Timed'


class PPVPurchaseStatus(models.TextChoices):
    """Status of PPV purchases"""
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'
    EXPIRED = 'expired', 'Expired'


class PPVPurchase(TenantAwareModel):
    """
    Pay Per View purchases - Module 11
    Tracks fan purchases of PPV content with pricing and access control
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # References
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='ppv_purchases'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='ppv_sales'
    )
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='ppv_purchases'
    )

    # Access Type
    access_type = models.CharField(
        max_length=20,
        choices=PPVAccessType.choices,
        default=PPVAccessType.ONE_TIME
    )

    # Pricing
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    status = models.CharField(
        max_length=20,
        choices=PPVPurchaseStatus.choices,
        default=PPVPurchaseStatus.PENDING
    )

    # Access Window
    access_granted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_expired = models.BooleanField(default=False)

    # Download
    allow_download = models.BooleanField(default=False)
    download_count = models.IntegerField(default=0)

    # Payment
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    gateway_reference = models.CharField(max_length=255, blank=True, null=True)

    # Refund
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(blank=True, null=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Timestamps
    purchased_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ppv_purchases'
        app_label = 'lipaidox_ppv'
        indexes = [
            models.Index(fields=['fan'], name='idx_ppv_fan'),
            models.Index(fields=['creator'], name='idx_ppv_creator'),
            models.Index(fields=['content'], name='idx_ppv_content'),
            models.Index(fields=['status'], name='idx_ppv_status'),
            models.Index(fields=['expires_at'], name='idx_ppv_expires'),
            models.Index(fields=['purchased_at'], name='idx_ppv_purchased'),
        ]
        constraints = [
            # A fan can only purchase the same content once
            models.UniqueConstraint(
                fields=['fan', 'content'],
                name='ppv_purchases_unique'
            ),
            models.CheckConstraint(check=models.Q(amount_paid__gt=0), name='ppv_amount_paid_check'),
            models.CheckConstraint(check=models.Q(platform_fee__gte=0), name='ppv_platform_fee_check'),
            models.CheckConstraint(check=models.Q(net_amount__gte=0), name='ppv_net_amount_check'),
            models.CheckConstraint(
                check=models.Q(net_amount=models.F('amount_paid') - models.F('platform_fee')),
                name='ppv_net_amount_calc'
            ),
            models.CheckConstraint(check=models.Q(download_count__gte=0), name='ppv_download_count_check'),
            models.CheckConstraint(
                check=models.Q(refund_amount__isnull=True) | models.Q(refund_amount__gt=0, refund_amount__lte=models.F('amount_paid')),
                name='ppv_refund_amount_check'
            ),
            models.CheckConstraint(
                check=~models.Q(access_type=PPVAccessType.TIMED) | models.Q(expires_at__isnull=False),
                name='ppv_timed_expiry_check'
            ),
        ]

    def __str__(self):
        return f"PPV Purchase: {self.fan.username} - {self.content.id} - {self.status}"

    @property
    def has_access(self):
        """Check if fan currently has access to content"""
        if self.status != PPVPurchaseStatus.COMPLETED:
            return False
        if self.is_expired:
            return False
        if self.access_type == PPVAccessType.TIMED and self.expires_at:
            from django.utils import timezone
            if timezone.now() > self.expires_at:
                return False
        return True

    def calculate_fees(self):
        """Calculate platform fee and net amount"""
        self.platform_fee = self.amount_paid * (self.platform_fee_percent / 100)
        self.net_amount = self.amount_paid - self.platform_fee

    def grant_access(self):
        """Grant access to content"""
        from django.utils import timezone
        self.status = PPVPurchaseStatus.COMPLETED
        self.access_granted_at = timezone.now()
        if self.access_type == PPVAccessType.TIMED and not self.expires_at:
            # Default 24 hours for timed access if not specified
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)
        self.save()

    def mark_expired(self):
        """Mark purchase as expired"""
        self.is_expired = True
        self.status = PPVPurchaseStatus.EXPIRED
        self.save()

    def process_refund(self, amount=None, reason=None):
        """Process refund for purchase"""
        from django.utils import timezone
        self.refund_amount = amount or self.amount_paid
        self.refund_reason = reason
        self.refunded_at = timezone.now()
        self.status = PPVPurchaseStatus.REFUNDED
        self.save()

    def increment_download(self):
        """Increment download counter if downloads are allowed"""
        if self.allow_download:
            self.download_count += 1
            self.save()
            return True
        return False


class PPVAccessLog(TenantAwareModel):
    """
    Log every time a fan accesses PPV content
    Useful for detecting abuse and analytics
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(
        PPVPurchase,
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='ppv_access_logs'
    )
    content = models.ForeignKey(
        'lipaidox_content.Content',
        on_delete=models.CASCADE,
        related_name='ppv_access_logs'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ppv_access_logs'
        app_label = 'lipaidox_ppv'
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['purchase'], name='idx_ppv_log_purchase'),
            models.Index(fields=['fan'], name='idx_ppv_log_fan'),
            models.Index(fields=['accessed_at'], name='idx_ppv_log_accessed'),
        ]

    def __str__(self):
        return f"Access: {self.fan.username} - {self.content.id} at {self.accessed_at}"
