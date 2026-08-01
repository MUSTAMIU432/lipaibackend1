from django.db import models
import uuid
from .enums import CreditType, CreditTransactionStatus


class CreditPurchase(models.Model):
    """
    When a creator or fan buys a credit package
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='credit_purchases'
    )
    credit_type = models.CharField(max_length=20, choices=CreditType.choices)
    package = models.ForeignKey(
        'CreditPackage',
        on_delete=models.CASCADE,
        related_name='purchases'
    )

    # Purchase Detail
    credits_purchased = models.IntegerField()
    bonus_credits = models.IntegerField(default=0)
    total_credits = models.IntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=20, choices=CreditTransactionStatus.choices, default=CreditTransactionStatus.PENDING)

    # Payment
    payment_method = models.ForeignKey(
        'lipaidox_payment.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    transaction_reference = models.CharField(max_length=255, blank=True, null=True)
    gateway_reference = models.CharField(max_length=255, blank=True, null=True)

    # Timestamps
    purchased_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'credit_purchases'
        ordering = ['-purchased_at']
        indexes = [
            models.Index(fields=['user'], name='idx_purchases_user'),
            models.Index(fields=['credit_type'], name='idx_purchases_type'),
            models.Index(fields=['status'], name='idx_purchases_status'),
            models.Index(fields=['purchased_at'], name='idx_purchases_at'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_purchased__gt=0), name='credits_purchased_check'),
            models.CheckConstraint(
                check=models.Q(total_credits=models.F('credits_purchased') + models.F('bonus_credits')),
                name='total_credits_check'
            ),
            models.CheckConstraint(check=models.Q(amount_paid__gt=0), name='amount_paid_check'),
        ]

    def __str__(self):
        return f"{self.user.username} purchased {self.total_credits} {self.get_credit_type_display()}"


class CreditGift(models.Model):
    """
    Admin-gifted credits to any creator or fan
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gifted_to_user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='credit_gifts'
    )
    gifted_by_admin = models.ForeignKey(
        'lipaidox_admin_panel.AdminAccount',
        on_delete=models.CASCADE,
        related_name='credits_gifted'
    )
    credit_type = models.CharField(max_length=20, choices=CreditType.choices)

    # Gift Detail
    credits_amount = models.IntegerField()
    reason = models.TextField()
    internal_note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')

    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    gifted_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'credit_gifts'
        ordering = ['-gifted_at']
        indexes = [
            models.Index(fields=['gifted_to_user'], name='idx_gifts_user'),
            models.Index(fields=['gifted_by_admin'], name='idx_gifts_admin'),
            models.Index(fields=['credit_type'], name='idx_gifts_type'),
            models.Index(fields=['status'], name='idx_gifts_status'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_amount__gt=0), name='credits_amount_check'),
        ]

    def __str__(self):
        return f"{self.credits_amount} {self.get_credit_type_display()} gifted to {self.gifted_to_user.username}"
