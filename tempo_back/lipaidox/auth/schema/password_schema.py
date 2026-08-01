import strawberry
from typing import Optional
from datetime import datetime
from ..models import PasswordResetToken


@strawberry.type
class PasswordResetTokenType:
    id: strawberry.ID
    token_hash: str
    status: str
    expires_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, instance: PasswordResetToken):
        return cls(
            id=strawberry.ID(str(instance.id)),
            token_hash=instance.token_hash,
            status=instance.status,
            expires_at=instance.expires_at,
            created_at=instance.created_at,
        )


@strawberry.type
class RequestPasswordResetPayload:
    """
    OTP flow result.

    When ``PASSWORD_RESET_INLINE_OTP`` is enabled (dev / no SMTP), ``inline_otp`` carries the
    six-digit code so the SPA can pre-fill; otherwise omit (null) and mail carries the code.
    """

    success: bool
    expires_in_seconds: int
    inline_otp: Optional[str] = None


@strawberry.input
class RequestPasswordResetInput:
    email: str


@strawberry.input
class ResetPasswordInput:
    email: str
    otp_code: str
    new_password: str


@strawberry.input
class VerifyPasswordResetOtpInput:
    email: str
    otp_code: str


@strawberry.input
class RequestPasswordResetLinkInput:
    email: str


@strawberry.input
class ResetPasswordWithTokenInput:
    token: str
    new_password: str


# ── Normal user: change password with old password verification ───────────────

@strawberry.input
class ChangePasswordInput:
    old_password: str
    new_password: str


# ── Google user: set initial password via email OTP ───────────────────────────

@strawberry.input
class RequestInitialPasswordOtpInput:
    """Sends an OTP to the logged-in user's email so they can set their first password."""
    email: str


@strawberry.input
class VerifyInitialPasswordOtpInput:
    email: str
    otp_code: str


@strawberry.input
class SetInitialPasswordWithOtpInput:
    email: str
    otp_code: str
    new_password: str
