from django.db import models
import uuid
from django.db.models import F
from .enums import CreditTransactionType


class CreatorCreditWallet(models.Model):
    """
    Each creator has a credit wallet tracking their live streaming credits
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='credit_wallet'
    )

    # Balances
    purchased_credits = models.IntegerField(default=0)
    free_monthly_credits = models.IntegerField(default=0)
    gifted_credits = models.IntegerField(default=0)

    # Usage Tracking
    total_credits_used = models.IntegerField(default=0)
    total_credits_purchased = models.IntegerField(default=0)
    total_credits_gifted = models.IntegerField(default=0)

    # Monthly Reset (Promax only)
    monthly_credits_allocated = models.IntegerField(default=0)
    monthly_reset_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'creator_credit_wallets'
        indexes = [
            models.Index(fields=['creator'], name='idx_creator_wallet_creator'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(purchased_credits__gte=0), name='purchased_credits_check'),
            models.CheckConstraint(check=models.Q(free_monthly_credits__gte=0), name='free_monthly_credits_check'),
            models.CheckConstraint(check=models.Q(gifted_credits__gte=0), name='gifted_credits_check'),
            models.CheckConstraint(check=models.Q(total_credits_used__gte=0), name='total_used_check'),
        ]

    @property
    def total_available_credits(self):
        return self.purchased_credits + self.free_monthly_credits + self.gifted_credits

    def has_sufficient_credits(self, amount=1):
        """Check if creator has enough credits to start live (1 credit = 15 min)"""
        return self.total_available_credits >= amount

    def use_credits(self, amount=1, live_stream_id=None):
        """
        Use credits for live streaming.
        Priority: free monthly credits first, then purchased, then gifted
        """
        if not self.has_sufficient_credits(amount):
            return False

        credits_remaining = amount
        credits_before = self.total_available_credits

        # Use free monthly credits first
        if self.free_monthly_credits > 0:
            to_use = min(credits_remaining, self.free_monthly_credits)
            self.free_monthly_credits -= to_use
            credits_remaining -= to_use
            self.save(update_fields=['free_monthly_credits', 'updated_at'])

        # Then use purchased credits
        if credits_remaining > 0 and self.purchased_credits > 0:
            to_use = min(credits_remaining, self.purchased_credits)
            self.purchased_credits -= to_use
            credits_remaining -= to_use
            self.save(update_fields=['purchased_credits', 'updated_at'])

        # Finally use gifted credits
        if credits_remaining > 0 and self.gifted_credits > 0:
            to_use = min(credits_remaining, self.gifted_credits)
            self.gifted_credits -= to_use
            credits_remaining -= to_use
            self.save(update_fields=['gifted_credits', 'updated_at'])

        # Update totals
        self.total_credits_used += amount
        self.save(update_fields=['total_credits_used', 'updated_at'])

        # Create ledger entry
        CreatorCreditLedger.objects.create(
            creator=self.creator,
            wallet=self,
            transaction_type=CreditTransactionType.SPENT,
            credits_delta=-amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            live_stream_id=live_stream_id,
            description=f"Used {amount} credit(s) for live streaming",
        )

        return True

    def add_purchased_credits(self, amount, purchase_id=None):
        """Add purchased credits to wallet"""
        credits_before = self.total_available_credits
        self.purchased_credits += amount
        self.total_credits_purchased += amount
        self.save(update_fields=['purchased_credits', 'total_credits_purchased', 'updated_at'])

        CreatorCreditLedger.objects.create(
            creator=self.creator,
            wallet=self,
            transaction_type=CreditTransactionType.PURCHASE,
            credits_delta=amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            purchase_id=purchase_id,
            description=f"Purchased {amount} creator credits",
        )

    def add_gifted_credits(self, amount, gift_id=None, expires_at=None):
        """Add admin-gifted credits to wallet"""
        credits_before = self.total_available_credits
        self.gifted_credits += amount
        self.total_credits_gifted += amount
        self.save(update_fields=['gifted_credits', 'total_credits_gifted', 'updated_at'])

        CreatorCreditLedger.objects.create(
            creator=self.creator,
            wallet=self,
            transaction_type=CreditTransactionType.ADMIN_GIFT,
            credits_delta=amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            gift_id=gift_id,
            description=f"Received {amount} creator credits as gift",
            expires_at=expires_at,
        )

    def allocate_monthly_credits(self, amount):
        """Allocate free monthly credits (Promax plan)"""
        credits_before = self.total_available_credits
        self.free_monthly_credits += amount
        self.monthly_credits_allocated = amount
        self.monthly_reset_at = models.functions.Now()
        self.save(update_fields=['free_monthly_credits', 'monthly_credits_allocated', 'monthly_reset_at', 'updated_at'])

        CreatorCreditLedger.objects.create(
            creator=self.creator,
            wallet=self,
            transaction_type=CreditTransactionType.MONTHLY_ALLOCATION,
            credits_delta=amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            description=f"Monthly allocation: {amount} free creator credits",
        )

    def __str__(self):
        return f"{self.creator.username} - {self.total_available_credits} credits"


class CreatorCreditLedger(models.Model):
    """
    Every credit movement for a creator - full append-only history
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='credit_ledger_entries'
    )
    wallet = models.ForeignKey(
        CreatorCreditWallet,
        on_delete=models.CASCADE,
        related_name='ledger_entries'
    )

    # Transaction
    transaction_type = models.CharField(max_length=30, choices=CreditTransactionType.choices)
    credits_delta = models.IntegerField()
    credits_before = models.IntegerField()
    credits_after = models.IntegerField()

    # Source References
    purchase = models.ForeignKey(
        'CreditPurchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    gift = models.ForeignKey(
        'CreditGift',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    live_stream_id = models.UUIDField(null=True, blank=True)

    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    is_expired = models.BooleanField(default=False)

    # Notes
    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'creator_credit_ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['creator'], name='idx_creator_ledger_creator'),
            models.Index(fields=['wallet'], name='idx_creator_ledger_wallet'),
            models.Index(fields=['transaction_type'], name='idx_creator_ledger_type'),
            models.Index(fields=['created_at'], name='idx_creator_ledger_created'),
            models.Index(fields=['expires_at'], name='idx_creator_ledger_expires'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_after__gte=0), name='credits_after_check'),
            models.CheckConstraint(
                check=models.Q(credits_after=models.F('credits_before') + models.F('credits_delta')),
                name='delta_consistency'
            ),
        ]

    def __str__(self):
        return f"{self.creator.username} {self.transaction_type}: {self.credits_delta:+d}"
