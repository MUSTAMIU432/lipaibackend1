"""
Is the payment gateway actually able to take real money?

Answers the question the app's "Payments aren't live yet" message is really asking,
without ever exposing the key or creating a charge. The probe is a read-only status
lookup of an order that does not exist: NBC authenticates the key first, so a
`404 Order not found` proves the key is accepted and the portal is reachable, while
`401/403` means the key was rejected — and nothing is created or charged either way.
"""
from __future__ import annotations

from django.conf import settings

from .gateways import nbc_client

# An order reference NBC will never have.
_PROBE_REFERENCE = "healthcheck-no-such-order"


def gateway_health(probe: bool = True) -> dict:
    """
    Returns a dict safe to expose publicly (booleans + labels, never the key):

      gateway        — the gateway selected by PAYMENT_GATEWAY_DEFAULT: "nbc" or "simulated"
      live           — True only when real money can be taken
      keyConfigured  — NBC_API_KEY is set on this server
      reachable      — NBC's portal answered (None when not probed)
      authenticated  — NBC accepted the key (None when not probed)
      problems       — plain-language reasons `live` is False (for operators)
    """
    default = (getattr(settings, "PAYMENT_GATEWAY_DEFAULT", "simulated") or "simulated").strip()
    key_set = bool(getattr(settings, "NBC_API_KEY", ""))
    problems: list[str] = []

    if default != "nbc":
        problems.append(
            f"PAYMENT_GATEWAY_DEFAULT is '{default}', so payments run in SIMULATION mode "
            "(no real money moves). Set PAYMENT_GATEWAY_DEFAULT=nbc."
        )
    if not key_set:
        problems.append("NBC_API_KEY is empty on this server.")

    reachable = authenticated = None
    if default == "nbc" and key_set and probe:
        try:
            nbc_client.get_payment(_PROBE_REFERENCE, timeout=8)
            reachable = authenticated = True  # unexpected 200, but the key clearly works
        except nbc_client.NbcError as exc:
            if exc.status == 404:
                reachable = authenticated = True
            elif exc.status in (401, 403):
                reachable, authenticated = True, False
                problems.append(
                    f"NBC rejected the API key (HTTP {exc.status}). Check NBC_API_KEY, and "
                    "whether the key is restricted to specific server IPs."
                )
            elif exc.status == 502:
                reachable, authenticated = False, None
                problems.append(f"Could not reach NBC at {getattr(settings, 'NBC_API_BASE', '')}: {exc}")
            else:
                reachable, authenticated = True, None
                problems.append(f"NBC answered HTTP {exc.status}: {exc}")

    configured = default == "nbc" and key_set
    live = configured and (authenticated is True if probe else True)

    return {
        "gateway": "nbc" if default == "nbc" else "simulated",
        "live": live,
        "keyConfigured": key_set,
        "reachable": reachable,
        "authenticated": authenticated,
        "walletCurrency": getattr(settings, "NBC_CURRENCY", ""),
        "settlementCurrency": getattr(settings, "NBC_SETTLEMENT_CURRENCY", ""),
        "redirectUrlConfigured": bool(getattr(settings, "NBC_REDIRECT_URL", "")),
        "problems": problems,
    }
