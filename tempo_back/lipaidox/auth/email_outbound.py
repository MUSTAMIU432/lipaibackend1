"""
Transactional email via Django’s email framework (SMTP from settings / .env).
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _forgot_password_otp_prefill_url(*, to_email: str, otp_code: str) -> str:
    """
    Deep link to the SPA forgot-password step (email + optional otp in query for convenience).
    Disable with PASSWORD_RESET_OTP_LINK_ENABLED=False if you only want the plain code in email.
    """
    if not getattr(settings, "PASSWORD_RESET_OTP_LINK_ENABLED", True):
        return ""
    origin = (getattr(settings, "FRONTEND_ORIGIN", "") or "").strip().rstrip("/")
    if not origin:
        return ""
    path = getattr(settings, "PASSWORD_RESET_OTP_PREFILL_PATH", "/forgot-password") or "/forgot-password"
    if not str(path).startswith("/"):
        path = "/" + str(path).lstrip("/")
    query = urlencode({"email": to_email, "step": "otp", "otp": otp_code})
    return f"{origin}{path}?{query}"


def send_password_reset_otp_email(
    *, to_email: str, otp_code: str, expires_minutes: int = 10
) -> None:
    """Send 6-digit password reset code; optionally appends a SPA deep link for one-tap continue."""
    subject = "Your password reset code"
    continue_url = _forgot_password_otp_prefill_url(to_email=to_email, otp_code=otp_code)
    link_block = "\n"
    if continue_url:
        link_block = (
            "\nOr open this link in your browser to go to the reset page (enter the code above manually):\n"
            f"{continue_url}\n\n"
        )
    body = (
        "You requested a password reset.\n\n"
        f"Your verification code is: {otp_code}\n\n"
        f"This code expires in {expires_minutes} minutes.\n"
        f"{link_block}"
        "If you did not request this, ignore this email.\n"
    )
    from_email = (
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or "noreply@localhost"
    ).strip()
    send_mail(
        subject,
        body,
        from_email,
        [to_email],
        fail_silently=False,
    )
    logger.info("Password reset OTP email sent to %s", to_email)


def send_password_reset_link_email(
    *, to_email: str, reset_url: str, expires_minutes: int = 60
) -> None:
    """Send a one-click reset link (opaque token in query string; token is not logged)."""
    subject = "Reset your password"
    body = (
        "You requested a password reset.\n\n"
        f"Open this link to choose a new password (valid for about {expires_minutes} minutes):\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    from_email = (
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or "noreply@localhost"
    ).strip()
    send_mail(
        subject,
        body,
        from_email,
        [to_email],
        fail_silently=False,
    )
    logger.info("Password reset link email sent to %s", to_email)


def send_profile_email_verification_otp_email(
    *, to_email: str, otp_code: str, expires_hours: int = 24
) -> None:
    """Onboarding / profile: 6-digit code to confirm the account email (same SMTP as password reset)."""
    subject = "Verify your email for Lipaidox"
    body = (
        "You are verifying the email on your Lipaidox account.\n\n"
        f"Your verification code is: {otp_code}\n\n"
        f"This code expires in about {expires_hours} hours.\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    from_email = (
        settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or "noreply@localhost"
    ).strip()
    send_mail(
        subject,
        body,
        from_email,
        [to_email],
        fail_silently=False,
    )
    logger.info("Profile email verification OTP sent to %s", to_email)
