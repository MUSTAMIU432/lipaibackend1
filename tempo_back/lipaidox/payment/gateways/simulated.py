import uuid
from decimal import Decimal
from typing import Optional

from lipaidox.payment.models import Charge, ChargePurpose, ChargeStatus
from . import PaymentGateway


class SimulatedGateway(PaymentGateway):
    """
    Records a Charge and settles it instantly. No real money moves.

    Set ``metadata['simulate'] == 'fail'`` to force a failed charge (used to test
    the no-entitlement-on-failure path).
    """
    code = "simulated"

    def create_charge(
        self,
        *,
        user,
        amount: Decimal,
        currency: str = "USD",
        purpose: str = ChargePurpose.WALLET_TOPUP,
        metadata: Optional[dict] = None,
    ) -> Charge:
        metadata = metadata or {}
        should_fail = str(metadata.get("simulate", "")).lower() == "fail"
        return Charge.objects.create(
            user=user,
            tenant=getattr(user, "tenant", None),
            gateway=self.code,
            amount=Decimal(str(amount)),
            currency=currency,
            purpose=purpose,
            status=ChargeStatus.FAILED if should_fail else ChargeStatus.SUCCEEDED,
            provider_ref=f"sim_{uuid.uuid4().hex[:16]}",
            metadata=metadata,
        )
