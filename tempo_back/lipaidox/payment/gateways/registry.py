from typing import Optional

from django.conf import settings

from . import PaymentGateway
from .simulated import SimulatedGateway
from .nbc import NbcGateway

_GATEWAYS = {
    SimulatedGateway.code: SimulatedGateway,
    NbcGateway.code: NbcGateway,
}


def register_gateway(gateway_cls) -> None:
    """Register a new PaymentGateway implementation (Daraja/Stripe later)."""
    _GATEWAYS[gateway_cls.code] = gateway_cls


def get_gateway(code: Optional[str] = None) -> PaymentGateway:
    """Resolve the active gateway. Defaults to settings.PAYMENT_GATEWAY_DEFAULT
    ('simulated' when unset)."""
    code = code or getattr(settings, "PAYMENT_GATEWAY_DEFAULT", "simulated")
    gateway_cls = _GATEWAYS.get(code, SimulatedGateway)
    return gateway_cls()
