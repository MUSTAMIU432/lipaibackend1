import strawberry
from decimal import Decimal
from typing import Optional

from lipaidox.payment.gateways.registry import get_gateway
from lipaidox.payment.gateways import nbc_client
from lipaidox.payment.models import ChargePurpose, ChargeStatus, PaymentMethod, PaymentMethodType
from lipaidox.wallet.services import credit_fan_wallet, get_or_create_fan_wallet
from lipaidox.wallet.models import Transaction, TransactionType, TransactionStatus
from ..schema.gateway_schema import TopUpResult, PayoutRequestResult


def _auth(info):
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def _recipient_from_method(method: PaymentMethod):
    """Map a creator's payout method to the (name, identifier, currency) NBC's
    payout API needs. Returns identifier=None when the method has no usable
    destination (e.g. a bank method with only a tokenized/last4 account)."""
    currency = (method.payout_currency or "USD").upper()
    if method.method_type == PaymentMethodType.MOBILE_MONEY:
        digits = "".join(ch for ch in (
            (method.mobile_money_phone_country_code or "") + (method.mobile_money_phone_number or "")
        ) if ch.isdigit())
        name = method.mobile_money_account_name or method.creator.username
        return name, (digits or None), currency
    if method.method_type == PaymentMethodType.BANK_TRANSFER:
        # Only the IBAN is stored in the clear; the account number is encrypted
        # (last4 only), so IBAN is the one identifier we can send today.
        name = method.bank_account_holder_name or method.creator.username
        return name, (method.bank_iban or None), currency
    # Cards are not a payout destination.
    return None, None, currency


@strawberry.type
class GatewayMutation:
    @strawberry.mutation
    def top_up_wallet(
        self,
        info: strawberry.types.Info,
        amount: float,
        currency: str = "USD",
        method: Optional[str] = None,
        simulate: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> TopUpResult:
        """Fund the fan wallet via the active gateway. Simulated gateway settles
        instantly; pass simulate='fail' to exercise the failure path."""
        user = _auth(info)
        amt = Decimal(str(amount))
        if amt <= 0:
            return TopUpResult(
                success=False, message="Amount must be positive",
                charge_id=None, charge_status=None,
                wallet_balance=float(get_or_create_fan_wallet(user, currency).balance),
            )

        gateway = get_gateway()
        metadata = {}
        if method:
            metadata["method"] = method
        if simulate:
            metadata["simulate"] = simulate
        if phone:
            metadata["phone"] = phone

        try:
            charge = gateway.create_charge(
                user=user, amount=amt, currency=currency,
                purpose=ChargePurpose.WALLET_TOPUP, metadata=metadata,
            )
        except Exception as exc:
            # A real gateway can reject at creation (bad amount, unapproved
            # redirect host, provider down). Surface its message, don't 500.
            return TopUpResult(
                success=False, message=str(exc) or "Payment could not be started",
                charge_id=None, charge_status="failed",
                wallet_balance=float(get_or_create_fan_wallet(user, currency).balance),
            )

        # Async gateway (NBC): charge is pending — hand the client the next action.
        if charge.status == ChargeStatus.PENDING:
            return TopUpResult(
                success=True,
                message="Complete your payment to fund your wallet",
                charge_id=strawberry.ID(str(charge.id)),
                charge_status=charge.status,
                wallet_balance=float(get_or_create_fan_wallet(user, currency).balance),
                requires_action=True,
                payment_url=charge.metadata.get("payment_url"),
                order_reference=charge.metadata.get("order_reference"),
            )

        if charge.status != ChargeStatus.SUCCEEDED:
            return TopUpResult(
                success=False, message="Payment failed",
                charge_id=strawberry.ID(str(charge.id)), charge_status=charge.status,
                wallet_balance=float(get_or_create_fan_wallet(user, currency).balance),
            )

        # Synchronous gateway (simulated): wallet funded inline.
        wallet = credit_fan_wallet(user, amt, currency)
        return TopUpResult(
            success=True, message="Wallet topped up",
            charge_id=strawberry.ID(str(charge.id)), charge_status=charge.status,
            wallet_balance=float(wallet.balance),
        )

    @strawberry.mutation
    def request_payout(
        self, info: strawberry.types.Info, amount: float, method_id: Optional[strawberry.ID] = None
    ) -> PayoutRequestResult:
        """Pay a creator out to their chosen method through the active gateway.

        When NBC is the gateway it resolves the recipient from the PaymentMethod
        and calls ``/api/v1/payouts`` (SENT → completed, else failed). On the
        simulated gateway — or when the method has no usable destination — it
        records a PENDING intent and moves no money. Never reports a transfer
        that didn't happen."""
        user = _auth(info)
        profile = getattr(user, "profile", None)
        if profile is None:
            return PayoutRequestResult(
                success=False, message="Only creators can request payouts",
                amount=amount, status="failed",
            )
        amt = Decimal(str(amount))
        if amt <= 0:
            return PayoutRequestResult(
                success=False, message="Amount must be positive", amount=amount, status="failed",
            )

        # Resolve the destination: the named method (must belong to this creator)
        # or their primary/first one.
        method = None
        if method_id:
            method = PaymentMethod.objects.filter(id=method_id, creator=profile).first()
            if method is None:
                return PayoutRequestResult(
                    success=False, message="Payout method not found", amount=amount, status="failed",
                )
        else:
            method = (
                PaymentMethod.objects.filter(creator=profile, is_primary=True).first()
                or PaymentMethod.objects.filter(creator=profile).first()
            )
        if method is None:
            return PayoutRequestResult(
                success=False, message="Add a payout method first", amount=amount, status="failed",
            )

        recipient_name, recipient_identifier, currency = _recipient_from_method(method)

        gateway = get_gateway()
        can_pay_out = bool(getattr(gateway, "supports_payouts", False)) and recipient_identifier

        # Simulated gateway, or no usable destination → record the intent only.
        if not can_pay_out:
            txn = Transaction.objects.create(
                fan=None, creator=profile, tenant=getattr(user, "tenant", None),
                payment_method=method,
                transaction_type=TransactionType.PAYOUT, status=TransactionStatus.PENDING,
                gross_amount=amt, platform_fee_percent=0, platform_fee=0, net_amount=amt,
                currency="USD", description="Payout request",
            )
            return PayoutRequestResult(
                success=True, message="Payout requested", amount=float(amt), status=txn.status,
            )

        # Real payout via NBC. Create the ledger row first so its id is the stable
        # idempotency key — a retry can't double-send.
        txn = Transaction.objects.create(
            fan=None, creator=profile, tenant=getattr(user, "tenant", None),
            payment_method=method,
            transaction_type=TransactionType.PAYOUT, status=TransactionStatus.PENDING,
            gross_amount=amt, platform_fee_percent=0, platform_fee=0, net_amount=amt,
            currency="USD", description="Payout request",
        )
        try:
            result = gateway.create_payout(
                recipient_name=recipient_name,
                recipient_identifier=recipient_identifier,
                amount=amt,
                currency=currency,
                idempotency_key=f"payout-{txn.id}",
                reason="Creator payout",
            )
        except nbc_client.NbcError as exc:
            txn.status = TransactionStatus.FAILED
            txn.gateway_response = {"error": str(exc)}
            txn.save(update_fields=["status", "gateway_response", "updated_at"])
            return PayoutRequestResult(
                success=False, message=str(exc) or "Payout failed",
                amount=float(amt), status=txn.status,
            )

        sent = str(result.get("status") or "").upper() == "SENT"
        txn.status = TransactionStatus.COMPLETED if sent else TransactionStatus.FAILED
        txn.gateway_reference = str(result.get("reference") or "")
        txn.gateway_response = result
        txn.save(update_fields=["status", "gateway_reference", "gateway_response", "updated_at"])
        return PayoutRequestResult(
            success=sent,
            message="Payout sent" if sent else "Payout was not accepted",
            amount=float(amt), status=txn.status,
        )
