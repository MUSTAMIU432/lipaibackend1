from django.db import models
import uuid
from .enums import CreditTransactionType, GiftAnimationType, CreditGiftStatus


class FanCreditWallet(models.Model):
    """
    Each fan has a credit wallet for sending gifts to creators
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fan = models.OneToOneField(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='fan_credit_wallet'
    )

    # Balances
    purchased_credits = models.IntegerField(default=0)
    gifted_credits = models.IntegerField(default=0)

    # Lifetime Stats
    total_credits_purchased = models.IntegerField(default=0)
    total_credits_gifted_by_admin = models.IntegerField(default=0)
    total_credits_sent = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fan_credit_wallets'
        indexes = [
            models.Index(fields=['fan'], name='idx_fan_wallet_fan'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(purchased_credits__gte=0), name='fan_purchased_credits_check'),
            models.CheckConstraint(check=models.Q(gifted_credits__gte=0), name='fan_gifted_credits_check'),
            models.CheckConstraint(check=models.Q(total_credits_sent__gte=0), name='fan_total_sent_check'),
        ]

    @property
    def total_available_credits(self):
        return self.purchased_credits + self.gifted_credits

    def has_sufficient_credits(self, amount):
        """Check if fan has enough credits to send a gift"""
        return self.total_available_credits >= amount

    def use_credits(self, amount, gift_sent_id=None):
        """
        Use credits to send a gift.
        Priority: purchased credits first, then gifted
        """
        if not self.has_sufficient_credits(amount):
            return False

        credits_remaining = amount
        credits_before = self.total_available_credits

        # Use purchased credits first
        if self.purchased_credits > 0:
            to_use = min(credits_remaining, self.purchased_credits)
            self.purchased_credits -= to_use
            credits_remaining -= to_use
            self.save(update_fields=['purchased_credits', 'updated_at'])

        # Then use gifted credits
        if credits_remaining > 0 and self.gifted_credits > 0:
            to_use = min(credits_remaining, self.gifted_credits)
            self.gifted_credits -= to_use
            credits_remaining -= to_use
            self.save(update_fields=['gifted_credits', 'updated_at'])

        # Update totals
        self.total_credits_sent += amount
        self.save(update_fields=['total_credits_sent', 'updated_at'])

        # Create ledger entry
        FanCreditLedger.objects.create(
            fan=self.fan,
            wallet=self,
            transaction_type=CreditTransactionType.SPENT,
            credits_delta=-amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            gift_sent_id=gift_sent_id,
            description=f"Sent {amount} credits as gift to creator",
        )

        return True

    def add_purchased_credits(self, amount, purchase_id=None):
        """Add purchased credits to wallet"""
        credits_before = self.total_available_credits
        self.purchased_credits += amount
        self.total_credits_purchased += amount
        self.save(update_fields=['purchased_credits', 'total_credits_purchased', 'updated_at'])

        FanCreditLedger.objects.create(
            fan=self.fan,
            wallet=self,
            transaction_type=CreditTransactionType.PURCHASE,
            credits_delta=amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            purchase_id=purchase_id,
            description=f"Purchased {amount} fan credits",
        )

    def add_gifted_credits(self, amount, gift_id=None):
        """Add admin-gifted credits to wallet"""
        credits_before = self.total_available_credits
        self.gifted_credits += amount
        self.total_credits_gifted_by_admin += amount
        self.save(update_fields=['gifted_credits', 'total_credits_gifted_by_admin', 'updated_at'])

        FanCreditLedger.objects.create(
            fan=self.fan,
            wallet=self,
            transaction_type=CreditTransactionType.ADMIN_GIFT,
            credits_delta=amount,
            credits_before=credits_before,
            credits_after=self.total_available_credits,
            gift_id=gift_id,
            description=f"Received {amount} fan credits as gift from admin",
        )

    def __str__(self):
        return f"{self.fan.username} - {self.total_available_credits} fan credits"


class FanCreditLedger(models.Model):
    """
    Every credit movement for a fan - full append-only history
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='fan_credit_ledger_entries'
    )
    wallet = models.ForeignKey(
        FanCreditWallet,
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
    gift_sent = models.ForeignKey(
        'FanCreditGiftSent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Notes
    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fan_credit_ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['fan'], name='idx_fan_ledger_fan'),
            models.Index(fields=['wallet'], name='idx_fan_ledger_wallet'),
            models.Index(fields=['transaction_type'], name='idx_fan_ledger_type'),
            models.Index(fields=['created_at'], name='idx_fan_ledger_created'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_after__gte=0), name='fan_credits_after_check'),
            models.CheckConstraint(
                check=models.Q(credits_after=models.F('credits_before') + models.F('credits_delta')),
                name='fan_delta_consistency'
            ),
        ]

    def __str__(self):
        return f"{self.fan.username} {self.transaction_type}: {self.credits_delta:+d}"


class FanCreditGiftSent(models.Model):
    """
    Every time a fan sends credits to a creator during a live stream
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fan = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='gifts_sent'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='gifts_received'
    )
    fan_wallet = models.ForeignKey(
        FanCreditWallet,
        on_delete=models.CASCADE,
        related_name='gifts_sent'
    )
    live_stream_id = models.UUIDField()

    # Gift Detail
    credits_sent = models.IntegerField()
    animation_type = models.CharField(max_length=20, choices=GiftAnimationType.choices, default=GiftAnimationType.HEART)
    message = models.CharField(max_length=255, blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)

    # Conversion to Earnings
    conversion_rate = models.ForeignKey(
        'CreditConversionRate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    monetary_value = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    creator_earnings = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=CreditGiftStatus.choices, default=CreditGiftStatus.PENDING)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Wallet Credit to Creator
    creator_wallet_credited = models.BooleanField(default=False)
    creator_wallet = models.ForeignKey(
        'CreatorCreditWallet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gifts_received'
    )

    sent_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fan_credit_gifts_sent'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['fan'], name='idx_fangifts_fan'),
            models.Index(fields=['creator'], name='idx_fangifts_creator'),
            models.Index(fields=['live_stream_id'], name='idx_fangifts_stream'),
            models.Index(fields=['status'], name='idx_fangifts_status'),
            models.Index(fields=['sent_at'], name='idx_fangifts_sent'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_sent__gt=0), name='gift_sent_credits_check'),
            models.CheckConstraint(
                check=models.Q(monetary_value__isnull=True) | models.Q(monetary_value__gte=0),
                name='gift_sent_monetary_value_check'
            ),
            models.CheckConstraint(
                check=models.Q(creator_earnings__isnull=True) | models.Q(creator_earnings__gte=0),
                name='gift_sent_creator_earnings_check'
            ),
        ]

    def __str__(self):
        return f"{self.fan.username} sent {self.credits_sent} credits to {self.creator.username}"

    def calculate_earnings(self):
        """Calculate creator earnings based on conversion rate"""
        if self.conversion_rate:
            earnings = self.conversion_rate.calculate_earnings(self.credits_sent)
            self.monetary_value = earnings['total_value']
            self.platform_fee = earnings['platform_fee']
            self.creator_earnings = earnings['creator_earnings']
            self.save(update_fields=['monetary_value', 'platform_fee', 'creator_earnings'])
            return earnings
        return None
