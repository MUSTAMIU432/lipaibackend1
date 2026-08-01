import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class StudentPaymentMethodType(models.TextChoices):
    CARD = 'card', 'Credit/Debit Card'
    BANK_ACCOUNT = 'bank_account', 'Bank Account'
    MOBILE_MONEY = 'mobile_money', 'Mobile Money'

class StudentPaymentMethodStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    EXPIRED = 'expired', 'Expired'
    FAILED = 'failed', 'Failed'

class StudentPaymentMethod(TenantAwareModel):
    """
    Payment methods for students (subscription billing)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_payment_methods"
    )
    
    method_type = models.CharField(
        max_length=20,
        choices=StudentPaymentMethodType.choices
    )
    status = models.CharField(
        max_length=20,
        choices=StudentPaymentMethodStatus.choices,
        default=StudentPaymentMethodStatus.ACTIVE
    )
    
    is_default = models.BooleanField(default=False)
    
    # Stripe integration
    stripe_payment_method_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Card details (stored via Stripe, not directly)
    card_brand = models.CharField(max_length=50, null=True, blank=True)
    card_last4 = models.CharField(max_length=4, null=True, blank=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)
    
    # Bank account details
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    bank_account_last4 = models.CharField(max_length=4, null=True, blank=True)
    
    # Mobile money details
    mobile_money_provider = models.CharField(max_length=100, null=True, blank=True)
    mobile_money_number = models.CharField(max_length=20, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "lms_student_payment_methods"
        app_label = "lms_financial"
        indexes = [
            models.Index(fields=['user'], name='idx_student_pm_user'),
            models.Index(fields=['status'], name='idx_student_pm_status'),
            models.Index(fields=['is_default'], name='idx_student_pm_default'),
        ]
    
    def __str__(self):
        if self.method_type == StudentPaymentMethodType.CARD:
            return f"{self.card_brand} ****{self.card_last4}"
        elif self.method_type == StudentPaymentMethodType.BANK_ACCOUNT:
            return f"{self.bank_name} ****{self.bank_account_last4}"
        elif self.method_type == StudentPaymentMethodType.MOBILE_MONEY:
            return f"{self.mobile_money_provider} {self.mobile_money_number}"
        return f"{self.method_type}"
    
    def mark_as_default(self):
        """Mark this payment method as default"""
        # Remove default status from other methods
        StudentPaymentMethod.objects.filter(
            user=self.user,
            is_default=True
        ).update(is_default=False)
        
        # Set this as default
        self.is_default = True
        self.save()
    
    @classmethod
    def get_default_payment_method(cls, user):
        """Get default payment method for user"""
        return cls.objects.filter(
            user=user,
            status=StudentPaymentMethodStatus.ACTIVE,
            is_default=True
        ).first()
    
    @classmethod
    def get_active_payment_methods(cls, user):
        """Get all active payment methods for user"""
        return cls.objects.filter(
            user=user,
            status=StudentPaymentMethodStatus.ACTIVE
        ).order_by('-is_default', '-created_at')
