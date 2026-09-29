import strawberry
from typing import List, Optional
from ..models import PaymentMethod, MobileMoneyProvider, TaxProfile
from ..schema.payment_schema import PaymentMethodType, MobileMoneyProviderType, TaxProfileType
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator
from lipaidox.cache import NS_MOBILE_MONEY_PROVIDERS, TTL_CATALOG, get_or_set_models

@strawberry.type
class PaymentQuery:
    @strawberry.field
    @require_creator
    def my_payment_methods(self, info: strawberry.types.Info) -> List[PaymentMethodType]:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        methods = PaymentMethod.objects.filter(creator__user=user).order_by('-is_primary', '-created_at')
        return [PaymentMethodType.from_model(m) for m in methods]

    @strawberry.field
    def mobile_money_providers(self) -> List[MobileMoneyProviderType]:
        providers = get_or_set_models(
            NS_MOBILE_MONEY_PROVIDERS, "active", ttl=TTL_CATALOG,
            loader=lambda: MobileMoneyProvider.objects.filter(is_active=True),
        )
        return [MobileMoneyProviderType.from_model(p) for p in providers]

    @strawberry.field
    @require_creator
    def my_tax_information(self, info: strawberry.types.Info) -> Optional[TaxProfileType]:
        user = info.context.request.user
        profile = TaxProfile.objects.filter(creator__user=user).first()
        return TaxProfileType.from_model(profile) if profile else None
