"""GraphQL types for the live-credit wallet and per-session billing."""
from datetime import datetime
from typing import List, Optional

import strawberry

from .credits_schema import CreatorCreditLedgerType
from ..live_billing import BillingSnapshot, WalletSnapshot, CREDITS_PER_UNIT, SECONDS_PER_UNIT, CREDIT_USD_VALUE, MIN_START_CREDITS


# Credits travel as floats in GraphQL: DECIMAL(20,6) never exceeds 15 significant
# digits in practice, and every client formats them for display. The database and
# all arithmetic stay Decimal.
@strawberry.type
class LiveCreditWalletType:
    availableCredits: float          # spendable: total minus what a live in progress holds
    reservedCredits: float
    totalCredits: float
    purchasedCredits: float
    freeMonthlyCredits: float
    giftedCredits: float
    lifetimeCreditsUsed: float
    monetaryValueUsd: float
    availableSeconds: int
    monthlyResetAt: Optional[datetime]
    canStartLive: bool
    startBlockedReason: Optional[str]
    minStartCredits: float
    creditsPer15Minutes: float
    secondsPerCredit: float
    creditUsdValue: float

    @classmethod
    def from_snapshot(cls, s: WalletSnapshot) -> "LiveCreditWalletType":
        return cls(
            availableCredits=float(s.spendable_credits),
            reservedCredits=float(s.reserved_credits),
            totalCredits=float(s.total_credits),
            purchasedCredits=float(s.purchased_credits),
            freeMonthlyCredits=float(s.free_monthly_credits),
            giftedCredits=float(s.gifted_credits),
            lifetimeCreditsUsed=float(s.lifetime_credits_used),
            monetaryValueUsd=float(s.monetary_value_usd),
            availableSeconds=s.available_seconds,
            monthlyResetAt=s.monthly_reset_at,
            canStartLive=s.can_start_live,
            startBlockedReason=s.start_blocked_reason,
            minStartCredits=float(MIN_START_CREDITS),
            creditsPer15Minutes=float(CREDITS_PER_UNIT),
            secondsPerCredit=float(SECONDS_PER_UNIT / CREDITS_PER_UNIT),
            creditUsdValue=float(CREDIT_USD_VALUE),
        )


@strawberry.type
class LiveBillingStatusType:
    liveStreamId: strawberry.ID
    status: str                       # active | settled
    endReason: Optional[str]          # creator_ended | credit_exhausted | forced_ended | connection_lost
    terminated: bool
    creditsReserved: float
    creditsConsumed: float
    creditsRemaining: float
    elapsedSeconds: int
    remainingSeconds: int
    lowCredit: bool
    lastSequence: int
    heartbeatIntervalSeconds: int

    @classmethod
    def from_snapshot(cls, s: BillingSnapshot) -> "LiveBillingStatusType":
        return cls(
            liveStreamId=strawberry.ID(s.live_stream_id),
            status=s.status,
            endReason=s.end_reason or None,
            terminated=s.terminated,
            creditsReserved=float(s.credits_reserved),
            creditsConsumed=float(s.credits_consumed),
            creditsRemaining=float(s.credits_remaining),
            elapsedSeconds=s.elapsed_seconds,
            remainingSeconds=s.remaining_seconds,
            lowCredit=s.low_credit,
            lastSequence=s.last_sequence,
            heartbeatIntervalSeconds=s.heartbeat_interval_seconds,
        )


# ── Transactions (creator) ───────────────────────────────────────────────────

@strawberry.type
class LiveCreditTransactionPage:
    items: List[CreatorCreditLedgerType]
    total: int
    page: int
    pages: int
    limit: int


# ── Admin ────────────────────────────────────────────────────────────────────

@strawberry.type
class AdminLiveSessionType:
    liveStreamId: strawberry.ID
    title: str
    creatorId: strawberry.ID
    creatorUsername: str
    status: str                      # active | settled
    endReason: Optional[str]
    startedAt: datetime
    lastHeartbeatAt: datetime
    elapsedSeconds: int
    creditsReserved: float
    creditsConsumed: float
    creditsPerMinute: float
    settledAt: Optional[datetime]

    @classmethod
    def from_model(cls, r) -> "AdminLiveSessionType":
        return cls(
            liveStreamId=strawberry.ID(str(r.live_stream_id)),
            title=r.live_stream.title,
            creatorId=strawberry.ID(str(r.creator_id)),
            creatorUsername=r.creator.username,
            status=r.status,
            endReason=r.end_reason or None,
            startedAt=r.started_at,
            lastHeartbeatAt=r.last_heartbeat_at,
            elapsedSeconds=r.billed_seconds,
            creditsReserved=float(r.credits_reserved),
            creditsConsumed=float(r.credits_consumed),
            creditsPerMinute=float(CREDITS_PER_UNIT * 60 / SECONDS_PER_UNIT),
            settledAt=r.settled_at,
        )


@strawberry.type
class AdminLiveDashboardType:
    activeSessions: int
    creditsPerMinute: float
    creditsHeld: float
    creditsConsumedToday: float
    sessionsToday: int


@strawberry.type
class AdminCreditsReportType:
    fromDate: datetime
    toDate: datetime
    creditsPurchased: float
    creditsConsumed: float
    creditsRefunded: float
    bonusCreditsIssued: float
    adjustmentsNet: float
    purchasesCount: int
    purchaseRevenueUsd: float
    liveSessions: int
    averageCreditsPerSession: float
    averageSessionSeconds: int
    creditExhaustionRate: float
    creditsHeldNow: float
    activeSessionsNow: int

    @classmethod
    def from_report(cls, r) -> "AdminCreditsReportType":
        return cls(
            fromDate=r.from_date, toDate=r.to_date,
            creditsPurchased=float(r.credits_purchased), creditsConsumed=float(r.credits_consumed),
            creditsRefunded=float(r.credits_refunded), bonusCreditsIssued=float(r.bonus_credits_issued),
            adjustmentsNet=float(r.adjustments_net), purchasesCount=r.purchases_count,
            purchaseRevenueUsd=float(r.purchase_revenue_usd), liveSessions=r.live_sessions,
            averageCreditsPerSession=float(r.average_credits_per_session),
            averageSessionSeconds=r.average_session_seconds,
            creditExhaustionRate=float(r.credit_exhaustion_rate),
            creditsHeldNow=float(r.credits_held_now), activeSessionsNow=r.active_sessions_now,
        )


@strawberry.type
class AuditLogType:
    id: strawberry.ID
    actorId: Optional[strawberry.ID]
    actorUsername: Optional[str]
    action: str
    entityType: str
    entityId: Optional[strawberry.ID]
    oldValue: strawberry.scalars.JSON
    newValue: strawberry.scalars.JSON
    ipAddress: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, a) -> "AuditLogType":
        return cls(
            id=strawberry.ID(str(a.id)),
            actorId=strawberry.ID(str(a.actor_id)) if a.actor_id else None,
            actorUsername=a.actor.username if a.actor_id else None,
            action=a.action, entityType=a.entity_type,
            entityId=strawberry.ID(str(a.entity_id)) if a.entity_id else None,
            oldValue=a.old_value, newValue=a.new_value,
            ipAddress=a.ip_address, createdAt=a.created_at,
        )
