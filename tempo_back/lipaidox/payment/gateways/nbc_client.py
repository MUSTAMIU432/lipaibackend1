"""
NBC / Haminass Pay HTTP client.

The single place that holds ``settings.NBC_API_KEY`` and knows the gateway's
wire format. Business logic never imports this — it goes through ``NbcGateway``
(the PaymentGateway seam), which returns provider-agnostic ``Charge`` rows.

Docs: POST /api/v1/payments · GET /api/v1/payments/<ref> · GET /api/v1/payments
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NbcError(Exception):
    """A gateway call failed. ``status`` mirrors NBC's HTTP status when known."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _base() -> str:
    return (settings.NBC_API_BASE or "https://accesspay.eopsprimax.com").rstrip("/")


def _headers(extra: Optional[dict] = None) -> dict:
    key = settings.NBC_API_KEY
    if not key:
        raise NbcError("NBC_API_KEY is not configured on the server", status=500)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    return headers


def _units(amount) -> float:
    """NBC takes normal currency units, not cents (5000 == 5,000 TZS; 4.99 == $4.99).
    NBC converts to the smallest unit internally, so we keep 2-decimal precision
    rather than rounding to whole numbers (which would drop USD cents)."""
    n = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(n)


def _error_message(resp: requests.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and isinstance(body.get("error"), str):
            return body["error"]
    except ValueError:
        pass
    return f"Gateway responded {resp.status_code}"


def create_payment(
    *,
    amount,
    currency: str,
    idempotency_key: str,
    method: str = "card",
    email: Optional[str] = None,
    phone: Optional[str] = None,
    redirect_url: Optional[str] = None,
    timeout: int = 20,
) -> dict:
    """
    Create a card or M-Pesa charge. Returns NBC's raw
    ``{orderReference, paymentPageUrl, status}``. Raises ``NbcError`` on failure.
    """
    payload = {"amount": _units(amount), "currency": (currency or "TZS").upper()}
    if method == "mpesa":
        payload["payment_method"] = "mpesa"
        if phone:
            # NBC's M-Pesa spec names this field `phone_number` and accepts a
            # Tanzanian MSISDN as digits (0712345678 or 255712345678).
            payload["phone_number"] = "".join(ch for ch in str(phone) if ch.isdigit())
    if email:
        payload["email"] = email
    if redirect_url:
        payload["redirect_url"] = redirect_url

    try:
        resp = requests.post(
            f"{_base()}/api/v1/payments",
            json=payload,
            headers=_headers({"Idempotency-Key": idempotency_key}),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("NBC create_payment network error: %s", exc)
        raise NbcError("Could not reach the payment gateway", status=502)

    if resp.status_code != 200:
        raise NbcError(_error_message(resp), status=resp.status_code)
    return resp.json()


def get_payment(order_reference: str, *, timeout: int = 15) -> dict:
    """Fetch one payment's current status. Raises ``NbcError`` on failure."""
    try:
        resp = requests.get(
            f"{_base()}/api/v1/payments/{order_reference}",
            headers=_headers(),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("NBC get_payment network error: %s", exc)
        raise NbcError("Could not reach the payment gateway", status=502)

    if resp.status_code != 200:
        raise NbcError(_error_message(resp), status=resp.status_code)
    return resp.json()


def refund_payment(
    order_reference: str,
    *,
    amount=None,
    reason: Optional[str] = None,
    timeout: int = 20,
) -> dict:
    """
    Refund all (``amount=None``) or part of a paid order. Returns NBC's raw
    ``{orderReference, status, refundedAmount, totalAmount}``. Raises ``NbcError``.

    NBC's refund endpoint is disabled today — this will surface that provider
    error rather than pretend a refund happened.
    """
    payload: dict = {}
    if amount is not None:
        payload["amount"] = _units(amount)
    if reason:
        payload["reason"] = reason
    try:
        resp = requests.post(
            f"{_base()}/api/v1/payments/{order_reference}/refund",
            json=payload,
            headers=_headers(),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("NBC refund_payment network error: %s", exc)
        raise NbcError("Could not reach the payment gateway", status=502)

    if resp.status_code != 200:
        raise NbcError(_error_message(resp), status=resp.status_code)
    return resp.json()


# ── Payouts (money out, not tied to an order) ─────────────────────────────────

def create_payout(
    *,
    recipient_name: str,
    recipient_identifier: str,
    amount,
    currency: str,
    idempotency_key: str,
    reason: Optional[str] = None,
    timeout: int = 20,
) -> dict:
    """
    Send money to a recipient directly (M-Pesa MSISDN, bank account, or IBAN).
    Returns NBC's raw ``{reference, status}`` (``status`` is ``SENT`` / ``FAILED``).
    Raises ``NbcError`` on a non-200 — the ``502`` body carries a ``reference``
    and ``status: FAILED`` which the caller can read off the exception if needed.

    NBC's payouts endpoint is disabled today — this surfaces that error rather
    than reporting a transfer that never happened.
    """
    payload = {
        "recipient_name": recipient_name,
        "recipient_identifier": recipient_identifier,
        "amount": _units(amount),
        "currency": (currency or "TZS").upper(),
    }
    if reason:
        payload["reason"] = reason
    try:
        resp = requests.post(
            f"{_base()}/api/v1/payouts",
            json=payload,
            headers=_headers({"Idempotency-Key": idempotency_key}),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("NBC create_payout network error: %s", exc)
        raise NbcError("Could not reach the payout gateway", status=502)

    if resp.status_code != 200:
        raise NbcError(_error_message(resp), status=resp.status_code)
    return resp.json()


def get_payout(reference: str, *, timeout: int = 15) -> dict:
    """Fetch one payout's current status. Raises ``NbcError`` on failure."""
    try:
        resp = requests.get(
            f"{_base()}/api/v1/payouts/{reference}",
            headers=_headers(),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("NBC get_payout network error: %s", exc)
        raise NbcError("Could not reach the payout gateway", status=502)

    if resp.status_code != 200:
        raise NbcError(_error_message(resp), status=resp.status_code)
    return resp.json()
