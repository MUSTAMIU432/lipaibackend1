from datetime import datetime
from typing import List, Optional

import strawberry

from lipaidox.auth.permissions import UserRoles

from .. import live_billing, reports
from ..models import CreatorCreditLedger, FinancialAuditLog
from ..schema.credits_schema import CreatorCreditLedgerType
from ..schema.live_billing_schema import (
    AdminCreditsReportType,
    AdminLiveDashboardType,
    AdminLiveSessionType,
    AuditLogType,
    LiveBillingStatusType,
    LiveCreditTransactionPage,
    LiveCreditWalletType,
)

MAX_PAGE_SIZE = 100


def _profile(info):
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
class LiveBillingQuery:
    @strawberry.field
    def my_live_credit_wallet(self, info: strawberry.types.Info) -> LiveCreditWalletType:
        """Balance, what is held for a live in progress, time it buys, and whether a stream can start."""
        return LiveCreditWalletType.from_snapshot(live_billing.wallet_snapshot(_profile(info)))

    @strawberry.field
    def live_billing_status(
        self, info: strawberry.types.Info, streamId: strawberry.ID
    ) -> Optional[LiveBillingStatusType]:
        """Where a stream's bill stands. Read-only — billing happens on heartbeats and on end."""
        snap = live_billing.billing_status(streamId, _profile(info))
        return LiveBillingStatusType.from_snapshot(snap) if snap else None

    # ── Creator: transactions ────────────────────────────────────────────────

    @strawberry.field
    def my_live_credit_transactions(
        self,
        info: strawberry.types.Info,
        page: int = 1,
        limit: int = 20,
        type: Optional[str] = None,
        fromDate: Optional[datetime] = None,
        toDate: Optional[datetime] = None,
    ) -> LiveCreditTransactionPage:
        """The wallet ledger, newest first, paged and filterable by type and date."""
        profile = _profile(info)
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        page = max(1, int(page))
        qs = CreatorCreditLedger.objects.filter(creator=profile)
        if type:
            qs = qs.filter(transaction_type=type)
        if fromDate:
            qs = qs.filter(created_at__gte=fromDate)
        if toDate:
            qs = qs.filter(created_at__lte=toDate)
        total = qs.count()
        pages = max(1, -(-total // limit))
        rows = qs.order_by("-created_at")[(page - 1) * limit: page * limit]
        return LiveCreditTransactionPage(
            items=[CreatorCreditLedgerType.from_model(r) for r in rows],
            total=total, page=page, pages=pages, limit=limit,
        )

    @strawberry.field
    def my_live_credit_transaction(
        self, info: strawberry.types.Info, id: strawberry.ID
    ) -> Optional[CreatorCreditLedgerType]:
        """One ledger entry. Only the owner can read it — anyone else gets null."""
        row = CreatorCreditLedger.objects.filter(pk=id, creator=_profile(info)).first()
        return CreatorCreditLedgerType.from_model(row) if row else None

    # ── Admin: live monitoring, reports, audit ───────────────────────────────

    @strawberry.field
    def admin_live_credit_sessions(
        self, info: strawberry.types.Info, status: Optional[str] = "active", limit: int = 50, offset: int = 0
    ) -> List[AdminLiveSessionType]:
        """Live sessions holding or having used credits. `status`: active | settled | null for all."""
        _admin(info)
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        qs = reports.sessions_queryset(status)[max(0, offset): max(0, offset) + limit]
        return [AdminLiveSessionType.from_model(r) for r in qs]

    @strawberry.field
    def admin_live_credit_session(
        self, info: strawberry.types.Info, streamId: strawberry.ID
    ) -> Optional[AdminLiveSessionType]:
        _admin(info)
        r = reports.sessions_queryset().filter(live_stream_id=streamId).first()
        return AdminLiveSessionType.from_model(r) if r else None

    @strawberry.field
    def admin_live_dashboard(self, info: strawberry.types.Info) -> AdminLiveDashboardType:
        """Active lives, credits burning per minute, and today's consumption."""
        _admin(info)
        d = reports.live_dashboard()
        return AdminLiveDashboardType(
            activeSessions=d.active_sessions, creditsPerMinute=float(d.credits_per_minute),
            creditsHeld=float(d.credits_held), creditsConsumedToday=float(d.credits_consumed_today),
            sessionsToday=d.sessions_today,
        )

    @strawberry.field
    def admin_credits_report(
        self,
        info: strawberry.types.Info,
        fromDate: Optional[datetime] = None,
        toDate: Optional[datetime] = None,
        creatorUserId: Optional[strawberry.ID] = None,
    ) -> AdminCreditsReportType:
        """Credits purchased / consumed / refunded / issued, revenue, and live-session stats for a period (default: last 30 days)."""
        _admin(info)
        return AdminCreditsReportType.from_report(reports.credits_report(fromDate, toDate, creatorUserId))

    @strawberry.field
    def admin_financial_audit_logs(
        self,
        info: strawberry.types.Info,
        action: Optional[str] = None,
        entityType: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditLogType]:
        """The append-only audit trail of administrator actions on money-related records."""
        _admin(info)
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
        qs = FinancialAuditLog.objects.select_related("actor")
        if action:
            qs = qs.filter(action=action)
        if entityType:
            qs = qs.filter(entity_type=entityType)
        return [AuditLogType.from_model(a) for a in qs[max(0, offset): max(0, offset) + limit]]
