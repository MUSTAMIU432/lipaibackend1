import strawberry
import random
from django.utils import timezone
from ..models import PhoneVerification, User
from ..schema.phone_schema import PhoneVerificationType, VerifyPhoneInput
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class PhoneMutation:
    @strawberry.mutation
    def send_phone_verification_otp(
        self, phone_number: str, country_code: str
    ) -> PhoneVerificationType:
        """Alias for clients that call `sendPhoneVerificationOtp` (same as `requestPhoneVerification`)."""
        return self.request_phone_verification(phone_number, country_code)

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
        try:
            verification = PhoneVerification.objects.get(
                phone_number=input.phone_number, 
                otp_code=input.otp_code,
                status="pending",
                expires_at__gt=timezone.now(),
                tenant=tenant
            )
            
            verification.status = "verified"
            verification.save()
            
            user = verification.user
            user.phone_verified = True
            user.save()
            
            return True
        except PhoneVerification.DoesNotExist:
            return False
