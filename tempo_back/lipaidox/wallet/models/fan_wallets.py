import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class FanWallet(TenantAwareModel):
    """
    Viewer/fan spendable money wallet (USD).

    Funded by gateway top-ups and spent on PPV unlocks, live entry fees, and
    subscriptions. It is the money source that gets debited before a creator
    wallet is credited (net of platform fee) via ``wallet.services.settle``.
    Distinct from ``FanCreditWallet`` (live-stream credits) in the credits app.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='fan_wallets',
    )
    currency = models.CharField(max_length=10, default='USD')

    balance = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    lifetime_topup = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    lifetime_spent = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fan_wallets'
        app_label = 'lipaidox_wallet'
        indexes = [
            models.Index(fields=['user'], name='idx_fan_wallet_user'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['user', 'currency'], name='fan_wallets_unique'),
            models.CheckConstraint(check=models.Q(balance__gte=0), name='fan_wallet_balance_check'),
        ]

    def __str__(self):
        return f"FanWallet: {self.user_id} - {self.balance} {self.currency}"

    def credit(self, amount):
        """Add funds (top-up). Caller is responsible for locking."""
        self.balance += amount
        self.lifetime_topup += amount
        self.save(update_fields=['balance', 'lifetime_topup', 'updated_at'])

    def debit(self, amount):
        """Spend funds. Raises ValueError if insufficient. Caller must lock."""
        if amount > self.balance:
            raise ValueError("Insufficient wallet balance")
        self.balance -= amount
        self.lifetime_spent += amount
        self.save(update_fields=['balance', 'lifetime_spent', 'updated_at'])
