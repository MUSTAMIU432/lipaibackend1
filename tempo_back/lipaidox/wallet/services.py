"""
Money-movement choke point.

Every purchase in the platform (PPV, live entry, subscriptions, credit packs) and
every top-up goes through these functions so ledger rows, wallet balances, and fee
splits stay consistent. All balance mutations are atomic and row-locked.

Design: the fan money wallet (``FanWallet``) is the single source of spend. A
"gateway" purchase is modelled as top-up-then-spend (``credit_fan_wallet`` then a
settle/spend), so the provider integration only ever funds a wallet and never
touches business logic.
"""
from decimal import Decimal
from typing import Optional, Tuple

from django.db import transaction as db_transaction

from .models import (
    CreatorWallet,
    FanWallet,
    Transaction,
    TransactionType,
    TransactionStatus,
    WalletTransactionType,
)


class InsufficientFunds(Exception):
    """Raised when a fan wallet cannot cover a spend."""


# Platform transaction type -> creator earning bucket on CreatorWallet.
_EARNING_TYPE = {
    TransactionType.PPV_PURCHASE: WalletTransactionType.PPV_EARNING,
    TransactionType.SUBSCRIPTION: WalletTransactionType.SUBSCRIPTION_EARNING,
    TransactionType.TIP: WalletTransactionType.TIP_EARNING,
    TransactionType.LIVE_ENTRY: WalletTransactionType.LIVE_STREAM_EARNING,
    TransactionType.CREDIT_PURCHASE: WalletTransactionType.CREDIT_GIFT_EARNING,
}


def get_or_create_fan_wallet(user, currency: str = "USD") -> FanWallet:
    wallet, _ = FanWallet.objects.get_or_create(
        user=user,
        currency=currency,
        defaults={"tenant": getattr(user, "tenant", None)},
    )
    return wallet


def get_or_create_creator_wallet(profile, currency: str = "USD") -> CreatorWallet:
    wallet, _ = CreatorWallet.objects.get_or_create(
        creator=profile,
        currency=currency,
        defaults={"tenant": getattr(profile, "tenant", None)},
    )
    return wallet


def credit_fan_wallet(user, amount, currency: str = "USD") -> FanWallet:
    """Top-up: add funds to the fan wallet (called after a successful Charge)."""
    amount = Decimal(str(amount))
    with db_transaction.atomic():
        wallet = get_or_create_fan_wallet(user, currency)
        wallet = FanWallet.objects.select_for_update().get(pk=wallet.pk)
        wallet.credit(amount)
    return wallet


def _write_transaction(*, fan, creator, gross, fee_percent, tx_type,
                       currency, description, metadata, **source_refs) -> Transaction:
    gross = Decimal(str(gross))
    fee_percent = Decimal(str(fee_percent or 0))
    platform_fee = (gross * fee_percent / Decimal("100")).quantize(Decimal("0.01"))
    net_amount = gross - platform_fee
    return Transaction.objects.create(
        fan=fan,
        creator=creator,
        tenant=getattr(fan, "tenant", None),
        transaction_type=tx_type,
        status=TransactionStatus.COMPLETED,
        gross_amount=gross,
        platform_fee_percent=fee_percent,
        platform_fee=platform_fee,
        net_amount=net_amount,
        currency=currency,
        description=description,
        metadata=metadata or {},
        **source_refs,
    )


def settle(
    *,
    fan_user,
    creator_profile,
    gross,
    fee_percent,
    tx_type,
    currency: str = "USD",
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    **source_refs,
) -> Tuple[FanWallet, Transaction]:
    """
    Move ``gross`` from the fan wallet to the creator wallet, net of platform fee.

    Atomic + row-locked on both wallets. Raises ``InsufficientFunds`` if the fan
    cannot cover it. Writes one completed ``Transaction`` ledger row and adds the
    net amount to the creator's pending balance. Returns (fan_wallet, transaction).
    """
    gross = Decimal(str(gross))
    with db_transaction.atomic():
        fan_wallet = get_or_create_fan_wallet(fan_user, currency)
        fan_wallet = FanWallet.objects.select_for_update().get(pk=fan_wallet.pk)
        if fan_wallet.balance < gross:
            raise InsufficientFunds(
                f"Wallet balance {fan_wallet.balance} < required {gross}"
            )
        fan_wallet.debit(gross)

        txn = _write_transaction(
            fan=fan_user,
            creator=creator_profile,
            gross=gross,
            fee_percent=fee_percent,
            tx_type=tx_type,
            currency=currency,
            description=description,
            metadata=metadata,
            **source_refs,
        )

        if creator_profile is not None:
            creator_wallet = get_or_create_creator_wallet(creator_profile, currency)
            creator_wallet = CreatorWallet.objects.select_for_update().get(
                pk=creator_wallet.pk
            )
            earning_type = _EARNING_TYPE.get(tx_type, WalletTransactionType.ADJUSTMENT)
            creator_wallet.add_pending_earning(txn.net_amount, earning_type)

    return fan_wallet, txn


def spend_fan_to_platform(
    *,
    fan_user,
    amount,
    tx_type,
    currency: str = "USD",
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    **source_refs,
) -> Tuple[FanWallet, Transaction]:
    """
    Debit the fan wallet for a platform-side purchase with no creator counterparty
    (e.g. buying a credit pack). Same guarantees as ``settle`` minus the creator leg.
    """
    amount = Decimal(str(amount))
    with db_transaction.atomic():
        fan_wallet = get_or_create_fan_wallet(fan_user, currency)
        fan_wallet = FanWallet.objects.select_for_update().get(pk=fan_wallet.pk)
        if fan_wallet.balance < amount:
            raise InsufficientFunds(
                f"Wallet balance {fan_wallet.balance} < required {amount}"
            )
        fan_wallet.debit(amount)
        txn = _write_transaction(
            fan=fan_user,
            creator=None,
            gross=amount,
            fee_percent=0,
            tx_type=tx_type,
            currency=currency,
            description=description,
            metadata=metadata,
            **source_refs,
        )
    return fan_wallet, txn


def credit_creator_from_credits(
    *,
    fan_user,
    creator_profile,
    gross,
    fee_percent,
    currency: str = "USD",
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    **source_refs,
) -> Transaction:
    """
    Record a credits-funded gift as creator earnings. The credit balance is
    debited by the caller (FanCreditWallet.use_credits); this only credits the
    creator wallet + writes the ledger row (money already collected at credit-buy).
    """
    with db_transaction.atomic():
        txn = _write_transaction(
            fan=fan_user,
            creator=creator_profile,
            gross=gross,
            fee_percent=fee_percent,
            tx_type=TransactionType.TIP,
            currency=currency,
            description=description,
            metadata=metadata,
            **source_refs,
        )
        creator_wallet = get_or_create_creator_wallet(creator_profile, currency)
        creator_wallet = CreatorWallet.objects.select_for_update().get(
            pk=creator_wallet.pk
        )
        creator_wallet.add_pending_earning(
            txn.net_amount, WalletTransactionType.CREDIT_GIFT_EARNING
        )
    return txn
