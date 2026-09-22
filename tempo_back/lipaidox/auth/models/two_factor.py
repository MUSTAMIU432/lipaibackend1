"""
Two-factor authentication (TOTP) and its two companion pieces: backup
(recovery) codes for when the authenticator app is unavailable, and a
short-lived login challenge for the "password OK, now prove the second
factor" step between `loginUser` and `completeTwoFactorLogin`.

The TOTP secret is stored in plain text. There is no field-level encryption
utility anywhere in this codebase today (the `bank_account_number_encrypted`
column on `PaymentMethod` is the same — a name that promises encryption
`payment/models/method.py` never implements), so this follows the existing
precedent rather than quietly inventing a new, unaudited crypto layer for
just this one field. Backup codes ARE hashed (sha256, via the same
`hash_token` the refresh-token table already uses) since those are
single-use bearer secrets, not something anyone ever needs to read back.
"""
import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


def _challenge_expiry():
    return timezone.now() + timedelta(minutes=10)


class TwoFactorAuth(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField("lipaidox_auth.User", on_delete=models.CASCADE, related_name="two_factor")

    secret = models.CharField(max_length=64)
    # False while a setup is in progress but not yet confirmed with a valid code.
    enabled = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "two_factor_auth"
        app_label = "lipaidox_auth"

    def __str__(self):
        return f"TwoFactorAuth({self.user.username}, enabled={self.enabled})"


class BackupCode(models.Model):
    """One single-use recovery code. Ten are minted whenever 2FA is
    confirmed or codes are regenerated; each can complete a login exactly
    once in place of a TOTP code, then is marked used."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "two_factor_backup_codes"
        app_label = "lipaidox_auth"
        indexes = [models.Index(fields=["user", "used_at"])]

    def __str__(self):
        return f"BackupCode({self.user.username}, used={self.used_at is not None})"


class TwoFactorLoginChallenge(models.Model):
    """Issued by `loginUser` in place of real tokens when the account has
    2FA enabled. The raw `token` is handed to the client and never stored;
    only its hash is kept, the same pattern `RefreshToken` uses for its
    opaque token. `completeTwoFactorLogin` exchanges a valid, unexpired,
    unused challenge + a correct code (TOTP or backup) for the real
    `AuthPayload` that `loginUser` would otherwise have returned directly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="two_factor_challenges")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(default=_challenge_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "two_factor_login_challenges"
        app_label = "lipaidox_auth"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and not self.is_expired

    def __str__(self):
        return f"TwoFactorLoginChallenge({self.user.username})"


def generate_backup_codes(user, count: int = 10) -> list[str]:
    """Replaces the user's backup codes with `count` fresh ones and returns
    the RAW codes — the only time they're ever available in plain text."""
    from ..jwt_auth import hash_token

    BackupCode.objects.filter(user=user).delete()
    codes = []
    rows = []
    for _ in range(count):
        # 10 hex chars, grouped for readability: e.g. "3f9a-2c8e1b".
        raw = secrets.token_hex(5)
        formatted = f"{raw[:4]}-{raw[4:]}"
        codes.append(formatted)
        rows.append(BackupCode(user=user, code_hash=hash_token(formatted)))
    BackupCode.objects.bulk_create(rows)
    return codes
