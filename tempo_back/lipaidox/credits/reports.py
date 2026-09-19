"""
Admin reporting for the live-credit economy (PRD §51, §68, §69, §89).

Everything is computed from the immutable ledger and the reservations — never from
cached counters — so a report can always be re-derived and audited.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Avg, Sum
from django.utils import timezone

from .live_billing import CREDITS_PER_UNIT, SECONDS_PER_UNIT
from .models import (
    CreatorCreditLedger,
    CreatorCreditWallet,
    CreditPurchase,
    CreditTransactionStatus,
    CreditTransactionType as T,
    CreditType,
    LiveCreditReservation,
    ReservationStatus,
)

ZERO = Decimal("0")


def _sum(qs, field: str) -> Decimal:
    return qs.aggregate(total=Sum(field))["total"] or ZERO


@dataclass
class CreditsReport:
    from_date: datetime
    to_date: datetime
    credits_purchased: Decimal
    credits_consumed: Decimal
    credits_refunded: Decimal
    bonus_credits_issued: Decimal
    adjustments_net: Decimal
    purchases_count: int
    purchase_revenue_usd: Decimal
    live_sessions: int
    average_credits_per_session: Decimal
    average_session_seconds: int
    credit_exhaustion_rate: Decimal   # exhausted sessions ÷ settled sessions, 0–1
    credits_held_now: Decimal
    active_sessions_now: int


def credits_report(
    start: Optional[datetime] = None, end: Optional[datetime] = None, creator_user_id=None
) -> CreditsReport:
    end = end or timezone.now()
    start = start or end - timedelta(days=30)

    ledger = CreatorCreditLedger.objects.filter(created_at__gte=start, created_at__lte=end)
    resv = LiveCreditReservation.objects.filter(
        status=ReservationStatus.SETTLED, settled_at__gte=start, settled_at__lte=end
    )
    purchases = CreditPurchase.objects.filter(
        credit_type=CreditType.CREATOR_CREDIT,
        status=CreditTransactionStatus.COMPLETED,
        completed_at__gte=start, completed_at__lte=end,
    )
    if creator_user_id:
        ledger = ledger.filter(creator__user_id=creator_user_id)
        resv = resv.filter(creator__user_id=creator_user_id)
        purchases = purchases.filter(user_id=creator_user_id)

    def gains(*types):
        return _sum(ledger.filter(transaction_type__in=types, credits_delta__gt=0), "credits_delta")

    consumed = -_sum(ledger.filter(transaction_type__in=[T.LIVE_USAGE, T.SPENT]), "credits_delta")

    settled = resv.count()
    exhausted = resv.filter(end_reason="credit_exhausted").count()
    agg = resv.aggregate(avg_credits=Avg("credits_consumed"), avg_seconds=Avg("billed_seconds"))

    active = LiveCreditReservation.objects.filter(status=ReservationStatus.ACTIVE)
    if creator_user_id:
        active = active.filter(creator__user_id=creator_user_id)

    return CreditsReport(
        from_date=start,
        to_date=end,
        credits_purchased=gains(T.PURCHASE),
        credits_consumed=consumed,
        credits_refunded=gains(T.REFUNDED),
        bonus_credits_issued=gains(T.ADMIN_GIFT, T.MONTHLY_ALLOCATION),
        adjustments_net=_sum(ledger.filter(transaction_type=T.ADJUSTMENT), "credits_delta"),
        purchases_count=purchases.count(),
        purchase_revenue_usd=_sum(purchases, "amount_paid"),
        live_sessions=settled,
        average_credits_per_session=Decimal(str(agg["avg_credits"] or 0)).quantize(Decimal("0.01")),
        average_session_seconds=int(agg["avg_seconds"] or 0),
        credit_exhaustion_rate=(Decimal(exhausted) / Decimal(settled)).quantize(Decimal("0.0001")) if settled else ZERO,
        credits_held_now=_sum(active, "credits_reserved"),
        active_sessions_now=active.count(),
    )


@dataclass
class LiveDashboard:
    active_sessions: int
    credits_per_minute: Decimal      # what the running sessions burn together, per minute
    credits_held: Decimal
    credits_consumed_today: Decimal
    sessions_today: int


def live_dashboard(now: Optional[datetime] = None) -> LiveDashboard:
    now = now or timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    active = LiveCreditReservation.objects.filter(status=ReservationStatus.ACTIVE)
    today = LiveCreditReservation.objects.filter(started_at__gte=day_start)
    n = active.count()
    per_minute = (Decimal(n) * CREDITS_PER_UNIT * 60 / SECONDS_PER_UNIT).quantize(Decimal("0.01"))
    return LiveDashboard(
        active_sessions=n,
        credits_per_minute=per_minute,
        credits_held=_sum(active, "credits_reserved"),
        credits_consumed_today=_sum(today, "credits_consumed"),
        sessions_today=today.count(),
    )


def sessions_queryset(status: Optional[str] = None):
    qs = LiveCreditReservation.objects.select_related("live_stream", "creator")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-started_at")


def wallet_totals() -> dict:
    """Platform-wide liability: credits sitting in creator wallets."""
    agg = CreatorCreditWallet.objects.aggregate(
        purchased=Sum("purchased_credits"), free=Sum("free_monthly_credits"),
        gifted=Sum("gifted_credits"), reserved=Sum("reserved_credits"),
    )
    return {k: v or ZERO for k, v in agg.items()}
