import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class WalletTransaction(TenantAwareModel):
    """
    Central ledger - every money movement into or out of creator wallets
    Append-only, never updated
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        'lipaidox_wallet.CreatorWallet',
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='wallet_transactions'
    )

    # Transaction Detail
    transaction_type = models.CharField(
        max_length=50,
        choices=[
            ('ppv_earning', 'PPV Earning'),
            ('subscription_earning', 'Subscription Earning'),
            ('tip_earning', 'Tip Earning'),
            ('credit_gift_earning', 'Credit Gift Earning'),
            ('live_stream_earning', 'Live Stream Earning'),
            ('payout', 'Payout'),
            ('payout_reversal', 'Payout Reversal'),
            ('refund_deduction', 'Refund Deduction'),
            ('platform_fee', 'Platform Fee'),
            ('tax_withholding', 'Tax Withholding'),
            ('adjustment', 'Adjustment'),
            ('bonus', 'Bonus'),
        ],
        default='ppv_earning'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('cleared', 'Cleared'),
            ('paid_out', 'Paid Out'),
            ('reversed', 'Reversed'),
            ('held', 'Held'),
        ],
        default='pending'
    )
    amount = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=10, default='USD')
    balance_before = models.DecimalField(max_digits=14, decimal_places=4)
    balance_after = models.DecimalField(max_digits=14, decimal_places=4)
    balance_type = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('available', 'Available'),
            ('on_hold', 'On Hold'),
        ]
    )

    # Source References
    ppv_purchase_id = models.UUIDField(null=True, blank=True)
    subscription_payment_id = models.UUIDField(null=True, blank=True)
    tip_id = models.UUIDField(null=True, blank=True)
    live_stream_id = models.UUIDField(null=True, blank=True)
    credit_transaction_id = models.UUIDField(null=True, blank=True)
    payout_id = models.UUIDField(null=True, blank=True)

    # Clearing
    clears_at = models.DateTimeField(null=True, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    # Notes
    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wallet_transactions'
        app_label = 'lipaidox_wallet'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet'], name='idx_wallet_txn_wallet'),
            models.Index(fields=['creator'], name='idx_wallet_txn_creator'),
            models.Index(fields=['transaction_type'], name='idx_wallet_txn_type'),
            models.Index(fields=['status'], name='idx_wallet_txn_status'),
            models.Index(fields=['clears_at'], name='idx_wallet_txn_clears_at'),
            models.Index(fields=['created_at'], name='idx_wallet_txn_created'),
        ]
        constraints = [
            models.CheckConstraint(check=~models.Q(amount=0), name='wallet_txn_amount_check'),
            models.CheckConstraint(check=models.Q(balance_after__gte=0), name='wallet_txn_balance_after_check'),
            models.CheckConstraint(
                check=models.Q(balance_after=models.F('balance_before') + models.F('amount')),
                name='wallet_txn_balance_consistency'
            ),
        ]

    def __str__(self):
        return f"Wallet Transaction: {self.transaction_type} - {self.amount} {self.currency}"

    @classmethod
    def create_earning_transaction(cls, wallet, amount, transaction_type, source_id=None, description=None):
        """Create an earning transaction"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Determine which balance to affect
        if transaction_type in ['ppv_earning', 'subscription_earning', 'tip_earning', 'credit_gift_earning', 'live_stream_earning']:
            balance_type = 'pending'
            clears_at = timezone.now() + timedelta(days=7)  # 7-day clearing period
        else:
            balance_type = 'available'
            clears_at = None
        
        balance_before = getattr(wallet, f"{balance_type}_balance")
        balance_after = balance_before + amount
        
        # Create transaction
        transaction = cls.objects.create(
            wallet=wallet,
            creator=wallet.creator,
            tenant=wallet.tenant,
            transaction_type=transaction_type,
            status='pending' if balance_type == 'pending' else 'cleared',
            amount=amount,
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            balance_type=balance_type,
            clears_at=clears_at,
            description=description
        )
        
        # Set source reference
        if transaction_type == 'ppv_earning' and source_id:
            transaction.ppv_purchase_id = source_id
        elif transaction_type == 'tip_earning' and source_id:
            transaction.tip_id = source_id
        elif transaction_type == 'credit_gift_earning' and source_id:
            transaction.credit_transaction_id = source_id
        elif transaction_type == 'live_stream_earning' and source_id:
            transaction.live_stream_id = source_id
        elif transaction_type == 'subscription_earning' and source_id:
            transaction.subscription_payment_id = source_id
        elif transaction_type == 'payout' and source_id:
            transaction.payout_id = source_id
        
        transaction.save()
        return transaction

    @classmethod
    def create_payout_transaction(cls, wallet, amount, payout_id, description=None):
        """Create a payout transaction (negative amount)"""
        balance_before = wallet.available_balance
        balance_after = balance_before - amount
        
        return cls.objects.create(
            wallet=wallet,
            creator=wallet.creator,
            tenant=wallet.tenant,
            transaction_type='payout',
            status='paid_out',
            amount=-amount,  # Negative for money out
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            balance_type='available',
            payout_id=payout_id,
            description=description
        )

    @classmethod
    def create_payout_reversal_transaction(cls, wallet, amount, payout_id, description=None):
        """Create a payout reversal transaction (positive amount)"""
        balance_before = wallet.available_balance
        balance_after = balance_before + amount
        
        return cls.objects.create(
            wallet=wallet,
            creator=wallet.creator,
            tenant=wallet.tenant,
            transaction_type='payout_reversal',
            status='cleared',
            amount=amount,  # Positive for money back
            currency=wallet.currency,
            balance_before=balance_before,
            balance_after=balance_after,
            balance_type='available',
            payout_id=payout_id,
            description=description
        )

    def mark_cleared(self):
        """Mark transaction as cleared"""
        from django.utils import timezone
        self.status = 'cleared'
        self.cleared_at = timezone.now()
        self.save()

    def reverse_transaction(self, reason=None):
        """Reverse a transaction"""
        from django.utils import timezone
        self.status = 'reversed'
        if reason:
            self.description = f"REVERSED: {reason}"
        self.save()
