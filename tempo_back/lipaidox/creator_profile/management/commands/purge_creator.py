"""
Management command: purge_creator

Reversibly purges all data owned by a creator (by username or user ID).
Deletion order respects FK constraints: child rows first, then the user.

Usage:
    # Dry-run (default — never deletes anything)
    python manage.py purge_creator --username alice

    # Live run — requires explicit confirmation flag
    python manage.py purge_creator --username alice --confirm

    # By user ID
    python manage.py purge_creator --user-id 7f3a1b2c-... --confirm
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Purge all data owned by a creator. Dry-run by default; pass --confirm to execute."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--username", type=str, help="Creator's username (profile.username)")
        group.add_argument("--user-id", dest="user_id", type=str, help="User UUID / PK")
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Actually delete rows. Without this flag the command is a dry-run.",
        )

    def handle(self, *args, **options):
        from lipaidox.auth.models import User
        from lipaidox.creator_profile.models import CreatorProfile

        username = options.get("username")
        user_id = options.get("user_id")
        confirm = options["confirm"]

        # ── Resolve creator profile ──────────────────────────────────────────
        try:
            if username:
                profile = CreatorProfile.objects.select_related("user").get(username=username)
            else:
                profile = CreatorProfile.objects.select_related("user").get(user_id=user_id)
        except CreatorProfile.DoesNotExist:
            raise CommandError(
                f"No CreatorProfile found for {'username=' + repr(username) if username else 'user_id=' + repr(user_id)}"
            )

        user = profile.user
        self.stdout.write(
            self.style.WARNING(
                f"{'[DRY-RUN] ' if not confirm else ''}Targeting creator: "
                f"username={profile.username!r}  user_id={user.pk}"
            )
        )

        # ── Count rows per table ─────────────────────────────────────────────
        counts = _count_rows(profile, user)

        self.stdout.write("\nRows to be deleted:")
        total = 0
        for table, count in counts.items():
            self.stdout.write(f"  {table:<45} {count:>6} row(s)")
            total += count
        self.stdout.write(f"\n  {'TOTAL':<45} {total:>6} row(s)\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to delete. Exiting."))
            return

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run complete. No data was deleted.\n"
                    "Re-run with --confirm to execute the purge."
                )
            )
            return

        # ── Execute inside a single transaction ──────────────────────────────
        self.stdout.write(self.style.ERROR("Starting irreversible deletion…"))
        started_at = datetime.now(tz=timezone.utc)

        with transaction.atomic():
            deleted = _delete_rows(profile, user)

        finished_at = datetime.now(tz=timezone.utc)
        elapsed = (finished_at - started_at).total_seconds()

        # ── Deletion summary ─────────────────────────────────────────────────
        self.stdout.write("\nDeletion summary:")
        grand_total = 0
        for table, count in deleted.items():
            self.stdout.write(f"  {table:<45} {count:>6} deleted")
            grand_total += count
        self.stdout.write(
            f"\n  {'TOTAL':<45} {grand_total:>6} deleted  ({elapsed:.2f}s)"
        )

        logger.info(
            "purge_creator: deleted %d rows for creator username=%r user_id=%s  elapsed=%.2fs",
            grand_total,
            profile.username,
            user.pk,
            elapsed,
        )

        self.stdout.write(self.style.SUCCESS("\nPurge complete."))


# ── Helpers ─────────────────────────────────────────────────────────────────

def _count_rows(profile, user) -> dict[str, int]:
    return _apply(profile, user, dry_run=True)


def _delete_rows(profile, user) -> dict[str, int]:
    return _apply(profile, user, dry_run=False)


def _apply(profile, user, *, dry_run: bool) -> dict[str, int]:
    """
    Walk tables in FK-safe order (children before parents).
    dry_run=True: count only.  dry_run=False: delete and return deleted counts.
    """
    from lipaidox.content.models import Content, ContentMedia, ContentSeries, ContentAttachment, ContentTag, ContentAccessRule
    from lipaidox.kyc.models import VerificationDocument, KYCStatus, BusinessVerification
    from lipaidox.monetization.models import MonetizationSettings, MonetizationPriceHistory
    from lipaidox.subscriptions.models import Subscription, SubscriptionPayment
    from lipaidox.wallet.models import CreatorWallet, WalletTransaction, Transaction, PayoutTransaction
    from lipaidox.creator_profile.models import Follow
    from lipaidox.auth.models import (
        EmailVerification, PhoneVerification, RefreshToken,
        PasswordResetToken, PasswordResetOtp,
    )

    results: dict[str, int] = {}

    def _handle(label: str, qs):
        count = qs.count()
        results[label] = count
        if not dry_run and count:
            qs.delete()

    # Content leaf tables (before Content itself)
    content_qs = Content.objects.filter(creator=profile)
    content_ids = list(content_qs.values_list("id", flat=True))

    _handle("content_tags", ContentTag.objects.filter(content_id__in=content_ids))
    _handle("content_media", ContentMedia.objects.filter(content_id__in=content_ids))
    _handle("content_attachments", ContentAttachment.objects.filter(content_id__in=content_ids))
    _handle("content_access_rules", ContentAccessRule.objects.filter(content_id__in=content_ids))
    _handle("content", content_qs)
    _handle("content_series", ContentSeries.objects.filter(creator=profile))

    # KYC — delete kyc_status first so current_document SET_NULL runs before we delete documents
    _handle("kyc_status", KYCStatus.objects.filter(creator=profile))
    try:
        _handle("business_verifications", BusinessVerification.objects.filter(creator=profile))
    except Exception:
        pass
    _handle("verification_documents", VerificationDocument.objects.filter(creator=profile))

    # Monetization
    _handle("monetization_settings", MonetizationSettings.objects.filter(creator=profile))
    _handle("monetization_price_history", MonetizationPriceHistory.objects.filter(creator=profile))

    # Subscriptions
    _handle("subscriptions", Subscription.objects.filter(creator=profile))
    _handle("subscription_payments", SubscriptionPayment.objects.filter(creator=profile))

    # Wallet
    try:
        wallet_qs = CreatorWallet.objects.filter(creator=profile)
        wallet_ids = list(wallet_qs.values_list("id", flat=True))
        _handle("wallet_transactions", WalletTransaction.objects.filter(wallet_id__in=wallet_ids))
        _handle("creator_wallets", wallet_qs)
    except Exception:
        pass

    try:
        _handle("transactions", Transaction.objects.filter(creator=profile))
    except Exception:
        pass

    try:
        _handle("payout_transactions", PayoutTransaction.objects.filter(creator=profile))
    except Exception:
        pass

    # Follows — both sides use FK to User
    _handle("follows_as_followed", Follow.objects.filter(followed=user))
    _handle("follows_as_follower", Follow.objects.filter(follower=user))

    # Creator profile
    _handle("creator_profiles", type(profile).objects.filter(pk=profile.pk))

    # Auth tokens / verifications (leaf before user)
    _handle("email_verifications", EmailVerification.objects.filter(user=user))
    _handle("refresh_tokens", RefreshToken.objects.filter(user=user))
    _handle("password_reset_tokens", PasswordResetToken.objects.filter(user=user))
    _handle("password_reset_otps", PasswordResetOtp.objects.filter(user=user))
    try:
        _handle("phone_verifications", PhoneVerification.objects.filter(user=user))
    except Exception:
        pass

    # User last (parent of everything else)
    _handle("users", type(user).objects.filter(pk=user.pk))

    return results
