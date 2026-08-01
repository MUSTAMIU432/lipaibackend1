import strawberry
from django.db import transaction
from ..models import PaymentMethod, PaymentMethodType as PMType, PaymentMethodStatus
from lipaidox.creator_profile.models import CreatorProfile
from ..schema.payment_schema import PaymentMethodType, BankTransferInput, MobileMoneyInput
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator

@strawberry.type
class PaymentMutation:
    @strawberry.mutation
    @require_creator
    def add_bank_transfer_method(self, info: strawberry.types.Info, input: BankTransferInput) -> PaymentMethodType:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()
        
        with transaction.atomic():
            is_first = not PaymentMethod.objects.filter(creator=profile).exists()
            method = PaymentMethod.objects.create(
                creator=profile,
                tenant=tenant,
                method_type=PMType.BANK_TRANSFER,
                bank_name=input.bankName,
                bank_account_holder_name=input.bankAccountHolderName,
                bank_account_number_last4=input.bankAccountNumber[-4:],
                bank_account_number_encrypted="ENCRYPTED_MOCK",
                bank_swift_code=input.bankSwiftCode,
                bank_iban=input.bankIban,
                bank_country=input.bankCountry,
                is_primary=is_first,
                status=PaymentMethodStatus.PENDING
            )
        return PaymentMethodType.from_model(method)

    @strawberry.mutation
    @require_creator
    def add_mobile_money_method(self, info: strawberry.types.Info, input: MobileMoneyInput) -> PaymentMethodType:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()
        
        with transaction.atomic():
            is_first = not PaymentMethod.objects.filter(creator=profile).exists()
            method = PaymentMethod.objects.create(
                creator=profile,
                tenant=tenant,
                method_type=PMType.MOBILE_MONEY,
                mobile_money_provider=input.provider,
                mobile_money_phone_number=input.phoneNumber,
                mobile_money_phone_country_code=input.countryCode,
                mobile_money_account_name=input.accountName,
                is_primary=is_first,
                status=PaymentMethodStatus.PENDING
            )
        return PaymentMethodType.from_model(method)

    @strawberry.mutation
    @require_creator
    def set_primary_payment_method(self, info: strawberry.types.Info, method_id: strawberry.ID) -> bool:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        profile = CreatorProfile.objects.get(user=user)
        with transaction.atomic():
            PaymentMethod.objects.filter(creator=profile).update(is_primary=False)
            method = PaymentMethod.objects.get(id=method_id, creator=profile)
            method.is_primary = True
            method.save()
            return True
        return False
