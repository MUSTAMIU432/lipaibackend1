from decimal import Decimal

from django.db import models
from django.utils import timezone
import uuid
from .enums import CreditTransactionType


CREDIT_PLACES = 6  # DECIMAL(20,6) — fixed-point, never float


class CreatorCreditWallet(models.Model):
    """
    A creator's live-streaming credit wallet.

    Credits are fixed-point decimals (`DECIMAL(20,6)`), because live time is billed
    by the second: 100 credits = 15 minutes, i.e. one credit every 9 seconds.

    Three buckets hold the balance (`free_monthly` is spent first, then
    `purchased`, then `gifted`). `reserved_credits` is NOT a fourth bucket — it is
    the part of the total currently held for live sessions in progress, so:

        total_available_credits = purchased + free_monthly + gifted
        spendable_credits       = total_available_credits - reserved_credits

    The balance only ever changes through a ledger row (`CreatorCreditLedger`).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='credit_wallet'
    )

    # Balances
    purchased_credits = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    free_monthly_credits = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    gifted_credits = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    # Held for live sessions in progress; released or consumed on settlement.
    reserved_credits = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)

    # Usage Tracking
    total_credits_used = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    total_credits_purchased = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    total_credits_gifted = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)

    # Monthly plan allocation
    monthly_credits_allocated = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
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
            models.CheckConstraint(check=models.Q(reserved_credits__gte=0), name='reserved_credits_check'),
            # A hold can never exceed what is actually in the wallet.
            models.CheckConstraint(
                check=models.Q(reserved_credits__lte=(
                    models.F('purchased_credits') + models.F('free_monthly_credits') + models.F('gifted_credits')
                )),
                name='reserved_within_balance_check',
            ),
        ]

    @property
    def total_available_credits(self):
        """Everything in the wallet, including credits held for a live in progress."""
        return self.purchased_credits + self.free_monthly_credits + self.gifted_credits

    @property
    def spendable_credits(self):
        """What can still be spent or reserved right now."""
        return self.total_available_credits - self.reserved_credits

    def has_sufficient_credits(self, amount=1):
        """True if `amount` credits can be spent right now (holds excluded)."""
        return self.spendable_credits >= Decimal(str(amount))

    def _ledger(self, transaction_type, delta, before, **extra):
        return CreatorCreditLedger.objects.create(
            creator=self.creator,
            wallet=self,
            transaction_type=transaction_type,
            credits_delta=delta,
            credits_before=before,
            credits_after=self.total_available_credits,
            **extra,
        )

    def take_credits(self, amount):
        """
        Remove `amount` from the buckets — free monthly first, then purchased,
        then gifted. Modifies fields in memory only; the caller saves and writes
        the ledger row. Raises ValueError if the buckets can't cover it.
        """
        amount = Decimal(str(amount))
        if amount > self.total_available_credits:
            raise ValueError("Insufficient credits")
        remaining = amount
        for field in ('free_monthly_credits', 'purchased_credits', 'gifted_credits'):
            have = getattr(self, field)
            take = min(remaining, have)
            setattr(self, field, have - take)
            remaining -= take
            if remaining <= 0:
                break

    def use_credits(self, amount, live_stream_id=None, description=None, transaction_type=None, metadata=None):
        """
        Spend `amount` credits that are NOT already held. Returns False (and
        changes nothing) when the spendable balance can't cover it.
        """
        amount = Decimal(str(amount))
        if amount <= 0 or not self.has_sufficient_credits(amount):
            return False
        before = self.total_available_credits
        self.take_credits(amount)
        self.total_credits_used += amount
        self.save(update_fields=[
            'free_monthly_credits', 'purchased_credits', 'gifted_credits',
            'total_credits_used', 'updated_at',
        ])
        self._ledger(
            transaction_type or CreditTransactionType.SPENT, -amount, before,
            live_stream_id=live_stream_id,
            description=description or f"Used {amount.normalize():f} credits",
            metadata=metadata or {},
        )
        return True

    def add_purchased_credits(self, amount, purchase_id=None):
        """Add purchased credits to wallet"""
        amount = Decimal(str(amount))
        before = self.total_available_credits
        self.purchased_credits += amount
        self.total_credits_purchased += amount
        self.save(update_fields=['purchased_credits', 'total_credits_purchased', 'updated_at'])
        self._ledger(
            CreditTransactionType.PURCHASE, amount, before,
            purchase_id=purchase_id,
            description=f"Purchased {amount.normalize():f} credits",
        )

    def add_gifted_credits(self, amount, gift_id=None, expires_at=None):
        """Add admin-gifted credits to wallet"""
        amount = Decimal(str(amount))
        before = self.total_available_credits
        self.gifted_credits += amount
        self.total_credits_gifted += amount
        self.save(update_fields=['gifted_credits', 'total_credits_gifted', 'updated_at'])
        self._ledger(
            CreditTransactionType.ADMIN_GIFT, amount, before,
            gift_id=gift_id, expires_at=expires_at,
            description=f"Received {amount.normalize():f} credits as gift",
        )

    def set_monthly_allocation(self, amount, description=None):
        """
        Set the free monthly bucket to the plan's allocation. Unused free credits
        from the previous period don't roll over — the bucket is replaced, and the
        net change is the one ledger row.
        """
        amount = Decimal(str(amount))
        before = self.total_available_credits
        previous = self.free_monthly_credits
        self.free_monthly_credits = amount
        self.monthly_credits_allocated = amount
        self.monthly_reset_at = timezone.now()
        self.save(update_fields=[
            'free_monthly_credits', 'monthly_credits_allocated', 'monthly_reset_at', 'updated_at',
        ])
        if amount != previous:
            self._ledger(
                CreditTransactionType.MONTHLY_ALLOCATION, amount - previous, before,
                description=description or f"Monthly allocation: {amount.normalize():f} free credits",
                metadata={'previous_free_balance': str(previous)},
            )

    def allocate_monthly_credits(self, amount):
        """Backwards-compatible name for `set_monthly_allocation`."""
        self.set_monthly_allocation(amount)

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
    credits_delta = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES)
    credits_before = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES)
    credits_after = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES)

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
        return f"{self.creator.username} {self.transaction_type}: {self.credits_delta:+f}"
