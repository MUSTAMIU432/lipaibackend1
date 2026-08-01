import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ChargePurpose(models.TextChoices):
    """Why a gateway charge was created."""
    WALLET_TOPUP = 'wallet_topup', 'Wallet Top-up'
    PPV = 'ppv', 'PPV Purchase'
    CREDITS = 'credits', 'Credit Purchase'
    LIVE_ENTRY = 'live_entry', 'Live Entry'
    SUBSCRIPTION = 'subscription', 'Subscription'


class ChargeStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SUCCEEDED = 'succeeded', 'Succeeded'
    FAILED = 'failed', 'Failed'


class Charge(TenantAwareModel):
    """
    A single funding attempt through a payment gateway.

    The simulated gateway settles instantly (pending -> succeeded/failed). Async
    providers (M-Pesa Daraja, Stripe) stay `pending` until their webhook hits
    ``payments/callback/<gateway>/`` and transitions the row. Business logic never
    talks to a provider directly — it only reads the resulting Charge status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='charges',
    )
    gateway = models.CharField(max_length=30, default='simulated')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    # Wallet stays USD-denominated. A Daraja charge would record currency='KES'
    # here while converting to USD before crediting the wallet.
    currency = models.CharField(max_length=10, default='USD')
    purpose = models.CharField(
        max_length=30, choices=ChargePurpose.choices, default=ChargePurpose.WALLET_TOPUP,
    )
    status = models.CharField(
        max_length=20, choices=ChargeStatus.choices, default=ChargeStatus.PENDING,
    )
    provider_ref = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'charges'
        app_label = 'lipaidox_payment'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user'], name='idx_charge_user'),
            models.Index(fields=['status'], name='idx_charge_status'),
            models.Index(fields=['purpose'], name='idx_charge_purpose'),
        ]

    def __str__(self):
        return f"Charge {self.amount} {self.currency} [{self.status}] ({self.gateway})"

    @property
    def succeeded(self) -> bool:
        return self.status == ChargeStatus.SUCCEEDED
