"""
REST surface for the async gateway — the parts that can't be GraphQL:

- ``payments/callback/<gateway>/`` — the provider's server-to-server webhook.
  It carries no user JWT, so it's CSRF-exempt and auth-free; trust comes from
  re-verifying the charge against the provider before granting anything.
- ``payments/status/<order_reference>/`` — a JSON status probe the SPA polls
  (M-Pesa has no redirect). It reads the fan's own charge and re-checks the
  provider, so the secret key never reaches the browser.
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from lipaidox.payment.gateways.registry import get_gateway
from lipaidox.payment.models import Charge

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST", "GET"])
def gateway_callback(request, gateway: str):
    """Provider webhook. Resolves + settles the referenced charge, then 200s so
    the provider stops retrying. Always 200 on a well-formed hit — settlement is
    idempotent, and a 500 would make the provider hammer us."""
    try:
        gw = get_gateway(gateway)
        charge = gw.handle_callback(request)
    except Exception as exc:  # never leak a 500 back to the provider
        logger.exception("gateway_callback(%s) error: %s", gateway, exc)
        return JsonResponse({"received": True}, status=200)

    return JsonResponse(
        {"received": True, "status": getattr(charge, "status", None)},
        status=200,
    )


@require_http_methods(["GET"])
def gateway_status(request, order_reference: str):
    """SPA poll target for M-Pesa / card return. Re-verifies against the provider
    and returns the settled status. No secret crosses to the browser."""
    charge = Charge.objects.filter(provider_ref=order_reference).first()
    if not charge:
        return JsonResponse({"error": "Unknown reference"}, status=404)

    gw = get_gateway(charge.gateway)
    verify = getattr(gw, "verify_and_settle", None)
    if callable(verify):
        charge = verify(charge)

    return JsonResponse(
        {
            "orderReference": order_reference,
            "status": charge.status,
            "purpose": charge.purpose,
            "amount": str(charge.amount),
            "currency": charge.currency,
        },
        status=200,
    )
