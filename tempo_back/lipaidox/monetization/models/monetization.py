import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from multitenant.models import TenantAwareModel

class SubscriptionBillingCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    ANNUAL = 'annual', 'Annual'

class ContentCurrency(models.TextChoices):
    USD = 'USD', 'USD'
    EUR = 'EUR', 'EUR'
    GBP = 'GBP', 'GBP'
    TZS = 'TZS', 'TZS'
    KES = 'KES', 'KES'
    NGN = 'NGN', 'NGN'
    GHS = 'GHS', 'GHS'
    ZAR = 'ZAR', 'ZAR'
    UGX = 'UGX', 'UGX'

class PriceField(models.TextChoices):
    SUBSCRIPTION_PRICE = 'subscription_price', 'Subscription Price'
    PPV_PRICE = 'ppv_price', 'PPV Price'
    LIVE_STREAM_CREDIT_PRICE = 'live_stream_credit_price', 'Live Stream Credit Price'
    CUSTOM_CONTENT_PRICE = 'custom_content_price', 'Custom Content Price'
    TIP_MIN_AMOUNT = 'tip_min_amount', 'Tip Min Amount'
    TIP_MAX_AMOUNT = 'tip_max_amount', 'Tip Max Amount'

class MonetizationSettings(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="monetization_settings")

    # Subscription
    subscription_enabled = models.BooleanField(default=False)
    subscription_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    subscription_billing_cycle = models.CharField(max_length=20, choices=SubscriptionBillingCycle.choices, default=SubscriptionBillingCycle.MONTHLY)
    subscription_trial_days = models.IntegerField(default=0)
    subscription_description = models.TextField(null=True, blank=True)

    # Pay Per View
    ppv_enabled = models.BooleanField(default=False)
    ppv_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ppv_price_min = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    ppv_price_max = models.DecimalField(max_digits=10, decimal_places=2, default=999.99)

    # Live Stream Credits
    live_stream_enabled = models.BooleanField(default=False)
    live_stream_credit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    live_stream_credit_description = models.TextField(null=True, blank=True)

    # Custom Content
    custom_content_enabled = models.BooleanField(default=False)
    custom_content_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    custom_content_delivery_days = models.IntegerField(default=7)
    custom_content_description = models.TextField(null=True, blank=True)

    # Tipping
    tips_enabled = models.BooleanField(default=False)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       
    tip_min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    tip_max_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    tip_suggested_amounts = ArrayField(models.DecimalField(max_digits=10, decimal_places=2), default=list, blank=True)

    # Promotions & Discounts
    promotions_enabled = models.BooleanField(default=False)
    discount_config = models.JSONField(null=True, blank=True)

    # Platform Info
    display_currency = models.CharField(max_length=10, choices=ContentCurrency.choices, default=ContentCurrency.USD)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "monetization_settings"
        app_label = "lipaidox_monetization"
        indexes = [
            models.Index(fields=['subscription_enabled']),
            models.Index(fields=['tips_enabled']),
        ]

    def __str__(self):
        return f"Monetization Settings for {self.creator}"

class MonetizationPriceHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey("lipaidox_creator_profile.CreatorProfile", on_delete=models.CASCADE, related_name="price_history")
    monetization = models.ForeignKey(MonetizationSettings, on_delete=models.CASCADE, related_name="history")
    price_field = models.CharField(max_length=50, choices=PriceField.choices)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    new_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    changed_by = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="price_changes")
    reason = models.TextField(null=True, blank=True)
    effective_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "monetization_price_history"
        app_label = "lipaidox_monetization"
        ordering = ['-effective_at']

    def __str__(self):
        return f"Price Change: {self.price_field} by {self.creator}"
