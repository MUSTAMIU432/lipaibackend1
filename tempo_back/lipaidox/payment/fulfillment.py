"""
Charge fulfillment — what a *succeeded* async charge grants.

Because the platform models every gateway purchase as top-up-then-spend (see
``wallet/services.py``), an async provider only ever funds the fan wallet here.
Once the wallet is funded, each feature (PPV, live, credits, subscriptions, tips)
spends from it through its normal WALLET path — so wiring the gateway to the
wallet wires it to every paid surface at once.

``fulfill_charge`` is idempotent: it transitions PENDING → SUCCEEDED under a row
lock and funds the wallet exactly once, so a webhook and a status poll racing on
the same charge can't double-credit.
"""
import logging

from django.db import transaction as db_transaction

from lipaidox.payment.models import Charge, ChargePurpose, ChargeStatus

logger = logging.getLogger(__name__)


def fulfill_charge(charge: Charge) -> Charge:
    """Settle a paid charge exactly once and grant what it funds."""
    with db_transaction.atomic():
        charge = Charge.objects.select_for_update().get(pk=charge.pk)
        if charge.status == ChargeStatus.SUCCEEDED:
            return charge  # already fulfilled by a concurrent webhook/poll
        charge.status = ChargeStatus.SUCCEEDED
        charge.save(update_fields=["status", "updated_at"])

        # All gateway charges fund the wallet. The Charge currency is the funding
        # currency (TZS for NBC); the wallet is keyed by that same currency, so
        # there is no FX here — price and spend must share the currency.
        from lipaidox.wallet.services import credit_fan_wallet

        credit_fan_wallet(charge.user, charge.amount, charge.currency)
        logger.info(
            "Fulfilled charge %s: credited %s %s to %s (purpose=%s)",
            charge.id, charge.amount, charge.currency, charge.user_id, charge.purpose,
        )
    return charge
