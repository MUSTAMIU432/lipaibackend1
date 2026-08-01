import strawberry
from typing import Optional
from datetime import datetime
from ..models import EmailVerification


@strawberry.type
class SendEmailVerificationOtpResult:
    """
    When ``EMAIL_VERIFICATION_INLINE_OTP`` is enabled (dev / no SMTP), ``inline_otp`` carries the
    plain 6-digit code so the SPA can pre-fill the field for the user.
    In production it is always ``None``.
    """

    success: bool
    inline_otp: Optional[str] = None

@strawberry.type
class EmailVerificationType:
    id: strawberry.ID
    email: str
    token: str
    otp_code: Optional[str]
    status: str
    expires_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, instance: EmailVerification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            email=instance.email,
            token=instance.token,
            otp_code=instance.otp_code,
            status=instance.status,
            expires_at=instance.expires_at,
            created_at=instance.created_at,
        )

@strawberry.input
class VerifyEmailInput:
    email: str
    otp_code: str


@strawberry.input
class ConfirmEmailVerificationOtpInput:
    """SPA sends only the code; server uses the logged-in user's email."""

    otp_code: str
