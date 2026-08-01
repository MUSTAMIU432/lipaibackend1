import uuid
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class PasswordResetOtpStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    USED = "used", "Used"
    EXPIRED = "expired", "Expired"
    SUPERSEDED = "superseded", "Superseded"


def _otp_default_expiry():
    return timezone.now() + timedelta(minutes=10)


class PasswordResetOtp(models.Model):
    """Single-use 6-digit email OTP for password reset (plain code never stored)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
    )
    code_hash = models.CharField(max_length=128)
    status = models.CharField(
        max_length=20,
        choices=PasswordResetOtpStatus.choices,
        default=PasswordResetOtpStatus.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(default=_otp_default_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_otps"
        app_label = "lipaidox_auth"
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"PasswordResetOtp({self.user_id}, {self.status})"

    @staticmethod
    def hash_code(plain: str) -> str:
        return make_password(plain)

    def verify_code(self, plain: str) -> bool:
        return check_password(plain, self.code_hash)
