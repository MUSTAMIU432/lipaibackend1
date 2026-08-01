"""
NBC / Haminass Pay gateway — the async provider behind the PaymentGateway seam.

Unlike ``SimulatedGateway`` (settles instantly), NBC is asynchronous: ``create_charge``
records a ``pending`` Charge and returns a hosted-page URL (card) or just a
reference (M-Pesa STK push). The Charge only becomes ``succeeded`` when the
webhook at ``/payments/callback/nbc/`` fires — or when a status poll confirms it —
at which point ``fulfill_charge`` runs (funding the wallet). Business logic never
changes: it still funds wallets through this one seam.
"""
import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings

from lipaidox.payment.models import Charge, ChargePurpose, ChargeStatus
from . import PaymentGateway
from . import nbc_client

logger = logging.getLogger(__name__)


def usd_to_tzs(amount: Decimal) -> Decimal:
    """Convert a USD amount to TZS using the configured reference rate.
    M-Pesa charges and mobile-money payouts must be quoted in TZS."""
    rate = Decimal(str(getattr(settings, "NBC_USD_TO_TZS", 2600) or 2600))
    return (Decimal(str(amount)) * rate).quantize(Decimal("0.01"))


def _settlement_currency() -> str:
    return (getattr(settings, "NBC_SETTLEMENT_CURRENCY", "TZS") or "TZS").upper()


def _to_settlement(amount: Decimal, currency: str) -> tuple[Decimal, str]:
    """Convert a wallet-currency amount into the currency NBC is settled in.

    The key is provisioned for one market, so *every* leg (card as well as
    M-Pesa) must be quoted in it — NBC 502s otherwise. Only the wire amount
    changes; the Charge row keeps ``currency`` so the wallet is credited in USD.
    """
    target = _settlement_currency()
    amount = Decimal(str(amount))
    if (currency or "").upper() == target:
        return amount, target
    if target == "TZS":
        return usd_to_tzs(amount), target
    # No rate configured for any other target — send as-is and let NBC decide.
    return amount, target


def _normalize_status(raw) -> str:
    s = str(raw or "").upper()
    if s in {"PAID", "COMPLETE", "COMPLETED", "SUCCESS", "SUCCESSFUL"}:
        return ChargeStatus.SUCCEEDED
    if s in {"PENDING", "PROCESSING", "INITIATED"}:
        return ChargeStatus.PENDING
    if s in {"FAILED", "CANCELLED", "CANCELED", "DECLINED", "EXPIRED"}:
        return ChargeStatus.FAILED
    # REFUNDED / PARTIALLY_REFUNDED / unknown → leave the charge as-is.
    return ChargeStatus.PENDING


class NbcGateway(PaymentGateway):
    code = "nbc"

    def create_charge(
        self,
        *,
        user,
        amount: Decimal,
        currency: str = None,
        purpose: str = ChargePurpose.WALLET_TOPUP,
        metadata: Optional[dict] = None,
    ) -> Charge:
        metadata = dict(metadata or {})
        method = "mpesa" if str(metadata.get("method", "")).lower() == "mpesa" else "card"
        currency = (currency or settings.NBC_CURRENCY or "TZS").upper()

        # Create the pending Charge first so we have a stable id to use as the
        # idempotency key — retrying with the same id can't double-charge.
        charge = Charge.objects.create(
            user=user,
            tenant=getattr(user, "tenant", None),
            gateway=self.code,
            amount=Decimal(str(amount)),
            currency=currency,
            purpose=purpose,
            status=ChargeStatus.PENDING,
            metadata={**metadata, "method": method},
        )

        # The API key is provisioned for one settlement currency (TZS) and rejects
        # anything else, so both card and M-Pesa go on the wire converted. The
        # wallet-facing Charge row stays in its own currency (USD) — fulfillment
        # still credits the wallet in USD.
        send_amount, send_currency = _to_settlement(charge.amount, currency)

        redirect_url = metadata.get("redirect_url") or settings.NBC_REDIRECT_URL or None
        call = dict(
            amount=send_amount,
            currency=send_currency,
            idempotency_key=f"charge-{charge.id}",
            method=method,
            email=getattr(user, "email", None),
            phone=metadata.get("phone"),
        )
        try:
            try:
                result = nbc_client.create_payment(**call, redirect_url=redirect_url)
            except nbc_client.NbcError as exc:
                # NBC 403s when the redirect host isn't pre-approved on the key.
                # Retry without it rather than failing the payment — NBC then uses
                # its own return page and the status poll still settles the charge.
                if not (redirect_url and exc.status == 403 and "redirect_url" in str(exc)):
                    raise
                logger.warning(
                    "NBC rejected redirect_url %s (%s) — retrying without it", redirect_url, exc
                )
                # A new idempotency key: the rejected attempt already consumed the old one.
                call["idempotency_key"] = f"charge-{charge.id}-noredirect"
                result = nbc_client.create_payment(**call, redirect_url=None)
                redirect_url = None
        except nbc_client.NbcError as exc:
            charge.status = ChargeStatus.FAILED
            charge.metadata = {**charge.metadata, "error": str(exc)}
            charge.save(update_fields=["status", "metadata", "updated_at"])
            raise

        order_reference = str(result.get("orderReference") or "")
        charge.provider_ref = order_reference
        charge.status = _normalize_status(result.get("status"))
        charge.metadata = {
            **charge.metadata,
            "payment_url": result.get("paymentPageUrl"),
            "order_reference": order_reference,
            # M-Pesa returns a human-readable prompt message instead of a page URL.
            "gateway_message": result.get("message"),
            "sent_amount": str(send_amount),
            "sent_currency": send_currency,
            "redirect_url": redirect_url,
        }
        charge.save(update_fields=["provider_ref", "status", "metadata", "updated_at"])
        return charge

    # ── Async settlement ──────────────────────────────────────────────────────

    def verify_and_settle(self, charge: Charge) -> Charge:
        """Re-check a pending charge against NBC and fulfill it if now PAID.
        Safe to call repeatedly — fulfillment runs at most once (idempotent)."""
        if charge.status == ChargeStatus.SUCCEEDED:
            return charge
        if not charge.provider_ref:
            return charge
        try:
            record = nbc_client.get_payment(charge.provider_ref)
        except nbc_client.NbcError as exc:
            logger.warning("NBC verify failed for charge %s: %s", charge.id, exc)
            return charge

        new_status = _normalize_status(record.get("status"))
        if new_status == ChargeStatus.SUCCEEDED and charge.status != ChargeStatus.SUCCEEDED:
            from lipaidox.payment.fulfillment import fulfill_charge
            fulfill_charge(charge)  # transitions to SUCCEEDED + funds the wallet
        elif new_status == ChargeStatus.FAILED and charge.status == ChargeStatus.PENDING:
            charge.status = ChargeStatus.FAILED
            charge.save(update_fields=["status", "updated_at"])
        return charge

    def handle_callback(self, request) -> Optional[Charge]:
        """Resolve the pending Charge referenced by an NBC webhook."""
        ref = _reference_from_request(request)
        if not ref:
            return None
        charge = Charge.objects.filter(gateway=self.code, provider_ref=ref).first()
        if not charge:
            logger.info("NBC webhook: no charge for reference %s", ref)
            return None
        return self.verify_and_settle(charge)

    # ── Refunds & payouts ──────────────────────────────────────────────────────

    supports_payouts = True

    def refund_charge(self, charge: Charge, *, amount=None, reason: Optional[str] = None) -> dict:
        """Refund all (``amount=None``) or part of a settled charge. Returns NBC's
        raw refund result. Raises ``nbc_client.NbcError`` (NBC refunds are disabled
        today, so this surfaces that instead of faking one)."""
        if not charge.provider_ref:
            raise nbc_client.NbcError("This charge has no gateway reference to refund", status=400)
        return nbc_client.refund_payment(charge.provider_ref, amount=amount, reason=reason)

    def create_payout(
        self,
        *,
        recipient_name: str,
        recipient_identifier: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
        reason: Optional[str] = None,
    ) -> dict:
        """Send money out via NBC. TZS payouts (mobile money) are converted from
        the USD balance; USD passes through. Returns NBC's raw ``{reference, status}``.
        Raises ``nbc_client.NbcError`` (payouts are disabled today)."""
        send_currency = (currency or "TZS").upper()
        send_amount = usd_to_tzs(amount) if send_currency == "TZS" else Decimal(str(amount))
        return nbc_client.create_payout(
            recipient_name=recipient_name,
            recipient_identifier=recipient_identifier,
            amount=send_amount,
            currency=send_currency,
            idempotency_key=idempotency_key,
            reason=reason,
        )

    def verify_payout(self, reference: str) -> dict:
        """Re-check a payout's status with NBC. Raises ``nbc_client.NbcError``."""
        return nbc_client.get_payout(reference)


def _reference_from_request(request) -> Optional[str]:
    """Pull the order reference from a webhook body or query, tolerating shapes."""
    import json

    for key in ("orderReference", "order_reference", "reference", "ref"):
        val = request.GET.get(key)
        if val:
            return val
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        body = {}
    if isinstance(body, dict):
        for key in ("orderReference", "order_reference", "reference", "ref"):
            if body.get(key):
                return str(body[key])
        data = body.get("data")
        if isinstance(data, dict):
            for key in ("orderReference", "order_reference", "reference", "ref"):
                if data.get(key):
                    return str(data[key])
    return None
