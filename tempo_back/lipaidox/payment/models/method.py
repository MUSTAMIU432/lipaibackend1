import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class PaymentMethodType(models.TextChoices):
    BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
    MOBILE_MONEY = 'mobile_money', 'Mobile Money'
    CARD = 'card', 'Card'

class PayoutFrequency(models.TextChoices):
    WEEKLY = 'weekly', 'Weekly'
    BI_WEEKLY = 'bi_weekly', 'Bi-Weekly'
    MONTHLY = 'monthly', 'Monthly'
    MANUAL = 'manual', 'Manual'

class PayoutCurrency(models.TextChoices):
    USD = 'USD', 'USD'
    EUR = 'EUR', 'EUR'
    GBP = 'GBP', 'GBP'
    TZS = 'TZS', 'TZS'
    KES = 'KES', 'KES'
    NGN = 'NGN', 'NGN'
    GHS = 'GHS', 'GHS'
    ZAR = 'ZAR', 'ZAR'
    UGX = 'UGX', 'UGX'

class PaymentMethodStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    VERIFIED = 'verified', 'Verified'
    FAILED = 'failed', 'Failed'
    DISABLED = 'disabled', 'Disabled'

class TaxWithholdingRate(models.TextChoices):
    NONE = 'none', 'None'
    TEN_PERCENT = 'ten_percent', '10%'
    FIFTEEN_PERCENT = 'fifteen_percent', '15%'
    TWENTY_PERCENT = 'twenty_percent', '20%'
    THIRTY_PERCENT = 'thirty_percent', '30%'

class PaymentMethod(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="payment_methods")
    method_type = models.CharField(max_length=20, choices=PaymentMethodType.choices)
    status = models.CharField(max_length=20, choices=PaymentMethodStatus.choices, default=PaymentMethodStatus.PENDING)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Bank Transfer Fields
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    bank_account_holder_name = models.CharField(max_length=255, null=True, blank=True)
    bank_account_number_encrypted = models.TextField(null=True, blank=True)
    bank_account_number_last4 = models.CharField(max_length=4, null=True, blank=True)
    bank_swift_code = models.CharField(max_length=20, null=True, blank=True)
    bank_iban = models.CharField(max_length=50, null=True, blank=True)
    bank_routing_number = models.CharField(max_length=50, null=True, blank=True)
    bank_country = models.CharField(max_length=100, null=True, blank=True)
    bank_branch_name = models.CharField(max_length=255, null=True, blank=True)
    bank_branch_code = models.CharField(max_length=50, null=True, blank=True)

    # Mobile Money Fields
    mobile_money_provider = models.CharField(max_length=100, null=True, blank=True)
    mobile_money_phone_number = models.CharField(max_length=20, null=True, blank=True)
    mobile_money_phone_country_code = models.CharField(max_length=10, null=True, blank=True)
    mobile_money_account_name = models.CharField(max_length=255, null=True, blank=True)

    # Card Fields (Tokenized)
    card_holder_name = models.CharField(max_length=255, null=True, blank=True)
    card_last4 = models.CharField(max_length=4, null=True, blank=True)
    card_brand = models.CharField(max_length=50, null=True, blank=True)
    card_expiry_month = models.SmallIntegerField(null=True, blank=True)
    card_expiry_year = models.SmallIntegerField(null=True, blank=True)
    card_billing_address_line1 = models.CharField(max_length=255, null=True, blank=True)
    card_billing_city = models.CharField(max_length=100, null=True, blank=True)
    card_billing_postal_code = models.CharField(max_length=20, null=True, blank=True)
    card_billing_country = models.CharField(max_length=100, null=True, blank=True)
    card_gateway_token = models.TextField(null=True, blank=True)
    card_fingerprint = models.TextField(null=True, blank=True)

    # Payout Settings
    payout_currency = models.CharField(max_length=10, choices=PayoutCurrency.choices, default=PayoutCurrency.USD)
    payout_frequency = models.CharField(max_length=20, choices=PayoutFrequency.choices, default=PayoutFrequency.MONTHLY)
    minimum_payout_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    tax_withholding_rate = models.CharField(max_length=20, choices=TaxWithholdingRate.choices, default=TaxWithholdingRate.NONE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_methods"
        app_label = "lipaidox_payment"
        constraints = [
            models.UniqueConstraint(
                fields=['creator'], 
                condition=models.Q(is_primary=True),
                name='idx_payment_methods_one_primary'
            ),
            models.CheckConstraint(
                check=models.Q(minimum_payout_threshold__gte=10.00),
                name='minimum_threshold_check'
            )
        ]

    def __str__(self):
        return f"{self.method_type} - {self.creator} ({self.status})"
