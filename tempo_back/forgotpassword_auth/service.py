from __future__ import annotations

import logging
from typing import Callable

from .exceptions import (
    AccountBlockedError,
    AlreadyHasPasswordError,
    EmailMismatchError,
    InvalidOtpError,
    NoPasswordYetError,
    UserNotFoundError,
    WeakPasswordError,
)
from .otp_util import generate_six_digit_code, hash_otp, normalize_email
from .password_rules import validate_new_password
from .protocols import Mailer, OtpRepository, UserRepository
from .types import OtpPurpose, ServiceResult

logger = logging.getLogger(__name__)


class ForgotPasswordAuthService:
    """
    - request_password_reset: existing forgot flow (must already have backend password).
    - request_initial_password_otp: Google-linked, no password yet (authenticated).
    - verify_otp: shared (caller passes purpose matching the OTP that was sent).
    - reset_password: complete forgot (FORGOT_PASSWORD OTP).
    - set_initial_password_with_otp: first backend password (INITIAL_PASSWORD OTP).
    """

    def __init__(
        self,
        *,
        users: UserRepository,
        otps: OtpRepository,
        mailer: Mailer,
        otp_pepper: str,
        hash_password: Callable[[str], str],
        otp_ttl_seconds: int = 600,
    ) -> None:
        self._users = users
        self._otps = otps
        self._mailer = mailer
        self._otp_pepper = otp_pepper
        self._hash_password = hash_password
        self._otp_ttl = otp_ttl_seconds

    def request_password_reset(self, email: str) -> ServiceResult[dict]:
        """
        Forgot password OTP. Anti-enumeration: unknown email or no password yet →
        same success shape, no email sent.
        """
        em = normalize_email(email)
        user = self._users.get_by_email_normalized(em)
        if not user or not user.has_password:
            return ServiceResult.ok({"expiresInSeconds": self._otp_ttl})
        if not user.may_request_password_reset:
            raise AccountBlockedError(
                "Password reset is not available for this account.",
            )
        code = generate_six_digit_code()
        self._otps.save_otp(
            email_normalized=em,
            purpose=OtpPurpose.FORGOT_PASSWORD,
            user_id=user.id,
            code_hash=hash_otp(code, self._otp_pepper),
            expires_in_seconds=self._otp_ttl,
        )
        self._mailer.send_otp_email(
            to_email=user.email,
            purpose=OtpPurpose.FORGOT_PASSWORD,
            code_plain=code,
        )
        return ServiceResult.ok({"expiresInSeconds": self._otp_ttl})

    def request_initial_password_otp(
        self,
        *,
        authenticated_user_id: str,
        email_must_match: str,
    ) -> ServiceResult[dict]:
        em = normalize_email(email_must_match)
        user = self._users.get_by_id(authenticated_user_id)
        if not user:
            raise UserNotFoundError("User not found.")
        if normalize_email(user.email) != em:
            raise EmailMismatchError("Email does not match the signed-in account.")
        if not user.is_google_linked:
            raise AccountBlockedError(
                "Initial password setup is only available for Google-linked accounts.",
            )
        if user.has_password:
            raise AlreadyHasPasswordError(
                "A password is already set. Use change password or forgot password.",
            )
        if not user.may_request_password_reset:
            raise AccountBlockedError(
                "Password setup is not available for this account.",
            )

        code = generate_six_digit_code()
        self._otps.save_otp(
            email_normalized=em,
            purpose=OtpPurpose.INITIAL_PASSWORD,
            user_id=user.id,
            code_hash=hash_otp(code, self._otp_pepper),
            expires_in_seconds=self._otp_ttl,
        )
        self._mailer.send_otp_email(
            to_email=user.email,
            purpose=OtpPurpose.INITIAL_PASSWORD,
            code_plain=code,
        )
        return ServiceResult.ok({"expiresInSeconds": self._otp_ttl})

    def verify_otp(self, email: str, otp_code: str, purpose: OtpPurpose) -> bool:
        em = normalize_email(email)
        return self._otps.verify_otp_active(
            email_normalized=em,
            purpose=purpose,
            code_plain=otp_code.strip(),
        )

    def verify_forgot_password_otp(self, email: str, otp_code: str) -> bool:
        return self.verify_otp(email, otp_code, OtpPurpose.FORGOT_PASSWORD)

    def verify_initial_password_otp(self, email: str, otp_code: str) -> bool:
        return self.verify_otp(email, otp_code, OtpPurpose.INITIAL_PASSWORD)

    def reset_password(self, email: str, otp_code: str, new_password: str) -> ServiceResult[bool]:
        em = normalize_email(email)
        user = self._users.get_by_email_normalized(em)
        if not user:
            raise UserNotFoundError("User not found.")
        if not user.has_password:
            raise NoPasswordYetError(
                "No password is on file for this account. Use Google sign-in and set a password in your profile.",
            )
        if not self._otps.verify_otp_active(
            email_normalized=em,
            purpose=OtpPurpose.FORGOT_PASSWORD,
            code_plain=otp_code.strip(),
        ):
            raise InvalidOtpError("Invalid or expired code.")
        validate_new_password(new_password)
        self._users.set_password_hash(user.id, self._hash_password(new_password))
        self._otps.consume_otp(email_normalized=em, purpose=OtpPurpose.FORGOT_PASSWORD)
        return ServiceResult.ok(True)

    def set_initial_password_with_otp(
        self,
        *,
        authenticated_user_id: str,
        email: str,
        otp_code: str,
        new_password: str,
    ) -> ServiceResult[bool]:
        em = normalize_email(email)
        user = self._users.get_by_id(authenticated_user_id)
        if not user:
            raise UserNotFoundError("User not found.")
        if normalize_email(user.email) != em:
            raise EmailMismatchError("Email does not match the signed-in account.")
        if user.has_password:
            raise AlreadyHasPasswordError("Password already set.")
        if not self._otps.verify_otp_active(
            email_normalized=em,
            purpose=OtpPurpose.INITIAL_PASSWORD,
            code_plain=otp_code.strip(),
        ):
            raise InvalidOtpError("Invalid or expired code.")
        validate_new_password(new_password)
        self._users.set_password_hash(user.id, self._hash_password(new_password))
        self._otps.consume_otp(email_normalized=em, purpose=OtpPurpose.INITIAL_PASSWORD)
        return ServiceResult.ok(True)
