"""
Password reset:

- **Firebase Auth (email/password):** use the **Firebase Web SDK** ``sendPasswordResetEmail`` on the
  client; Firebase sends the mail and owns templates / authorized domains. No GraphQL mutation
  on this backend for that flow.

- **Django-only:** ``requestPasswordReset`` / ``verifyPasswordResetOtp`` / ``resetPassword`` (OTP), or
  ``requestPasswordResetLink`` / ``resetPasswordWithToken`` (Django magic link + SMTP).
- **Dev / no SMTP:** set ``PASSWORD_RESET_INLINE_OTP=True`` → OTP is returned as ``inlineOtp`` in
  GraphQL (no email); SPA pre-fills and continues to new password.
"""

import logging
import secrets

import strawberry
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from ..models import PasswordResetOtp, PasswordResetOtpStatus, PasswordResetToken
from ..email_outbound import send_password_reset_link_email, send_password_reset_otp_email
from ..jwt_auth import hash_token
from ..services.password_reset_link import build_password_reset_url
from ..forgetpassword_auth.otp_verify import (
    MAX_OTP_ATTEMPTS,
    verify_password_reset_otp as _verify_password_reset_otp,
)
from ..schema.password_schema import (
    ChangePasswordInput,
    RequestInitialPasswordOtpInput,
    RequestPasswordResetInput,
    RequestPasswordResetLinkInput,
    RequestPasswordResetPayload,
    ResetPasswordInput,
    ResetPasswordWithTokenInput,
    SetInitialPasswordWithOtpInput,
    VerifyInitialPasswordOtpInput,
    VerifyPasswordResetOtpInput,
)
from ..validation import normalize_signup_email, validate_signup_password
from ..user_eligibility import (
    assert_user_may_authenticate,
    assert_user_may_request_password_reset,
    find_user_by_email_tenant,
)
from multitenant.utils.tenant_context import get_current_tenant

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 600  # 10 minutes

# Matches ``PasswordResetToken`` default expiry (1 hour).
LINK_TTL_SECONDS = 3600
_LINK_TOKEN_BYTES = 32

_TOKEN_STATUS_PENDING = "pending"
_TOKEN_STATUS_SUPERSEDED = "superseded"
_TOKEN_STATUS_USED = "used"


def _send_password_reset_link_for_user(user) -> RequestPasswordResetPayload:
    """Create ``PasswordResetToken``, email magic link (FRONTEND_ORIGIN + path)."""
    PasswordResetToken.objects.filter(
        user=user,
        status=_TOKEN_STATUS_PENDING,
    ).update(status=_TOKEN_STATUS_SUPERSEDED)

    raw_token = secrets.token_urlsafe(_LINK_TOKEN_BYTES)
    PasswordResetToken.objects.create(
        tenant_id=user.tenant_id,
        user=user,
        token_hash=hash_token(raw_token),
        status=_TOKEN_STATUS_PENDING,
    )

    path = getattr(
        settings, "PASSWORD_RESET_FRONTEND_PATH", "/reset-password"
    )
    reset_url = build_password_reset_url(
        frontend_origin=settings.FRONTEND_ORIGIN,
        frontend_path=path,
        token=raw_token,
    )

    try:
        send_password_reset_link_email(
            to_email=user.email,
            reset_url=reset_url,
            expires_minutes=LINK_TTL_SECONDS // 60,
        )
    except Exception as exc:
        logger.exception("Password reset link email failed for %s", user.email)
        msg = "We could not send the reset email. Check server email settings or try again later."
        if getattr(settings, "DEBUG", False):
            detail = (str(exc) or type(exc).__name__).strip()
            if detail:
                msg = f"{msg} (detail: {detail[:400]})"
        raise Exception(msg) from exc

    return RequestPasswordResetPayload(
        success=True,
        expires_in_seconds=LINK_TTL_SECONDS,
        inline_otp=None,
    )


@strawberry.type
class PasswordMutation:
    @strawberry.mutation
    def request_password_reset(
        self, input: RequestPasswordResetInput
    ) -> RequestPasswordResetPayload:
        tenant = get_current_tenant()
        email = normalize_signup_email(input.email)
        user = find_user_by_email_tenant(email, tenant.id)
        if not user:
            raise Exception(
                "No account found for this email. Check spelling or create an account."
            )
        assert_user_may_request_password_reset(user)

        plain_otp = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = PasswordResetOtp.hash_code(plain_otp)

        PasswordResetOtp.objects.filter(
            user=user,
            status=PasswordResetOtpStatus.PENDING,
        ).update(status=PasswordResetOtpStatus.SUPERSEDED)

        PasswordResetOtp.objects.create(
            user=user,
            code_hash=code_hash,
            status=PasswordResetOtpStatus.PENDING,
            attempts=0,
        )

        inline = getattr(settings, "PASSWORD_RESET_INLINE_OTP", False)
        if inline:
            logger.info(
                "PASSWORD_RESET_INLINE_OTP: skipping SMTP for %s; returning code in GraphQL only",
                user.email,
            )
            return RequestPasswordResetPayload(
                success=True,
                expires_in_seconds=OTP_TTL_SECONDS,
                inline_otp=plain_otp,
            )

        try:
            send_password_reset_otp_email(
                to_email=user.email,
                otp_code=plain_otp,
                expires_minutes=OTP_TTL_SECONDS // 60,
            )
        except Exception as exc:
            logger.exception("Password reset OTP email failed for %s", user.email)
            msg = "We could not send the reset email. Check server email settings or try again later."
            if getattr(settings, "DEBUG", False):
                detail = (str(exc) or type(exc).__name__).strip()
                if detail:
                    msg = f"{msg} (detail: {detail[:400]})"
            raise Exception(msg) from exc

        return RequestPasswordResetPayload(
            success=True,
            expires_in_seconds=OTP_TTL_SECONDS,
            inline_otp=None,
        )

    @strawberry.mutation
    def verify_password_reset_otp(self, input: VerifyPasswordResetOtpInput) -> bool:
        """Optional wizard step: check OTP before ``resetPassword`` (does not consume the OTP)."""
        return _verify_password_reset_otp(email=input.email, otp_code=input.otp_code)

    @strawberry.mutation
    def request_password_reset_link(
        self, input: RequestPasswordResetLinkInput
    ) -> RequestPasswordResetPayload:
        tenant = get_current_tenant()
        email = normalize_signup_email(input.email)
        user = find_user_by_email_tenant(email, tenant.id)
        if not user:
            raise Exception(
                "No account found for this email. Check spelling or create an account."
            )
        assert_user_may_request_password_reset(user)
        return _send_password_reset_link_for_user(user)

    @strawberry.mutation
    def reset_password(self, input: ResetPasswordInput) -> bool:
        tenant = get_current_tenant()
        email = normalize_signup_email(input.email)
        digits_only = "".join(c for c in (input.otp_code or "") if c.isdigit())
        if len(digits_only) != 6:
            return False

        record = (
            PasswordResetOtp.objects.filter(
                user__email__iexact=email,
                user__tenant_id=tenant.id,
                status=PasswordResetOtpStatus.PENDING,
                expires_at__gt=timezone.now(),
            )
            .select_related("user")
            .order_by("-created_at")
            .first()
        )
        if not record:
            return False

        if record.attempts >= MAX_OTP_ATTEMPTS:
            record.status = PasswordResetOtpStatus.EXPIRED
            record.save(update_fields=["status"])
            return False

        if not record.verify_code(digits_only):
            PasswordResetOtp.objects.filter(pk=record.pk).update(
                attempts=F("attempts") + 1
            )
            return False

        validate_signup_password(input.new_password)

        user = record.user
        assert_user_may_authenticate(user)
        user.password = make_password(input.new_password)
        user.save(update_fields=["password"])

        record.status = PasswordResetOtpStatus.USED
        record.save(update_fields=["status"])
        return True

    @strawberry.mutation
    def change_password(self, info: strawberry.types.Info, input: ChangePasswordInput) -> bool:
        """
        Authenticated user with an existing password changes it by supplying the old one.
        Rejects Google-only accounts that have no usable password yet.
        """
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception("Authentication required.")
        user = request.user
        if not user.has_usable_password():
            raise Exception("No password set on this account. Use the email OTP flow to create one.")
        if not user.check_password(input.old_password):
            raise Exception("Current password is incorrect.")
        validate_signup_password(input.new_password)
        user.set_password(input.new_password)
        user.save(update_fields=["password"])
        return True

    @strawberry.mutation
    def request_initial_password_otp(
        self, info: strawberry.types.Info, input: RequestInitialPasswordOtpInput
    ) -> RequestPasswordResetPayload:
        """
        Google-linked user (no backend password) requests an OTP sent to their account email
        so they can create their first password without knowing any existing password.
        Requires Bearer auth — the session email must match ``input.email``.
        """
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception("Authentication required.")
        user = request.user
        email = normalize_signup_email(input.email)
        user_email = normalize_signup_email((getattr(user, "email", "") or "").strip())
        if not email or email != user_email:
            raise Exception("Email does not match your account.")

        import secrets as _secrets
        from ..models import PasswordResetOtp, PasswordResetOtpStatus
        from ..email_outbound import send_password_reset_otp_email as _send_otp

        tenant = get_current_tenant()
        PasswordResetOtp.objects.filter(
            user=user, status=PasswordResetOtpStatus.PENDING
        ).update(status=PasswordResetOtpStatus.EXPIRED)

        plain_otp = f"{_secrets.randbelow(1_000_000):06d}"
        PasswordResetOtp.objects.create(
            user=user,
            code_hash=PasswordResetOtp.hash_code(plain_otp),
        )

        inline = getattr(settings, "EMAIL_VERIFICATION_INLINE_OTP", False) or getattr(
            settings, "PASSWORD_RESET_INLINE_OTP", False
        )
        if inline:
            logger.info("request_initial_password_otp: inline OTP for %s", email)
            return RequestPasswordResetPayload(
                success=True,
                expires_in_seconds=OTP_TTL_SECONDS,
                inline_otp=plain_otp,
            )

        try:
            _send_otp(to_email=email, otp_code=plain_otp)
        except Exception as exc:
            logger.exception("request_initial_password_otp: mail failed for %s", email)
            msg = "Could not send the verification email. Check server email settings or try again."
            if getattr(settings, "DEBUG", False):
                detail = (str(exc) or type(exc).__name__).strip()
                if detail:
                    msg = f"{msg} (detail: {detail[:400]})"
            raise Exception(msg) from exc

        return RequestPasswordResetPayload(
            success=True,
            expires_in_seconds=OTP_TTL_SECONDS,
            inline_otp=None,
        )

    @strawberry.mutation
    def verify_initial_password_otp(
        self, info: strawberry.types.Info, input: VerifyInitialPasswordOtpInput
    ) -> bool:
        """Check the OTP without consuming it — lets the SPA validate before showing the password form."""
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception("Authentication required.")
        from django.db.models import Q
        from ..models import PasswordResetOtp, PasswordResetOtpStatus
        tenant = get_current_tenant()
        email = normalize_signup_email(input.email)
        digits = "".join(c for c in (input.otp_code or "") if c.isdigit())
        if len(digits) != 6:
            return False
        record = (
            PasswordResetOtp.objects.filter(
                user=request.user,
                user__email__iexact=email,
                status=PasswordResetOtpStatus.PENDING,
                expires_at__gt=timezone.now(),
            )
            .filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            .order_by("-created_at")
            .first()
        )
        if not record:
            return False
        return record.verify_code(digits)

    @strawberry.mutation
    def set_initial_password_with_otp(
        self, info: strawberry.types.Info, input: SetInitialPasswordWithOtpInput
    ) -> bool:
        """
        Consume the OTP and set the user's first password.
        After this call the account has a usable password and switches to the normal flow.
        """
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception("Authentication required.")
        from django.db.models import Q
        from ..models import PasswordResetOtp, PasswordResetOtpStatus
        tenant = get_current_tenant()
        email = normalize_signup_email(input.email)
        user_email = normalize_signup_email((getattr(request.user, "email", "") or "").strip())
        if not email or email != user_email:
            raise Exception("Email does not match your account.")
        digits = "".join(c for c in (input.otp_code or "") if c.isdigit())
        if len(digits) != 6:
            return False

        record = (
            PasswordResetOtp.objects.filter(
                user=request.user,
                user__email__iexact=email,
                status=PasswordResetOtpStatus.PENDING,
                expires_at__gt=timezone.now(),
            )
            .filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            .order_by("-created_at")
            .first()
        )
        if not record:
            return False
        if record.attempts >= MAX_OTP_ATTEMPTS:
            record.status = PasswordResetOtpStatus.EXPIRED
            record.save(update_fields=["status"])
            return False
        if not record.verify_code(digits):
            PasswordResetOtp.objects.filter(pk=record.pk).update(attempts=F("attempts") + 1)
            return False

        validate_signup_password(input.new_password)
        user = request.user
        assert_user_may_authenticate(user)
        user.set_password(input.new_password)
        user.save(update_fields=["password"])

        record.status = PasswordResetOtpStatus.USED
        record.save(update_fields=["status"])
        return True

    @strawberry.mutation
    def reset_password_with_token(self, input: ResetPasswordWithTokenInput) -> bool:
        raw = (input.token or "").strip()
        if not raw:
            return False

        token_hash = hash_token(raw)
        record = (
            PasswordResetToken.objects.filter(
                token_hash=token_hash,
                status=_TOKEN_STATUS_PENDING,
                expires_at__gt=timezone.now(),
            )
            .select_related("user")
            .first()
        )
        if not record:
            return False

        tenant = get_current_tenant()
        if record.user.tenant_id != tenant.id:
            return False

        validate_signup_password(input.new_password)
        user = record.user
        assert_user_may_authenticate(user)
        user.password = make_password(input.new_password)
        user.save(update_fields=["password"])

        record.status = _TOKEN_STATUS_USED
        record.save(update_fields=["status"])
        return True
