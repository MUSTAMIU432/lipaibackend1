import strawberry
from typing import Optional
from datetime import datetime
from ..models import PhoneVerification

@strawberry.type
class PhoneVerificationType:
    id: strawberry.ID
    phone_number: str
    country_code: str
    otp_code: str
    status: str
    expires_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, instance: PhoneVerification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            phone_number=instance.phone_number,
            country_code=instance.country_code,
            otp_code=instance.otp_code,
            status=instance.status,
            expires_at=instance.expires_at,
            created_at=instance.created_at,
        )

@strawberry.input
class VerifyPhoneInput:
    phone_number: str
    otp_code: str
