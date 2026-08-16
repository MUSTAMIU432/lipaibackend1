import strawberry
import random
from django.db import IntegrityError
from django.utils import timezone
from ..models import PhoneVerification, User
from ..schema.phone_schema import PhoneVerificationType, VerifyPhoneInput
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class PhoneMutation:
    @strawberry.mutation
    def send_phone_verification_otp(
        self, info: strawberry.types.Info, phone_number: str, country_code: str
    ) -> PhoneVerificationType:
        """Send a phone OTP to the SIGNED-IN user, saving the number on their account.

        Unlike the legacy `requestPhoneVerification` (which required the number to
        already be on file), this is the onboarding entry point: the fan is adding
        their phone for the first time, so we attach it to the authenticated user
        and issue the code. The 6-digit `otpCode` is returned on the result so a
        build with no SMS gateway can still complete the step (mirrors the email
        inline-OTP path).
        """
        user = info.context.request.user
        if not getattr(user, "is_authenticated", False):
            raise Exception("Authentication required")
        tenant = get_current_tenant()

        phone_number = (phone_number or "").strip()
        country_code = (country_code or "").strip()
        if not phone_number or not country_code:
            raise Exception("Enter your phone number and country code.")

        # Refuse a number already verified by a different account.
        clash = (
            User.objects.filter(phone_number=phone_number, phone_country_code=country_code)
            .exclude(pk=user.pk)
            .exists()
        )
        if clash:
            raise Exception("That phone number is already in use by another account.")

        user.phone_number = phone_number
        user.phone_country_code = country_code
        try:
            user.save(update_fields=["phone_number", "phone_country_code"])
        except IntegrityError:
            raise Exception("That phone number is already in use by another account.")

        otp = f"{random.randint(100000, 999999)}"
        verification = PhoneVerification.objects.create(
            user=user, tenant=tenant, phone_number=phone_number,
            country_code=country_code, otp_code=otp, status="pending",
        )
        return PhoneVerificationType.from_model(verification)

    @strawberry.mutation
    def request_phone_verification(self, phone_number: str, country_code: str) -> PhoneVerificationType:
        tenant = get_current_tenant()
        try:
            user = User.objects.get(phone_number=phone_number, phone_country_code=country_code, tenant=tenant)
            
            otp = f"{random.randint(100000, 999999)}"
            
            verification = PhoneVerification.objects.create(
                user=user,
                tenant=tenant,
                phone_number=phone_number,
                country_code=country_code,
                otp_code=otp,
                status="pending"
            )
            return PhoneVerificationType.from_model(verification)
        except User.DoesNotExist:
            raise Exception("User with this phone number not found in this tenant.")

    @strawberry.mutation
    def verify_phone(self, input: VerifyPhoneInput) -> bool:
        tenant = get_current_tenant()
        # A re-send leaves several pending rows; take the newest match rather than
        # `.get()`, which would raise MultipleObjectsReturned.
        verification = (
            PhoneVerification.objects.filter(
                phone_number=input.phone_number,
                otp_code=input.otp_code,
                status="pending",
                expires_at__gt=timezone.now(),
                tenant=tenant,
            )
            .order_by("-created_at")
            .first()
        )
        if verification is None:
            return False

        verification.status = "verified"
        verification.verified_at = timezone.now()
        verification.save(update_fields=["status", "verified_at"])

        user = verification.user
        user.phone_verified = True
        user.save(update_fields=["phone_verified"])
        return True
