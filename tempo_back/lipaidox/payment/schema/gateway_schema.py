import strawberry
from decimal import Decimal
from datetime import datetime
from typing import Optional


@strawberry.type
class FanWalletType:
    """Viewer/fan spendable money wallet."""
    balance: float
    currency: str
    lifetime_topup: float
    lifetime_spent: float

    @classmethod
    def from_model(cls, wallet) -> "FanWalletType":
        return cls(
            balance=float(wallet.balance),
            currency=wallet.currency,
            lifetime_topup=float(wallet.lifetime_topup),
            lifetime_spent=float(wallet.lifetime_spent),
        )

    @classmethod
    def empty(cls, currency: str = "USD") -> "FanWalletType":
        return cls(balance=0.0, currency=currency, lifetime_topup=0.0, lifetime_spent=0.0)


@strawberry.type
class LedgerEntryType:
    """A row from the platform Transaction ledger, from the current user's view."""
    id: strawberry.ID
    transaction_type: str
    status: str
    gross_amount: float
    net_amount: float
    platform_fee: float
    currency: str
    direction: str  # "debit" (money out) | "credit" (money in)
    description: Optional[str]
    counterparty: Optional[str]
    created_at: datetime

    @classmethod
    def from_model(cls, txn, viewer_user_id) -> "LedgerEntryType":
        # Fan side = money out (debit); creator side = money in (credit).
        is_fan_side = txn.fan_id == viewer_user_id
        counterparty = None
        if is_fan_side and txn.creator_id:
            counterparty = getattr(txn.creator, "username", None)
        return cls(
            id=strawberry.ID(str(txn.id)),
            transaction_type=txn.transaction_type,
            status=txn.status,
            gross_amount=float(txn.gross_amount),
            net_amount=float(txn.net_amount),
            platform_fee=float(txn.platform_fee),
            currency=txn.currency,
            direction="debit" if is_fan_side else "credit",
            description=txn.description,
            counterparty=counterparty,
            created_at=txn.created_at,
        )


@strawberry.type
class TopUpResult:
    success: bool
    message: str
    charge_id: Optional[strawberry.ID]
    charge_status: Optional[str]
    wallet_balance: float
    # Async gateways (NBC card/M-Pesa) can't settle inline. When the charge is
    # still pending, `requires_action` is True and the client must act:
    #  - card  → redirect the browser to `payment_url`
    #  - M-Pesa → poll /payments/status/<order_reference>/ until it settles
    # The wallet is credited by the webhook, not by this mutation.
    requires_action: bool = False
    payment_url: Optional[str] = None
    order_reference: Optional[str] = None


@strawberry.type
class PayoutRequestResult:
    success: bool
    message: str
    amount: float
    status: str
