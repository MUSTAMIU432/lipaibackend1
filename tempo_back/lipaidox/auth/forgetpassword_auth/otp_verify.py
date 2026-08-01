"""
Check a pending password-reset OTP without completing the reset.

Mirrors the lookup rules in ``password_mutation.PasswordMutation.reset_password``:
same tenant, email, pending + unexpired row, attempt cap, and Django password hash check.
"""

from __future__ import annotations

from django.db.models import F
from django.utils import timezone

from ..models import PasswordResetOtp, PasswordResetOtpStatus
from ..validation import normalize_signup_email
from multitenant.utils.tenant_context import get_current_tenant

# Single source for OTP verify + ``password_mutation.reset_password``.
MAX_OTP_ATTEMPTS = 5


def verify_password_reset_otp(*, email: str, otp_code: str) -> bool:
    tenant = get_current_tenant()
    email_norm = normalize_signup_email(email)
    digits_only = "".join(c for c in (otp_code or "") if c.isdigit())
    if len(digits_only) != 6:
        return False

    record = (
        PasswordResetOtp.objects.filter(
            user__email__iexact=email_norm,
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
        PasswordResetOtp.objects.filter(pk=record.pk).update(attempts=F("attempts") + 1)
        return False

    return True
