import strawberry
from typing import List

from lipaidox.wallet.services import get_or_create_fan_wallet
from lipaidox.wallet.models import Transaction
from ..schema.gateway_schema import FanWalletType, LedgerEntryType


def _auth(info):
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


@strawberry.type
class GatewayQuery:
    @strawberry.field
    def my_fan_wallet(self, info: strawberry.types.Info, currency: str = "USD") -> FanWalletType:
        """Current user's spendable money wallet (auto-created, defaults to zero)."""
        try:
            user = _auth(info)
        except Exception:
            return FanWalletType.empty(currency)
        wallet = get_or_create_fan_wallet(user, currency)
        return FanWalletType.from_model(wallet)

    @strawberry.field
    def my_fan_transactions(
        self, info: strawberry.types.Info, limit: int = 50, offset: int = 0
    ) -> List[LedgerEntryType]:
        """Platform ledger rows where the current user is fan or creator."""
        try:
            user = _auth(info)
        except Exception:
            return []
        from django.db.models import Q

        # Rows where the viewer is the fan. Only widen to the creator side when
        # they actually have a profile: a None creator_id would compile to
        # `creator_id IS NULL` and match other users' creator-less rows (e.g.
        # credit purchases), which then read as income for someone who earned
        # nothing.
        query = Q(fan=user)
        profile = getattr(user, "profile", None)
        if profile is not None:
            query |= Q(creator_id=profile.id)

        qs = Transaction.objects.filter(query).order_by(
            "-created_at"
        )[offset: offset + limit]
        return [LedgerEntryType.from_model(t, user.id) for t in qs]
