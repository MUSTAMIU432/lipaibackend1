from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from lipaidox.payment.models import Charge, ChargePurpose


class PaymentGateway(ABC):
    """
    Provider-agnostic charge interface.

    The whole platform funds wallets through this one seam; business logic (PPV,
    credits, subscriptions, live entry) never talks to a provider directly — it
    calls ``create_charge`` and reads the resulting Charge status. To add M-Pesa
    Daraja or Stripe later, implement this ABC and register it in ``registry.py``;
    no caller changes.

    Currency note: the simulated gateway keeps everything USD. A DarajaGateway
    would charge KES, record ``currency='KES'`` on the Charge, and convert to USD
    before the wallet is credited.
    """
    code = "base"

    @abstractmethod
    def create_charge(
        self,
        *,
        user,
        amount: Decimal,
        currency: str = "USD",
        purpose: str = ChargePurpose.WALLET_TOPUP,
        metadata: Optional[dict] = None,
    ) -> Charge:
        """Create (and, for synchronous gateways, settle) a Charge row."""
        ...

    def handle_callback(self, request) -> Optional[Charge]:
        """Async providers resolve a pending Charge here. No-op for synchronous ones."""
        return None
