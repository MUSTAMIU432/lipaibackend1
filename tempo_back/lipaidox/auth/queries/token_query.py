import strawberry
from typing import List, Optional
from ..models import BackupCode, RefreshToken, TwoFactorAuth
from ..schema.token_schema import RefreshTokenType
from ..schema.two_factor_schema import TwoFactorStatusType

@strawberry.type
class TokenQuery:
    @strawberry.field
    def my_two_factor_status(self, info: strawberry.types.Info) -> Optional[TwoFactorStatusType]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        tfa = TwoFactorAuth.objects.filter(user=user, enabled=True).first()
        remaining = BackupCode.objects.filter(user=user, used_at__isnull=True).count() if tfa else 0
        return TwoFactorStatusType(
            enabled=tfa is not None,
            confirmedAt=tfa.confirmed_at if tfa else None,
            backupCodesRemaining=remaining,
        )

    @strawberry.field
    def active_refresh_tokens(self, info: strawberry.types.Info) -> List[RefreshTokenType]:
        """The signed-in user's own active sessions — one row per device
        that's still logged in. Scoped to `request.user`: this used to
        filter only by tenant, which handed back every OTHER user's
        session metadata (device name, last-used time) in the same
        tenant, not just the caller's own."""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        tokens = RefreshToken.objects.filter(user=user, status="active").order_by("-last_used_at", "-created_at")
        return [RefreshTokenType.from_model(t) for t in tokens]
