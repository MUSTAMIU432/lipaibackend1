from django.db import models
import uuid
from .enums import CreditType, CreditPackageTarget


class CreditPackage(models.Model):
    """
    Predefined bundles a creator or fan can purchase
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    credit_type = models.CharField(max_length=20, choices=CreditType.choices)
    target = models.CharField(max_length=10, choices=CreditPackageTarget.choices, default=CreditPackageTarget.BOTH)

    # Credits & Pricing
    credit_amount = models.IntegerField()
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    bonus_credits = models.IntegerField(default=0)

    # Live Stream Specific (creator credits only)
    duration_minutes = models.IntegerField(null=True, blank=True)

    # Display
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    badge_label = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'credit_packages'
        ordering = ['credit_type', 'sort_order', 'price_usd']
        indexes = [
            models.Index(fields=['credit_type'], name='idx_pkg_type'),
            models.Index(fields=['target'], name='idx_pkg_target'),
            models.Index(fields=['is_active'], name='idx_pkg_is_active'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credit_amount__gt=0), name='credit_amount_check'),
            models.CheckConstraint(check=models.Q(price_usd__gt=0), name='price_check'),
            models.CheckConstraint(check=models.Q(bonus_credits__gte=0), name='bonus_credits_check'),
            models.CheckConstraint(
                check=models.Q(duration_minutes__isnull=True) | models.Q(duration_minutes__gt=0),
                name='duration_check'
            ),
        ]

    @property
    def total_credits(self):
        return self.credit_amount + self.bonus_credits

    def __str__(self):
        return f"{self.name} ({self.get_credit_type_display()})"


class CreditConversionRate(models.Model):
    """
    Defines how many fan credits equal how much real money for a creator payout
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credit_type = models.CharField(max_length=20, choices=CreditType.choices, default=CreditType.FAN_CREDIT)
    credits_per_unit = models.IntegerField()
    currency = models.CharField(max_length=10, default='USD')
    monetary_value = models.DecimalField(max_digits=10, decimal_places=4)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(auto_now_add=True)
    effective_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'lipaidox_admin_panel.AdminAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'credit_conversion_rates'
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['credit_type'], name='idx_rate_type'),
            models.Index(fields=['is_active'], name='idx_rate_is_active'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_per_unit__gt=0), name='rate_credits_per_unit_check'),
            models.CheckConstraint(check=models.Q(monetary_value__gt=0), name='rate_monetary_value_check'),
            models.CheckConstraint(
                check=models.Q(platform_fee_percent__gte=0, platform_fee_percent__lte=100),
                name='rate_platform_fee_check'
            ),
        ]

    @property
    def creator_receives(self):
        """Calculate how much creator receives after platform fee"""
        return self.monetary_value * (1 - (self.platform_fee_percent / 100))

    def __str__(self):
        return f"{self.credits_per_unit} {self.get_credit_type_display()} = {self.monetary_value} {self.currency}"

    def calculate_earnings(self, credits):
        """Calculate creator earnings for given credits. Decimal-safe (credit
        counts can arrive as int/float, monetary fields are Decimal)."""
        from decimal import Decimal
        credits = Decimal(str(credits))
        per_unit = Decimal(str(self.credits_per_unit)) or Decimal("1")
        units = credits / per_unit
        total_value = units * Decimal(str(self.monetary_value))
        platform_fee = total_value * (Decimal(str(self.platform_fee_percent)) / Decimal("100"))
        creator_earnings = total_value - platform_fee
        return {
            'total_value': total_value,
            'platform_fee': platform_fee,
            'creator_earnings': creator_earnings
        }
