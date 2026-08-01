import strawberry
from django.db import transaction
from ..models import MonetizationSettings, MonetizationPriceHistory, PriceField
from lipaidox.creator_profile.models import CreatorProfile
from ..schema.monetization_schema import MonetizationSettingsType, MonetizationUpdateInput
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator

@strawberry.type
class MonetizationMutation:
    @strawberry.mutation
    @require_creator
    def update_monetization_settings(self, info: strawberry.types.Info, input: MonetizationUpdateInput) -> MonetizationSettingsType:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()

        with transaction.atomic():
            settings, created = MonetizationSettings.objects.get_or_create(
                creator=profile,
                tenant=tenant
            )

            fields_to_check = {
                'subscriptionPrice': (PriceField.SUBSCRIPTION_PRICE, 'subscription_price'),
                'ppvPrice': (PriceField.PPV_PRICE, 'ppv_price'),
                'tipMinAmount': (PriceField.TIP_MIN_AMOUNT, 'tip_min_amount'),
                'tipMaxAmount': (PriceField.TIP_MAX_AMOUNT, 'tip_max_amount'),
            }

            for input_field, (enum_val, model_field) in fields_to_check.items():
                val = getattr(input, input_field)
                if val is not None:
                    old_val = getattr(settings, model_field)
                    if float(old_val or 0) != float(val):
                        MonetizationPriceHistory.objects.create(
                            creator=profile,
                            monetization=settings,
                            price_field=enum_val,
                            old_price=old_val,
                            new_price=val,
                            changed_by=user,
                            reason="Creator update"
                        )
                        setattr(settings, model_field, val)

            if input.subscriptionEnabled is not None:
                settings.subscription_enabled = input.subscriptionEnabled
            elif input.subscriptionPrice is not None and float(input.subscriptionPrice) > 0:
                # Implicitly enable when a valid price is provided
                settings.subscription_enabled = True

            if input.ppvEnabled is not None:
                settings.ppv_enabled = input.ppvEnabled
            elif input.ppvPrice is not None and float(input.ppvPrice) > 0:
                settings.ppv_enabled = True

            if input.tipsEnabled is not None:
                settings.tips_enabled = input.tipsEnabled
            if input.subscriptionBillingCycle:
                settings.subscription_billing_cycle = input.subscriptionBillingCycle
            if input.displayCurrency:
                settings.display_currency = input.displayCurrency

            settings.save()

        return MonetizationSettingsType.from_model(settings)
