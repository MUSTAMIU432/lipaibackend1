"""
Premium Live billing engine — "Premium Live Streaming Credit System" PRD.

The rule, everywhere: **100 credits = $10 = 15 minutes**, i.e. one credit every
9 seconds (`elapsed ÷ 9`). Credits are fixed-point decimals; nothing here uses
floats for money or time.

Lifecycle of a live session
---------------------------
1. `start_billing`   — checks the plan and balance, then *reserves* credits so
                       nothing else can spend them (no double-spend).
2. `heartbeat`       — every 5–10 s. Bills the time elapsed by the SERVER clock
                       since the stream started (client timestamps are never
                       trusted), extends the hold when it runs out, and ends the
                       stream with `credit_exhausted` at zero. Replayed sequence
                       numbers are ignored, so a retry can't bill twice.
3. `settle`          — on end: bills the final stretch, moves the consumed credits
                       out of the wallet with ONE immutable `LIVE_USAGE` ledger
                       row, and releases whatever the hold didn't use.

`bill_active_sessions` is the safety net for creators whose app vanished mid-stream.

Every function that touches balances runs in a transaction and locks the wallet
row first, then the reservation, in that order — always the same order, so two
requests can't deadlock.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    CreatorCreditWallet,
    CreditTransactionType,
    LiveBillingEvent,
    LiveCreditReservation,
    LiveEndReason,
    ReservationStatus,
)

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
# Defaults are the PRD's; override in Django settings if the economy changes.

def _dec(name: str, default: str) -> Decimal:
    return Decimal(str(getattr(settings, name, default)))


CREDITS_PER_UNIT = _dec("LIVE_CREDITS_PER_15_MINUTES", "100")
SECONDS_PER_UNIT = _dec("LIVE_SECONDS_PER_UNIT", "900")
CREDIT_USD_VALUE = _dec("CREDIT_USD_VALUE", "0.10")
#: How much is held when a stream starts, and each time the hold runs out.
RESERVE_CHUNK = _dec("LIVE_RESERVE_CHUNK_CREDITS", "100")
#: Smallest spendable balance that may start a stream (10 credits = 90 s).
MIN_START_CREDITS = _dec("LIVE_MIN_START_CREDITS", "10")
#: "Low credit" warning threshold — 5 minutes of stream left.
LOW_CREDIT_SECONDS = int(getattr(settings, "LIVE_LOW_CREDIT_SECONDS", 300))
#: Interval the client is asked to heartbeat at (seconds).
HEARTBEAT_INTERVAL_SECONDS = int(getattr(settings, "LIVE_HEARTBEAT_INTERVAL_SECONDS", 10))
#: A stream that has heartbeated before but gone quiet this long is treated as dropped.
STALE_HEARTBEAT_SECONDS = int(getattr(settings, "LIVE_STALE_HEARTBEAT_SECONDS", 60))

_MICRO = Decimal("0.000001")


class BillingError(Exception):
    """A billing rule refused the request. `code` is stable for clients to branch on."""

    def __init__(self, message: str, code: str = "BILLING_ERROR"):
        super().__init__(message)
        self.code = code


# ── Pure math ────────────────────────────────────────────────────────────────

def credits_for_seconds(seconds) -> Decimal:
    """Credits consumed by `seconds` of live time: seconds × 100 ÷ 900."""
    return (Decimal(int(seconds)) * CREDITS_PER_UNIT / SECONDS_PER_UNIT).quantize(_MICRO, rounding=ROUND_HALF_UP)


def seconds_for_credits(credits) -> int:
    """Whole seconds of live time `credits` buys: credits × 9 (rounded down)."""
    return int((Decimal(str(credits)) * SECONDS_PER_UNIT / CREDITS_PER_UNIT).to_integral_value(rounding=ROUND_FLOOR))


def usd_for_credits(credits) -> Decimal:
    return (Decimal(str(credits)) * CREDIT_USD_VALUE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Snapshots ────────────────────────────────────────────────────────────────

@dataclass
class WalletSnapshot:
    spendable_credits: Decimal
    reserved_credits: Decimal
    total_credits: Decimal
    purchased_credits: Decimal
    free_monthly_credits: Decimal
    gifted_credits: Decimal
    lifetime_credits_used: Decimal
    monetary_value_usd: Decimal
    available_seconds: int
    monthly_reset_at: Optional[datetime]
    can_start_live: bool
    start_blocked_reason: Optional[str]


@dataclass
class BillingSnapshot:
    live_stream_id: str
    status: str
    end_reason: str
    terminated: bool
    credits_reserved: Decimal
    credits_consumed: Decimal
    credits_remaining: Decimal
    elapsed_seconds: int
    remaining_seconds: int
    low_credit: bool
    last_sequence: int
    heartbeat_interval_seconds: int


# ── Wallet ───────────────────────────────────────────────────────────────────

def get_or_create_wallet(profile) -> CreatorCreditWallet:
    wallet, _ = CreatorCreditWallet.objects.get_or_create(creator=profile)
    return wallet


def _lock_wallet(profile) -> CreatorCreditWallet:
    get_or_create_wallet(profile)
    return CreatorCreditWallet.objects.select_for_update().get(creator=profile)


def refresh_monthly_allocation(wallet: CreatorCreditWallet, now: Optional[datetime] = None) -> None:
    """
    Grant this month's plan credits if a month has passed. Lazy on purpose — it
    runs whenever the wallet is read or a stream starts, so no scheduler is needed.
    Skipped while a stream holds credits (the free bucket mustn't shrink under a hold).
    """
    from lipaidox.creator_plans.services import plan_for_creator

    now = now or timezone.now()
    if wallet.reserved_credits > 0:
        return
    plan = plan_for_creator(wallet.creator)
    allowance = Decimal(str(plan.monthly_free_credits)) if plan else Decimal("0")
    if allowance <= 0:
        return
    if wallet.monthly_reset_at and now - wallet.monthly_reset_at < timedelta(days=30):
        return
    wallet.set_monthly_allocation(allowance)


def sync_plan_allocation(profile, plan) -> None:
    """Called when a creator changes plan: their monthly bucket becomes the new plan's."""
    with transaction.atomic():
        wallet = _lock_wallet(profile)
        if wallet.reserved_credits > 0:
            return  # applied on the next refresh, after the stream settles
        wallet.set_monthly_allocation(
            Decimal(str(plan.monthly_free_credits or 0)),
            description=f"{plan.name} plan monthly credits",
        )


def _start_blocker(profile, wallet: CreatorCreditWallet) -> Optional[tuple[str, str]]:
    from lipaidox.creator_plans.services import plan_for_creator

    plan = plan_for_creator(profile)
    if plan is not None and not plan.can_live_stream:
        return ("PLAN_NO_LIVE", f"Live streaming isn't included in the {plan.name} plan. Upgrade to go live.")
    if wallet.spendable_credits < MIN_START_CREDITS:
        return (
            "INSUFFICIENT_CREDITS",
            f"You need at least {MIN_START_CREDITS.normalize():f} credits to go live. Buy credits to continue.",
        )
    return None


def wallet_snapshot(profile) -> WalletSnapshot:
    with transaction.atomic():
        wallet = _lock_wallet(profile)
        refresh_monthly_allocation(wallet)
        wallet.refresh_from_db()
        blocker = _start_blocker(profile, wallet)
    spendable = wallet.spendable_credits
    return WalletSnapshot(
        spendable_credits=spendable,
        reserved_credits=wallet.reserved_credits,
        total_credits=wallet.total_available_credits,
        purchased_credits=wallet.purchased_credits,
        free_monthly_credits=wallet.free_monthly_credits,
        gifted_credits=wallet.gifted_credits,
        lifetime_credits_used=wallet.total_credits_used,
        monetary_value_usd=usd_for_credits(spendable),
        available_seconds=seconds_for_credits(spendable),
        monthly_reset_at=wallet.monthly_reset_at,
        can_start_live=blocker is None,
        start_blocked_reason=blocker[1] if blocker else None,
    )


# ── Snapshot of a session ────────────────────────────────────────────────────

def _snapshot(res: LiveCreditReservation, wallet: CreatorCreditWallet) -> BillingSnapshot:
    active = res.status == ReservationStatus.ACTIVE
    # What's left = the rest of this hold + anything unreserved the hold can grow into.
    remaining = (res.credits_reserved - res.credits_consumed) + (wallet.spendable_credits if active else Decimal("0"))
    remaining_seconds = seconds_for_credits(remaining) if active else 0
    return BillingSnapshot(
        live_stream_id=str(res.live_stream_id),
        status=res.status,
        end_reason=res.end_reason,
        terminated=not active,
        credits_reserved=res.credits_reserved,
        credits_consumed=res.credits_consumed,
        credits_remaining=remaining if active else Decimal("0"),
        elapsed_seconds=res.billed_seconds,
        remaining_seconds=remaining_seconds,
        low_credit=active and remaining_seconds <= LOW_CREDIT_SECONDS,
        last_sequence=res.last_sequence,
        heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
    )


def billing_status(stream_id, profile) -> Optional[BillingSnapshot]:
    """Read-only view of a session's billing (no billing happens here)."""
    res = LiveCreditReservation.objects.filter(live_stream_id=stream_id, creator=profile).select_related("wallet").first()
    if res is None:
        return None
    return _snapshot(res, res.wallet)


# ── Start ────────────────────────────────────────────────────────────────────

def start_billing(stream, now: Optional[datetime] = None) -> LiveCreditReservation:
    """
    Reserve credits for `stream` (already LIVE). Idempotent: a second call for the
    same stream returns the existing reservation. Raises `BillingError` if the
    creator's plan or balance doesn't allow going live.
    """
    profile = stream.creator
    now = now or stream.started_at or timezone.now()
    with transaction.atomic():
        wallet = _lock_wallet(profile)

        existing = LiveCreditReservation.objects.select_for_update().filter(live_stream=stream).first()
        if existing is not None:
            return existing

        refresh_monthly_allocation(wallet, now)
        wallet.refresh_from_db()

        blocker = _start_blocker(profile, wallet)
        if blocker:
            raise BillingError(blocker[1], blocker[0])

        if LiveCreditReservation.objects.filter(creator=profile, status=ReservationStatus.ACTIVE).exists():
            raise BillingError("You already have a live session running.", "ALREADY_LIVE")

        hold = min(RESERVE_CHUNK, wallet.spendable_credits)
        wallet.reserved_credits += hold
        wallet.save(update_fields=["reserved_credits", "updated_at"])
        return LiveCreditReservation.objects.create(
            wallet=wallet,
            creator=profile,
            live_stream=stream,
            credits_reserved=hold,
            started_at=now,
            last_heartbeat_at=now,
        )


# ── Billing a stretch of time ────────────────────────────────────────────────

def _bill_to(res: LiveCreditReservation, wallet: CreatorCreditWallet, now: datetime) -> bool:
    """
    Bring `res` up to date as of `now` (server clock). Extends the hold from the
    wallet's free balance when it runs out. Returns True if the wallet ran dry,
    in which case consumption is capped at what was actually held — the wallet can
    never go negative.
    Caller holds the wallet and reservation locks and saves both.
    """
    elapsed = max(0, int((now - res.started_at).total_seconds()))
    # Computed from the running total, not summed per heartbeat, so rounding
    # never accumulates across thousands of heartbeats.
    owed = credits_for_seconds(elapsed)

    while owed > res.credits_reserved:
        room = wallet.spendable_credits
        if room <= 0:
            break
        extra = min(RESERVE_CHUNK, room)
        wallet.reserved_credits += extra
        res.credits_reserved += extra

    if owed > res.credits_reserved:
        res.credits_consumed = res.credits_reserved
        res.billed_seconds = seconds_for_credits(res.credits_consumed)
        exhausted = True
    else:
        res.credits_consumed = owed
        res.billed_seconds = elapsed
        exhausted = False
    res.last_heartbeat_at = now
    return exhausted


def _settle_locked(res, wallet, stream, reason: str, ended_at: datetime) -> None:
    """Deduct, release, ledger and end the stream. Caller holds the locks."""
    consumed = res.credits_consumed
    held = res.credits_reserved

    wallet.reserved_credits -= held
    wallet.save(update_fields=["reserved_credits", "updated_at"])

    if consumed > 0:
        before = wallet.total_available_credits
        wallet.take_credits(consumed)
        wallet.total_credits_used += consumed
        wallet.save(update_fields=[
            "free_monthly_credits", "purchased_credits", "gifted_credits", "total_credits_used", "updated_at",
        ])
        minutes, seconds = divmod(res.billed_seconds, 60)
        wallet._ledger(
            CreditTransactionType.LIVE_USAGE, -consumed, before,
            live_stream_id=stream.id,
            description=f"Premium Live — {minutes}m {seconds:02d}s",
            metadata={
                "reservation_id": str(res.id),
                "billed_seconds": res.billed_seconds,
                "credits_reserved": str(held),
                "credits_released": str(held - consumed),
                "end_reason": reason,
            },
        )

    res.credits_released = held - consumed
    res.status = ReservationStatus.SETTLED
    res.end_reason = reason
    res.settled_at = timezone.now()
    res.save()

    stream.credits_used = consumed
    stream.end_stream(reason=reason, ended_at=ended_at)


# ── Heartbeat ────────────────────────────────────────────────────────────────

def heartbeat(stream_id, profile, sequence: int, now: Optional[datetime] = None) -> BillingSnapshot:
    """
    Accept a heartbeat for the creator's stream and bill up to `now`.

    Idempotent per sequence: a sequence not greater than the last accepted one is a
    retry or replay and just returns the current state. `now` defaults to the
    server clock and is only overridable so tests can control time.
    """
    now = now or timezone.now()
    with transaction.atomic():
        wallet = _lock_wallet(profile)
        res = (
            LiveCreditReservation.objects.select_for_update()
            .select_related("live_stream")
            .filter(live_stream_id=stream_id, creator=profile)
            .first()
        )
        if res is None:
            raise BillingError("No billing session for this stream.", "NO_SESSION")
        if res.status != ReservationStatus.ACTIVE:
            return _snapshot(res, wallet)
        if sequence <= res.last_sequence:
            return _snapshot(res, wallet)

        previous = res.credits_consumed
        exhausted = _bill_to(res, wallet, now)
        res.last_sequence = sequence
        LiveBillingEvent.objects.create(
            reservation=res,
            creator=profile,
            event_sequence=sequence,
            elapsed_seconds=res.billed_seconds,
            credits_consumed=res.credits_consumed,
            credits_delta=res.credits_consumed - previous,
        )

        if exhausted:
            _settle_locked(res, wallet, res.live_stream, LiveEndReason.CREDIT_EXHAUSTED, now)
        else:
            wallet.save(update_fields=["reserved_credits", "updated_at"])
            res.save()
        return _snapshot(res, wallet)


# ── Settle ───────────────────────────────────────────────────────────────────

def settle(stream, reason: str = LiveEndReason.CREATOR_ENDED, now: Optional[datetime] = None) -> Optional[BillingSnapshot]:
    """
    End the stream and settle its bill. Returns None when the stream never had a
    billing session (it is simply ended). Idempotent: settling twice is harmless.
    """
    now = now or timezone.now()
    with transaction.atomic():
        wallet = _lock_wallet(stream.creator)
        res = (
            LiveCreditReservation.objects.select_for_update()
            .filter(live_stream=stream)
            .first()
        )
        if res is None:
            stream.end_stream(reason=reason, ended_at=now)
            return None
        if res.status == ReservationStatus.ACTIVE:
            exhausted = _bill_to(res, wallet, now)
            _settle_locked(
                res, wallet, stream,
                LiveEndReason.CREDIT_EXHAUSTED if exhausted else reason,
                now,
            )
        return _snapshot(res, wallet)


# ── Sweeper ──────────────────────────────────────────────────────────────────

def bill_active_sessions(now: Optional[datetime] = None) -> dict:
    """
    Bill every running session up to `now` and end the ones that shouldn't keep
    running. Run this every few seconds (`manage.py bill_live_sessions --loop`).

    - A session that heartbeated before but has been silent for STALE_HEARTBEAT_SECONDS
      is a dropped connection: it is settled as `connection_lost`, billed up to its
      LAST heartbeat, so the creator isn't charged for time nobody was watching.
    - A session that has never heartbeated (an older app) is simply billed by time
      and ended when it exhausts.
    """
    now = now or timezone.now()
    summary = {"billed": 0, "ended_exhausted": 0, "ended_lost": 0}
    ids = list(
        LiveCreditReservation.objects.filter(status=ReservationStatus.ACTIVE).values_list("live_stream_id", "creator_id")
    )
    from lipaidox.creator_profile.models import CreatorProfile
    from lipaidox.live_streaming.models import LiveStream

    for stream_id, creator_id in ids:
        try:
            profile = CreatorProfile.objects.get(pk=creator_id)
            with transaction.atomic():
                wallet = _lock_wallet(profile)
                res = LiveCreditReservation.objects.select_for_update().filter(live_stream_id=stream_id).first()
                if res is None or res.status != ReservationStatus.ACTIVE:
                    continue
                stream = LiveStream.objects.get(pk=stream_id)

                silent_for = (now - res.last_heartbeat_at).total_seconds()
                if res.last_sequence > 0 and silent_for > STALE_HEARTBEAT_SECONDS:
                    _bill_to(res, wallet, res.last_heartbeat_at)
                    _settle_locked(res, wallet, stream, LiveEndReason.CONNECTION_LOST, res.last_heartbeat_at)
                    summary["ended_lost"] += 1
                    continue

                # Billing up to `now` moves `last_heartbeat_at`; keep the client's own
                # heartbeat time separate so the staleness test stays honest.
                seen = res.last_heartbeat_at
                exhausted = _bill_to(res, wallet, now)
                if exhausted:
                    _settle_locked(res, wallet, stream, LiveEndReason.CREDIT_EXHAUSTED, now)
                    summary["ended_exhausted"] += 1
                else:
                    res.last_heartbeat_at = seen
                    wallet.save(update_fields=["reserved_credits", "updated_at"])
                    res.save()
                    summary["billed"] += 1
        except Exception:  # noqa: BLE001 — one bad session must not stop the sweep
            logger.exception("bill_active_sessions failed for stream %s", stream_id)
    return summary
