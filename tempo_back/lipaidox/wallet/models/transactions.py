import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class TransactionType(models.TextChoices):
    """Platform-wide transaction types"""
    PPV_PURCHASE = 'ppv_purchase', 'PPV Purchase'
    SUBSCRIPTION = 'subscription', 'Subscription'
    TIP = 'tip', 'Tip'
    CREDIT_PURCHASE = 'credit_purchase', 'Credit Purchase'
    LIVE_ENTRY = 'live_entry', 'Live Entry'
    PAYOUT = 'payout', 'Payout'
    REFUND = 'refund', 'Refund'
    TAX_WITHHOLDING = 'tax_withholding', 'Tax Withholding'
    PLATFORM_FEE = 'platform_fee', 'Platform Fee'
    ADJUSTMENT = 'adjustment', 'Adjustment'


class TransactionStatus(models.TextChoices):
    """Platform-wide transaction statuses"""
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'
    PARTIALLY_REFUNDED = 'partially_refunded', 'Partially Refunded'
    DISPUTED = 'disputed', 'Disputed'
    CANCELLED = 'cancelled', 'Cancelled'


class Transaction(TenantAwareModel):
    """
    Platform-wide master transaction ledger
    Every money movement between fans and creators
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Parties
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='platform_transactions'
    )

    # Transaction Detail
    transaction_type = models.CharField(
        max_length=50,
        choices=TransactionType.choices,
        default=TransactionType.PPV_PURCHASE
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING
    )

    # Amounts
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')

    # Source References
    ppv_purchase_id = models.UUIDField(null=True, blank=True)
    subscription_payment_id = models.UUIDField(null=True, blank=True)
    tip_id = models.UUIDField(null=True, blank=True)
    credit_purchase_id = models.UUIDField(null=True, blank=True)
    payout_id = models.UUIDField(null=True, blank=True)

    # Payment
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    gateway_reference = models.CharField(max_length=255, blank=True, null=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    # Refund
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_reason = models.TextField(blank=True, null=True)
    refunded_by = models.ForeignKey(
        'lipaidox_admin_panel.AdminAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunded_transactions'
    )

    # Dispute
    disputed_at = models.DateTimeField(null=True, blank=True)
    dispute_reason = models.TextField(blank=True, null=True)
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)

    # Description
    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transactions'
        app_label = 'lipaidox_wallet'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['fan'], name='idx_txn_fan'),
            models.Index(fields=['creator'], name='idx_txn_creator'),
            models.Index(fields=['transaction_type'], name='idx_txn_type'),
            models.Index(fields=['status'], name='idx_txn_status'),
            models.Index(fields=['gateway_reference'], name='idx_txn_gateway_ref'),
            models.Index(fields=['created_at'], name='idx_txn_created'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(gross_amount__gt=0), name='txn_gross_amount_check'),
            models.CheckConstraint(check=models.Q(platform_fee__gte=0), name='txn_platform_fee_check'),
            models.CheckConstraint(check=models.Q(net_amount__gte=0), name='txn_net_amount_check'),
            models.CheckConstraint(
                check=models.Q(net_amount=models.F('gross_amount') - models.F('platform_fee')),
                name='txn_net_calculation'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(refund_amount__isnull=True) |
                    (models.Q(refund_amount__gt=0) & models.Q(refund_amount__lte=models.F('gross_amount')))
                ),
                name='txn_refund_amount_check'
            ),
        ]

    def __str__(self):
        return f"Transaction: {self.transaction_type} - {self.gross_amount} {self.currency}"

    def calculate_platform_fee(self):
        """Calculate platform fee based on percentage"""
        self.platform_fee = self.gross_amount * (self.platform_fee_percent / 100)
        self.net_amount = self.gross_amount - self.platform_fee

    def complete_transaction(self, gateway_reference=None, gateway_response=None):
        """Mark transaction as completed"""
        if gateway_reference:
            self.gateway_reference = gateway_reference
        if gateway_response:
            self.gateway_response = gateway_response
        self.status = TransactionStatus.COMPLETED
        self.save()

    def fail_transaction(self):
        """Mark transaction as failed"""
        self.status = TransactionStatus.FAILED
        self.save()

    def refund_transaction(self, refund_amount, refund_reason, refunded_by_admin=None):
        """Process a refund"""
        from django.utils import timezone
        
        if refund_amount > self.gross_amount:
            raise ValueError("Refund amount cannot exceed gross amount")
        
        self.refunded_at = timezone.now()
        self.refund_amount = refund_amount
        self.refund_reason = refund_reason
        self.refunded_by = refunded_by_admin
        
        if refund_amount == self.gross_amount:
            self.status = TransactionStatus.REFUNDED
        else:
            self.status = TransactionStatus.PARTIALLY_REFUNDED
        
        self.save()

    def dispute_transaction(self, dispute_reason):
        """Mark transaction as disputed"""
        from django.utils import timezone
        self.disputed_at = timezone.now()
        self.dispute_reason = dispute_reason
        self.status = TransactionStatus.DISPUTED
        self.save()

    def resolve_dispute(self):
        """Mark dispute as resolved"""
        from django.utils import timezone
        self.dispute_resolved_at = timezone.now()
        self.save()

    @classmethod
    def create_ppv_transaction(cls, fan, creator, gross_amount, platform_fee_percent, ppv_purchase_id, description=None):
        """Create a PPV transaction"""
        platform_fee = gross_amount * (platform_fee_percent / 100)
        net_amount = gross_amount - platform_fee
        
        return cls.objects.create(
            fan=fan,
            creator=creator,
            tenant=fan.tenant,
            transaction_type=TransactionType.PPV_PURCHASE,
            status=TransactionStatus.PENDING,
            gross_amount=gross_amount,
            platform_fee_percent=platform_fee_percent,
            platform_fee=platform_fee,
            net_amount=net_amount,
            ppv_purchase_id=ppv_purchase_id,
            description=description
        )

    @classmethod
    def create_tip_transaction(cls, fan, creator, gross_amount, platform_fee_percent, tip_id, description=None):
        """Create a tip transaction"""
        platform_fee = gross_amount * (platform_fee_percent / 100)
        net_amount = gross_amount - platform_fee
        
        return cls.objects.create(
            fan=fan,
            creator=creator,
            tenant=fan.tenant,
            transaction_type=TransactionType.TIP,
            status=TransactionStatus.PENDING,
            gross_amount=gross_amount,
            platform_fee_percent=platform_fee_percent,
            platform_fee=platform_fee,
            net_amount=net_amount,
            tip_id=tip_id,
            description=description
        )

    @classmethod
    def create_subscription_transaction(cls, fan, creator, gross_amount, platform_fee_percent, subscription_payment_id, description=None):
        """Create a subscription transaction"""
        platform_fee = gross_amount * (platform_fee_percent / 100)
        net_amount = gross_amount - platform_fee
        
        return cls.objects.create(
            fan=fan,
            creator=creator,
            tenant=fan.tenant,
            transaction_type=TransactionType.SUBSCRIPTION,
            status=TransactionStatus.PENDING,
            gross_amount=gross_amount,
            platform_fee_percent=platform_fee_percent,
            platform_fee=platform_fee,
            net_amount=net_amount,
            subscription_payment_id=subscription_payment_id,
            description=description
        )
