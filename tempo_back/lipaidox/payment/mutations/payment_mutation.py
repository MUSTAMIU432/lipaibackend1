import re
import strawberry
from typing import Optional
from django.db import transaction
from django.utils import timezone
from ..models import PaymentMethod, PaymentMethodType as PMType, PaymentMethodStatus, TaxProfile, TaxProfileStatus
from lipaidox.creator_profile.models import CreatorProfile
from ..schema.payment_schema import (
    PaymentMethodType, BankTransferInput, MobileMoneyInput, CardPayoutInput,
    TaxProfileType, TaxInformationInput,
)
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator, require_admin

CARD_BRANDS = {"visa", "mastercard", "amex"}

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
    def add_card_payout_method(self, info: strawberry.types.Info, input: CardPayoutInput) -> PaymentMethodType:
        user = info.context.request.user
        brand = input.brand.strip().lower()
        if brand not in CARD_BRANDS:
            raise Exception("Only Visa, Mastercard and American Express cards are supported.")
        if not re.fullmatch(r"\d{4}", input.last4 or ""):
            raise Exception("Invalid card number.")
        if not 1 <= input.expiryMonth <= 12:
            raise Exception("Invalid expiry month.")
        today = timezone.now().date()
        if (input.expiryYear, input.expiryMonth) < (today.year, today.month):
            raise Exception("This card has expired.")
        if not input.holderName.strip():
            raise Exception("Card holder name is required.")

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()

        with transaction.atomic():
            is_first = not PaymentMethod.objects.filter(creator=profile).exists()
            method = PaymentMethod.objects.create(
                creator=profile,
                tenant=tenant,
                method_type=PMType.CARD,
                card_holder_name=input.holderName.strip(),
                card_brand=brand,
                card_last4=input.last4,
                card_expiry_month=input.expiryMonth,
                card_expiry_year=input.expiryYear,
                is_primary=is_first,
                status=PaymentMethodStatus.PENDING
            )
        return PaymentMethodType.from_model(method)

    @strawberry.mutation
    @require_creator
    def submit_tax_information(self, info: strawberry.types.Info, input: TaxInformationInput) -> TaxProfileType:
        user = info.context.request.user
        tin = re.sub(r"[\s-]", "", input.tinNumber or "")
        if not tin:
            raise Exception("Taxpayer Identification Number is required.")
        if not (input.tinCertificateUrl or "").strip():
            raise Exception("Upload your tax registration certificate.")
        if not input.taxpayerName.strip():
            raise Exception("Registered taxpayer name is required.")

        profile = CreatorProfile.objects.get(user=user)
        existing = TaxProfile.objects.filter(creator=profile).first()
        if existing is not None and existing.status == TaxProfileStatus.VERIFIED:
            raise Exception("Your tax information is already verified. Contact support to change it.")

        tax_profile, _ = TaxProfile.objects.update_or_create(
            creator=profile,
            defaults={
                "tenant": get_current_tenant(),
                "country_code": input.countryCode.strip().upper()[:2],
                "country_name": input.countryName.strip(),
                "tax_authority": input.taxAuthority.strip(),
                "taxpayer_name": input.taxpayerName.strip(),
                "tin_number": tin,
                "tin_certificate_url": input.tinCertificateUrl.strip(),
                "status": TaxProfileStatus.PENDING,
                "rejection_reason": None,
                "submitted_at": timezone.now(),
                "verified_at": None,
            },
        )
        return TaxProfileType.from_model(tax_profile)

    @strawberry.mutation
    @require_admin
    def admin_review_tax_information(
        self,
        info: strawberry.types.Info,
        creator_id: strawberry.ID,
        approve: bool,
        reason: Optional[str] = None,
    ) -> TaxProfileType:
        tax_profile = TaxProfile.objects.get(creator_id=creator_id)
        if approve:
            tax_profile.status = TaxProfileStatus.VERIFIED
            tax_profile.verified_at = timezone.now()
            tax_profile.rejection_reason = None
        else:
            tax_profile.status = TaxProfileStatus.REJECTED
            tax_profile.verified_at = None
            tax_profile.rejection_reason = (reason or "").strip() or None
        tax_profile.save()
        return TaxProfileType.from_model(tax_profile)

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
