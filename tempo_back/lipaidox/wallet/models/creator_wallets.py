import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class WalletTransactionType(models.TextChoices):
    """Types of wallet transactions"""
    PPV_EARNING = 'ppv_earning', 'PPV Earning'
    SUBSCRIPTION_EARNING = 'subscription_earning', 'Subscription Earning'
    TIP_EARNING = 'tip_earning', 'Tip Earning'
    CREDIT_GIFT_EARNING = 'credit_gift_earning', 'Credit Gift Earning'
    LIVE_STREAM_EARNING = 'live_stream_earning', 'Live Stream Earning'
    PAYOUT = 'payout', 'Payout'
    PAYOUT_REVERSAL = 'payout_reversal', 'Payout Reversal'
    REFUND_DEDUCTION = 'refund_deduction', 'Refund Deduction'
    PLATFORM_FEE = 'platform_fee', 'Platform Fee'
    TAX_WITHHOLDING = 'tax_withholding', 'Tax Withholding'
    ADJUSTMENT = 'adjustment', 'Adjustment'
    BONUS = 'bonus', 'Bonus'


class WalletTransactionStatus(models.TextChoices):
    """Status of wallet transactions"""
    PENDING = 'pending', 'Pending'
    CLEARED = 'cleared', 'Cleared'
    PAID_OUT = 'paid_out', 'Paid Out'
    REVERSED = 'reversed', 'Reversed'
    HELD = 'held', 'Held'


class PayoutStatus(models.TextChoices):
    """Status of payouts"""
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REVERSED = 'reversed', 'Reversed'
    CANCELLED = 'cancelled', 'Cancelled'


class PayoutFailureReason(models.TextChoices):
    """Reasons for payout failures"""
    INVALID_ACCOUNT = 'invalid_account', 'Invalid Account'
    INSUFFICIENT_FUNDS = 'insufficient_funds', 'Insufficient Funds'
    BANK_REJECTED = 'bank_rejected', 'Bank Rejected'
    GATEWAY_ERROR = 'gateway_error', 'Gateway Error'
    COMPLIANCE_HOLD = 'compliance_hold', 'Compliance Hold'
    ACCOUNT_SUSPENDED = 'account_suspended', 'Account Suspended'
    OTHER = 'other', 'Other'


class CreatorWallet(TenantAwareModel):
    """
    Creator wallets - Module 14
    Tracks creator balances and earnings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='wallets'
    )
    currency = models.CharField(max_length=10, default='USD')

    # Balances
    pending_balance = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    available_balance = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    on_hold_balance = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Lifetime Stats
    lifetime_earnings = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    lifetime_payouts = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    lifetime_refunds = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    lifetime_platform_fees = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Earnings Breakdown
    earnings_from_ppv = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    earnings_from_subscriptions = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    earnings_from_tips = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    earnings_from_credits = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    earnings_from_live_streams = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Payout Settings
    last_payout_at = models.DateTimeField(null=True, blank=True)
    last_payout_amount = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'creator_wallets'
        app_label = 'lipaidox_wallet'
        indexes = [
            models.Index(fields=['creator'], name='idx_wallet_creator'),
            models.Index(fields=['currency'], name='idx_wallet_currency'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['creator', 'currency'],
                name='creator_wallets_unique'
            ),
            models.CheckConstraint(check=models.Q(pending_balance__gte=0), name='wallet_pending_balance_check'),
            models.CheckConstraint(check=models.Q(available_balance__gte=0), name='wallet_available_balance_check'),
            models.CheckConstraint(check=models.Q(on_hold_balance__gte=0), name='wallet_on_hold_balance_check'),
            models.CheckConstraint(check=models.Q(lifetime_earnings__gte=0), name='wallet_lifetime_earnings_check'),
            models.CheckConstraint(check=models.Q(lifetime_payouts__gte=0), name='wallet_lifetime_payouts_check'),
        ]

    def __str__(self):
        return f"Wallet: {self.creator.username} - {self.currency}"

    @property
    def total_balance(self):
        """Calculate total balance"""
        return self.pending_balance + self.available_balance + self.on_hold_balance

    def add_pending_earning(self, amount, earning_type):
        """Add pending earnings to wallet"""
        self.pending_balance += amount
        self.lifetime_earnings += amount
        
        # Update specific earning category
        if earning_type == WalletTransactionType.PPV_EARNING:
            self.earnings_from_ppv += amount
        elif earning_type == WalletTransactionType.SUBSCRIPTION_EARNING:
            self.earnings_from_subscriptions += amount
        elif earning_type == WalletTransactionType.TIP_EARNING:
            self.earnings_from_tips += amount
        elif earning_type == WalletTransactionType.CREDIT_GIFT_EARNING:
            self.earnings_from_credits += amount
        elif earning_type == WalletTransactionType.LIVE_STREAM_EARNING:
            self.earnings_from_live_streams += amount
        
        self.save()

    def clear_pending_balance(self, amount):
        """Move pending balance to available balance"""
        if amount > self.pending_balance:
            raise ValueError("Insufficient pending balance")
        
        self.pending_balance -= amount
        self.available_balance += amount
        self.save()

    def deduct_available_balance(self, amount):
        """Deduct from available balance for payout"""
        if amount > self.available_balance:
            raise ValueError("Insufficient available balance")
        
        self.available_balance -= amount
        self.save()

    def add_available_balance(self, amount):
        """Add to available balance (e.g., payout reversal)"""
        self.available_balance += amount
        self.save()

    def hold_balance(self, amount):
        """Move balance to on_hold"""
        if amount > self.available_balance:
            raise ValueError("Insufficient available balance to hold")
        
        self.available_balance -= amount
        self.on_hold_balance += amount
        self.save()

    def release_hold_balance(self, amount):
        """Release held balance back to available"""
        if amount > self.on_hold_balance:
            raise ValueError("Insufficient held balance to release")
        
        self.on_hold_balance -= amount
        self.available_balance += amount
        self.save()

    def record_payout(self, amount):
        """Record a completed payout"""
        self.lifetime_payouts += amount
        self.last_payout_at = timezone.now()
        self.last_payout_amount = amount
        self.save()
