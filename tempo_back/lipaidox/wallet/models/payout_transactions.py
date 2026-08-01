import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class PayoutTransaction(TenantAwareModel):
    """
    Every payout request a creator makes
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='payout_transactions'
    )
    wallet = models.ForeignKey(
        'lipaidox_wallet.CreatorWallet',
        on_delete=models.CASCADE,
        related_name='payout_transactions'
    )
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='payout_transactions'
    )

    # Payout Detail
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    tax_withholding_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_withheld_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_payout_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('reversed', 'Reversed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )

    # Gateway
    gateway_reference = models.CharField(max_length=255, blank=True, null=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    gateway_fee = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Failure
    failure_reason = models.CharField(
        max_length=50,
        choices=[
            ('invalid_account', 'Invalid Account'),
            ('insufficient_funds', 'Insufficient Funds'),
            ('bank_rejected', 'Bank Rejected'),
            ('gateway_error', 'Gateway Error'),
            ('compliance_hold', 'Compliance Hold'),
            ('account_suspended', 'Account Suspended'),
            ('other', 'Other'),
        ],
        null=True,
        blank=True
    )
    failure_note = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)

    # Reversal
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True, null=True)
    reversed_by = models.ForeignKey(
        'lipaidox_admin_panel.AdminAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversed_payouts'
    )

    # Review
    requires_admin_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        'lipaidox_admin_panel.AdminAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payouts'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    processing_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payout_transactions'
        app_label = 'lipaidox_wallet'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator'], name='idx_payout_creator'),
            models.Index(fields=['wallet'], name='idx_payout_wallet'),
            models.Index(fields=['status'], name='idx_payout_status'),
            models.Index(fields=['initiated_at'], name='idx_payout_initiated'),
            models.Index(fields=['completed_at'], name='idx_payout_completed'),
            models.Index(fields=['payment_method'], name='idx_payout_payment_method'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='payout_amount_check'),
            models.CheckConstraint(check=models.Q(net_payout_amount__gt=0), name='payout_net_amount_check'),
            models.CheckConstraint(check=models.Q(tax_withheld_amount__gte=0), name='payout_tax_check'),
            models.CheckConstraint(
                check=models.Q(net_payout_amount=models.F('amount') - models.F('tax_withheld_amount')),
                name='payout_net_calculation'
            ),
            models.CheckConstraint(check=models.Q(retry_count__gte=0), name='payout_retry_check'),
            models.CheckConstraint(
                check=models.Q(tax_withholding_percent__gte=0) & models.Q(tax_withholding_percent__lte=100),
                name='payout_tax_percent_check'
            ),
        ]

    def __str__(self):
        return f"Payout: {self.creator.username} - {self.net_payout_amount} {self.currency}"

    def calculate_taxes(self):
        """Calculate tax withholding"""
        self.tax_withheld_amount = self.amount * (self.tax_withholding_percent / 100)
        self.net_payout_amount = self.amount - self.tax_withheld_amount

    def start_processing(self):
        """Mark payout as processing"""
        from django.utils import timezone
        self.status = 'processing'
        self.processing_at = timezone.now()
        self.save()

    def complete_payout(self, gateway_reference=None, gateway_response=None):
        """Mark payout as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        if gateway_reference:
            self.gateway_reference = gateway_reference
        if gateway_response:
            self.gateway_response = gateway_response
        self.save()

    def fail_payout(self, failure_reason, failure_note=None):
        """Mark payout as failed"""
        from django.utils import timezone
        self.status = 'failed'
        self.failure_reason = failure_reason
        self.failure_note = failure_note
        self.retry_count += 1
        self.last_retry_at = timezone.now()
        self.save()

    def reverse_payout(self, reversal_reason, reversed_by_admin):
        """Reverse a payout and return funds to wallet"""
        from django.utils import timezone
        self.status = 'reversed'
        self.reversed_at = timezone.now()
        self.reversal_reason = reversal_reason
        self.reversed_by = reversed_by_admin
        self.save()

        # Return funds to wallet
        from .wallet_transactions import WalletTransaction
        self.wallet.add_available_balance(self.amount)
        WalletTransaction.create_payout_reversal_transaction(
            wallet=self.wallet,
            amount=self.amount,
            payout_id=self.id,
            description=f"Payout reversal: {reversal_reason}"
        )

    def approve_payout(self, approved_by_admin):
        """Approve payout for processing"""
        from django.utils import timezone
        self.approved_by = approved_by_admin
        self.approved_at = timezone.now()
        self.save()

    def can_retry(self):
        """Check if payout can be retried"""
        return self.status == 'failed' and self.retry_count < 3
