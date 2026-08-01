import logging
import secrets

import strawberry
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from strawberry.types import Info

from lipaidox.auth.googleOuth.googleOuth import FirebaseAuthService
from lipaidox.onboarding.models import CreatorOnboardingStatus, StepStatus
from multitenant.utils.tenant_context import get_current_tenant

from ..email_outbound import send_profile_email_verification_otp_email
from ..models import EmailVerification
from ..schema.email_schema import ConfirmEmailVerificationOtpInput, SendEmailVerificationOtpResult, VerifyEmailInput
from ..validation import normalize_signup_email

logger = logging.getLogger(__name__)


def _otp_digits(raw: str) -> str:
    return "".join(c for c in (raw or "") if c.isdigit())[:6]


def _sync_onboarding_email_step(*, user, tenant) -> None:
    """Mark onboarding email step completed so app shell / profile gate updates."""
    try:
        ob, created = CreatorOnboardingStatus.objects.get_or_create(
            user=user,
            defaults={"tenant": tenant},
        )
    except Exception:
        logger.exception("Onboarding get_or_create failed after email verify")
        return
    if not created and ob.tenant_id is None and tenant is not None:
        ob.tenant = tenant
        ob.save(update_fields=["tenant"])
    if ob.email_verified_status != StepStatus.COMPLETED:
        ob.email_verified_status = StepStatus.COMPLETED
        if not ob.email_verified_at:
            ob.email_verified_at = timezone.now()
        ob.calculate_completion()


def _verify_email_core(info: Info, input: VerifyEmailInput) -> bool:
    """
    Shared implementation for ``verifyEmail`` and ``confirmEmailVerificationOtp``.

    Root GraphQL mutation resolvers receive ``root`` as ``None``, so mutation methods
    must not call ``self.other_mutation`` — use this helper instead.
    """
    request = info.context.request
    if not request.user.is_authenticated:
        raise Exception("Authentication required.")

    tenant = get_current_tenant()
    email = normalize_signup_email(input.email)
    user_email = normalize_signup_email(
        (getattr(request.user, "email", None) or "").strip()
    )
    if not email or email != user_email:
        raise Exception("Email does not match your account.")

    digits = _otp_digits(input.otp_code)
    if len(digits) != 6:
        return False

    # Match pending row for this user; tolerate legacy rows with tenant=NULL
    # (strict tenant=tenant alone fails after some migrations / restarts).
    verification = (
        EmailVerification.objects.filter(
            email=email,
            otp_code=digits,
            status="pending",
            expires_at__gt=timezone.now(),
            user_id=request.user.pk,
        )
        .filter(Q(tenant=tenant) | Q(tenant__isnull=True))
        .order_by("-created_at")
        .first()
    )
    if not verification:
        return False

    with transaction.atomic():
        verification.status = "verified"
        ver_update_fields = ["status"]
        if verification.tenant_id is None and tenant is not None:
            verification.tenant = tenant
            ver_update_fields.append("tenant")
        verification.save(update_fields=ver_update_fields)

        u = verification.user
        u.email_verified = True
        u.save(update_fields=["email_verified"])

        _sync_onboarding_email_step(user=u, tenant=tenant)

    return True


@strawberry.type
class EmailMutation:
    @strawberry.mutation
    def send_email_verification_otp(self, info: Info) -> SendEmailVerificationOtpResult:
        """
        Email a 6-digit code to the **logged-in user's** account email (same SMTP as password reset).
        Call after saving email on step 1; requires Bearer auth.

        When ``EMAIL_VERIFICATION_INLINE_OTP=True`` (dev / no SMTP) the OTP is returned in
        ``inlineOtp`` instead of being emailed — mirrors ``PASSWORD_RESET_INLINE_OTP``.
        """
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception(
                "Authentication required. Sign in, then request a verification code."
            )
        user = request.user
        tenant = get_current_tenant()
        if not getattr(user, "tenant_id", None) or str(user.tenant_id) != str(tenant.id):
            raise Exception("Tenant mismatch. Refresh the page and try again.")

        raw_email = (getattr(user, "email", None) or "").strip()
        if not raw_email:
            raise Exception(
                "Add and save your email on the previous step before requesting a code."
            )
        email = normalize_signup_email(raw_email)

        EmailVerification.objects.filter(user=user, status="pending").delete()

        token = secrets.token_urlsafe(32)
        otp = f"{secrets.randbelow(1_000_000):06d}"

        EmailVerification.objects.create(
            user=user,
            tenant=tenant,
            email=email,
            token=token,
            otp_code=otp,
            status="pending",
        )

        inline = getattr(settings, "EMAIL_VERIFICATION_INLINE_OTP", False)
        if inline:
            logger.info(
                "EMAIL_VERIFICATION_INLINE_OTP: skipping SMTP for %s; returning code in GraphQL only",
                email,
            )
            return SendEmailVerificationOtpResult(success=True, inline_otp=otp)

        try:
            send_profile_email_verification_otp_email(to_email=email, otp_code=otp)
        except Exception as exc:
            logger.exception("Email verification OTP mail failed for %s", email)
            msg = (
                "We could not send the verification email. "
                "Check server email settings or try again later."
            )
            if getattr(settings, "DEBUG", False):
                detail = (str(exc) or type(exc).__name__).strip()
                if detail:
                    msg = f"{msg} (detail: {detail[:400]})"
            raise Exception(msg) from exc

        return SendEmailVerificationOtpResult(success=True, inline_otp=None)

    @strawberry.mutation
    def confirm_email_verification_otp(
        self, info: Info, input: ConfirmEmailVerificationOtpInput
    ) -> bool:
        """Confirm the 6-digit code for the logged-in user's email."""
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception("Authentication required.")
        email = normalize_signup_email(
            (getattr(request.user, "email", None) or "").strip()
        )
        if not email:
            return False
        digits = _otp_digits(input.otp_code)
        if len(digits) != 6:
            return False
        return _verify_email_core(
            info,
            VerifyEmailInput(email=email, otp_code=digits),
        )

    @strawberry.mutation
    def verify_email(self, info: Info, input: VerifyEmailInput) -> bool:
        """
        Verify pending EmailVerification for this tenant; sets ``User.email_verified``.
        When called from the client, the email in ``input`` must match the logged-in user.
        """
        return _verify_email_core(info, input)

    @strawberry.mutation
    def sync_email_verified_from_firebase(self, info: Info, id_token: str) -> bool:
        """
        After the client completes Firebase email link verification, it sends a fresh
        Firebase ID token; we verify it with Admin SDK and set ``User.email_verified``.
        """
        request = info.context.request
        if not request.user.is_authenticated:
            raise Exception("Authentication required. Please log in and try again.")

        trimmed = (id_token or "").strip()
        if not trimmed:
            return False

        svc = FirebaseAuthService()
        claims = svc.verify_token(trimmed)
        if not claims:
            err = getattr(svc, "last_verify_error", None) or "Could not verify Firebase token."
            raise Exception(err)

        uid = str(claims.get("uid") or "")
        if uid != str(request.user.pk):
            raise Exception("Firebase account does not match the logged-in user.")

        token_email = (claims.get("email") or "").strip().lower()
        user_email = (getattr(request.user, "email", None) or "").strip().lower()
        if not token_email or token_email != user_email:
            raise Exception("Firebase email does not match your account email.")

        if not bool(claims.get("email_verified")):
            return False

        request.user.email_verified = True
        request.user.save(update_fields=["email_verified"])
        tenant = get_current_tenant()
        _sync_onboarding_email_step(user=request.user, tenant=tenant)
        return True
