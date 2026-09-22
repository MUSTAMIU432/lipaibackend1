"""
Two-factor authentication mutations: TOTP setup/confirm/disable, backup
(recovery) code regeneration, and the login-time second step.

Every state change here is server-enforced: `enabled` only ever flips to
True inside `confirm_two_factor_setup`, and only after `pyotp` verifies a
real code against the secret just issued; disabling and regenerating codes
both require a fresh valid code too, not just being logged in — someone
with a stolen session token alone can't turn 2FA off.
"""
import pyotp
import strawberry
from typing import Optional

from django.utils import timezone

from ..jwt_auth import hash_token
from ..models import BackupCode, TwoFactorAuth, TwoFactorLoginChallenge, User, generate_backup_codes
from ..schema.two_factor_schema import TwoFactorConfirmResult, TwoFactorSetupType
from ..schema.token_schema import AuthPayload

ISSUER = "Lipaidox"


def _require_user(info: strawberry.types.Info) -> User:
    user = info.context.request.user
    if not getattr(user, "is_authenticated", False):
        raise Exception("Authentication required.")
    return user


def verify_totp_or_backup(user, code: str) -> bool:
    """Tries the code as a TOTP first, then as an unused backup code.
    A matching backup code is consumed (marked used) so it can't be
    replayed — that's the whole point of a single-use recovery code."""
    code = (code or "").strip()
    if not code:
        return False

    tfa = TwoFactorAuth.objects.filter(user=user, enabled=True).first()
    if tfa is not None:
        totp = pyotp.TOTP(tfa.secret)
        if totp.verify(code, valid_window=1):
            return True

    candidate_hash = hash_token(code.lower())
    backup = BackupCode.objects.filter(user=user, code_hash=candidate_hash, used_at__isnull=True).first()
    if backup is not None:
        backup.used_at = timezone.now()
        backup.save(update_fields=["used_at"])
        return True

    return False


@strawberry.type
class TwoFactorMutation:
    @strawberry.mutation
    def begin_two_factor_setup(self, info: strawberry.types.Info) -> TwoFactorSetupType:
        """Issues a fresh secret and stores it un-enabled. Calling this
        again before confirming just replaces the pending secret — no
        harm, since nothing is active until `confirmTwoFactorSetup`."""
        user = _require_user(info)
        if TwoFactorAuth.objects.filter(user=user, enabled=True).exists():
            raise Exception("Two-factor authentication is already enabled. Disable it before setting up again.")

        secret = pyotp.random_base32()
        TwoFactorAuth.objects.update_or_create(
            user=user,
            defaults={"secret": secret, "enabled": False, "confirmed_at": None},
        )
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email or user.username, issuer_name=ISSUER)
        return TwoFactorSetupType(secret=secret, provisioningUri=uri)

    @strawberry.mutation
    def confirm_two_factor_setup(self, info: strawberry.types.Info, code: str) -> TwoFactorConfirmResult:
        user = _require_user(info)
        tfa = TwoFactorAuth.objects.filter(user=user, enabled=False).first()
        if tfa is None:
            raise Exception("Start setup with beginTwoFactorSetup first.")

        totp = pyotp.TOTP(tfa.secret)
        if not totp.verify((code or "").strip(), valid_window=1):
            raise Exception("That code didn't match. Check your authenticator app and try again.")

        tfa.enabled = True
        tfa.confirmed_at = timezone.now()
        tfa.save(update_fields=["enabled", "confirmed_at"])

        codes = generate_backup_codes(user)
        return TwoFactorConfirmResult(enabled=True, backupCodes=codes)

    @strawberry.mutation
    def disable_two_factor(self, info: strawberry.types.Info, code: str) -> bool:
        user = _require_user(info)
        if not TwoFactorAuth.objects.filter(user=user, enabled=True).exists():
            return True  # already off
        if not verify_totp_or_backup(user, code):
            raise Exception("That code didn't match. Enter a current authenticator code or an unused backup code.")

        TwoFactorAuth.objects.filter(user=user).delete()
        BackupCode.objects.filter(user=user).delete()
        return True

    @strawberry.mutation
    def regenerate_backup_codes(self, info: strawberry.types.Info, code: str) -> list[str]:
        """Invalidates every existing backup code and mints ten new ones —
        the Account Security screen's "recovery codes" refresh."""
        user = _require_user(info)
        if not TwoFactorAuth.objects.filter(user=user, enabled=True).exists():
            raise Exception("Two-factor authentication isn't enabled.")
        if not verify_totp_or_backup(user, code):
            raise Exception("That code didn't match. Enter a current authenticator code or an unused backup code.")
        return generate_backup_codes(user)

    @strawberry.mutation
    def complete_two_factor_login(
        self, info: strawberry.types.Info, challenge_token: str, code: str
    ) -> AuthPayload:
        """The second step `loginUser` hands off to when the account has
        2FA enabled — exchanges the challenge + a correct code for the
        real tokens `loginUser` would otherwise have returned directly."""
        from .user_mutation import _issue_auth_payload  # local import: avoids a circular import at module load

        token_hash = hash_token(challenge_token)
        challenge = TwoFactorLoginChallenge.objects.select_related("user").filter(token_hash=token_hash).first()
        if challenge is None or not challenge.is_valid:
            raise Exception("This login attempt has expired. Sign in again.")

        if not verify_totp_or_backup(challenge.user, code):
            raise Exception("That code didn't match. Try again.")

        challenge.used_at = timezone.now()
        challenge.save(update_fields=["used_at"])

        payload = _issue_auth_payload(info, challenge.user)
        if challenge.user.is_first_login:
            User.objects.filter(pk=challenge.user.pk).update(is_first_login=False)
        return payload
