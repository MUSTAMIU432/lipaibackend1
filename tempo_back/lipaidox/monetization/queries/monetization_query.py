import strawberry
from typing import Optional
from ..models import MonetizationSettings
from ..schema.monetization_schema import MonetizationSettingsType
from lipaidox.auth.permissions import require_creator

@strawberry.type
class MonetizationQuery:
    @strawberry.field
    @require_creator
    def my_monetization_settings(self, info: strawberry.types.Info) -> Optional[MonetizationSettingsType]:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        try:
            settings = MonetizationSettings.objects.get(creator__user=user)
            return MonetizationSettingsType.from_model(settings)
        except MonetizationSettings.DoesNotExist:
            return None
