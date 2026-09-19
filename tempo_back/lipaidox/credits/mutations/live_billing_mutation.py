from decimal import Decimal, InvalidOperation
from typing import Optional

import strawberry
from django.db import transaction

from lipaidox.auth.permissions import UserRoles

from .. import live_billing
from ..audit import record_audit
from ..models import CreatorCreditLedger, CreatorCreditWallet, CreditTransactionType, LiveEndReason
from ..schema.credits_schema import CreatorCreditLedgerType
from ..schema.live_billing_schema import LiveBillingStatusType


def _creator_profile(info):
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise Exception("Authentication required")
    if user.role != UserRoles.CREATOR:
        raise Exception("Creator access required")
    from lipaidox.creator_profile.models import CreatorProfile

    profile = CreatorProfile.objects.filter(user=user).first()
    if profile is None:
        raise Exception("Creator profile not found")
    return profile


def _admin(info):
    user = info.context.request.user
    if not user or not user.is_authenticated:
        raise Exception("Authentication required")
    if user.role not in [UserRoles.ADMIN, "superadmin"]:
        raise Exception("Admin access required")
    return user


@strawberry.type
class LiveBillingMutation:
    @strawberry.mutation
    def live_billing_heartbeat(
        self, info: strawberry.types.Info, streamId: strawberry.ID, sequence: int
    ) -> LiveBillingStatusType:
        """
        Billing heartbeat, every 5–10 s while live. Time is measured by the SERVER
        clock from when the stream started; `sequence` only makes retries safe (a
        repeated or lower sequence is ignored, never billed twice). When the reply
        says `terminated`, the stream has ended — read `endReason`.
        """
        profile = _creator_profile(info)
        try:
            return LiveBillingStatusType.from_snapshot(live_billing.heartbeat(streamId, profile, sequence))
        except live_billing.BillingError as exc:
            raise Exception(str(exc))

    @strawberry.mutation
    def admin_adjust_creator_credits(
        self,
        info: strawberry.types.Info,
        creatorUserId: strawberry.ID,
        credits: str,
        reason: str,
        idempotencyKey: Optional[str] = None,
    ) -> CreatorCreditLedgerType:
        """
        Manual correction by an administrator. Never edits history: it appends an
        ADJUSTMENT ledger row (positive adds gifted credits; negative takes credits
        that aren't held for a live in progress). `reason` is required and is kept
        on the row. Every adjustment is written to the audit trail. `idempotencyKey`
        makes a retry return the original entry instead of adjusting twice.
        """
        admin = _admin(info)
        if not reason.strip():
            raise Exception("A reason is required for a manual adjustment.")
        try:
            amount = Decimal(credits)
        except InvalidOperation:
            raise Exception("credits must be a number, e.g. \"25.5\" or \"-10\".")
        if amount == 0:
            raise Exception("Adjustment can't be zero.")

        from lipaidox.creator_profile.models import CreatorProfile

        profile = CreatorProfile.objects.filter(user_id=creatorUserId).first()
        if profile is None:
            raise Exception("Creator not found")

        with transaction.atomic():
            live_billing.get_or_create_wallet(profile)
            wallet = CreatorCreditWallet.objects.select_for_update().get(creator=profile)
            if idempotencyKey:
                prior = CreatorCreditLedger.objects.filter(
                    wallet=wallet, transaction_type=CreditTransactionType.ADJUSTMENT,
                    metadata__idempotency_key=idempotencyKey,
                ).first()
                if prior is not None:
                    return CreatorCreditLedgerType.from_model(prior)
            before = wallet.total_available_credits
            if amount > 0:
                wallet.gifted_credits += amount
                wallet.total_credits_gifted += amount
                wallet.save(update_fields=["gifted_credits", "total_credits_gifted", "updated_at"])
            else:
                take = -amount
                if take > wallet.spendable_credits:
                    raise Exception("Can't remove more than the spendable balance (credits held for a live are excluded).")
                wallet.take_credits(take)
                wallet.save(update_fields=["free_monthly_credits", "purchased_credits", "gifted_credits", "updated_at"])
            entry = wallet._ledger(
                CreditTransactionType.ADJUSTMENT, amount, before,
                description=f"Admin adjustment: {reason.strip()}",
                metadata={
                    "admin_user_id": str(admin.id), "reason": reason.strip(),
                    **({"idempotency_key": idempotencyKey} if idempotencyKey else {}),
                },
            )
            record_audit(
                info, "ADMIN_CREDIT_ADJUSTMENT", "creator_credit_wallet", wallet.id,
                old={"total_credits": str(before)},
                new={"total_credits": str(wallet.total_available_credits), "delta": str(amount), "reason": reason.strip()},
            )
        return CreatorCreditLedgerType.from_model(entry)

    @strawberry.mutation
    def admin_terminate_live(self, info: strawberry.types.Info, streamId: strawberry.ID) -> LiveBillingStatusType:
        """Force-end a live session. The creator is billed for the time actually streamed."""
        _admin(info)
        from lipaidox.live_streaming.models import LiveStream, LiveStreamStatus

        stream = LiveStream.objects.filter(pk=streamId).select_related("creator").first()
        if stream is None:
            raise Exception("Stream not found")
        if stream.status != LiveStreamStatus.LIVE:
            raise Exception("Only a live stream can be terminated.")
        snap = live_billing.settle(stream, reason=LiveEndReason.FORCED_ENDED)
        record_audit(
            info, "LIVE_FORCE_ENDED", "live_stream", stream.id,
            new={"credits_consumed": str(snap.credits_consumed) if snap else "0", "billed": snap is not None},
        )
        if snap is None:
            raise Exception("This stream has no billing session; it was ended without a bill.")
        return LiveBillingStatusType.from_snapshot(snap)
