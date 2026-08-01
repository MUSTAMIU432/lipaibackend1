import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import json
from ..models import (
    CreatorWallet, WalletTransaction, PayoutTransaction, Transaction, WalletClearingJob,
    WalletTransactionType, WalletTransactionStatus, PayoutStatus, PayoutFailureReason,
    TransactionType, TransactionStatus, ClearingJobStatus
)


@strawberry.type
class CreatorWalletType:
    id: strawberry.ID
    creatorId: strawberry.ID
    currency: str
    pendingBalance: Decimal
    availableBalance: Decimal
    onHoldBalance: Decimal
    totalBalance: Decimal
    lifetimeEarnings: Decimal
    lifetimePayouts: Decimal
    lifetimeRefunds: Decimal
    lifetimePlatformFees: Decimal
    earningsFromPpv: Decimal
    earningsFromSubscriptions: Decimal
    earningsFromTips: Decimal
    earningsFromCredits: Decimal
    earningsFromLiveStreams: Decimal
    lastPayoutAt: Optional[datetime]
    lastPayoutAmount: Optional[Decimal]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: CreatorWallet):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            currency=instance.currency,
            pendingBalance=instance.pending_balance,
            availableBalance=instance.available_balance,
            onHoldBalance=instance.on_hold_balance,
            totalBalance=instance.total_balance,
            lifetimeEarnings=instance.lifetime_earnings,
            lifetimePayouts=instance.lifetime_payouts,
            lifetimeRefunds=instance.lifetime_refunds,
            lifetimePlatformFees=instance.lifetime_platform_fees,
            earningsFromPpv=instance.earnings_from_ppv,
            earningsFromSubscriptions=instance.earnings_from_subscriptions,
            earningsFromTips=instance.earnings_from_tips,
            earningsFromCredits=instance.earnings_from_credits,
            earningsFromLiveStreams=instance.earnings_from_live_streams,
            lastPayoutAt=instance.last_payout_at,
            lastPayoutAmount=instance.last_payout_amount,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class WalletTransactionType:
    id: strawberry.ID
    walletId: strawberry.ID
    creatorId: strawberry.ID
    transactionType: str
    status: str
    amount: Decimal
    currency: str
    balanceBefore: Decimal
    balanceAfter: Decimal
    balanceType: str
    ppvPurchaseId: Optional[strawberry.ID]
    subscriptionPaymentId: Optional[strawberry.ID]
    tipId: Optional[strawberry.ID]
    liveStreamId: Optional[strawberry.ID]
    creditTransactionId: Optional[strawberry.ID]
    payoutId: Optional[strawberry.ID]
    clearsAt: Optional[datetime]
    clearedAt: Optional[datetime]
    description: Optional[str]
    metadata: str
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: WalletTransaction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            walletId=strawberry.ID(str(instance.wallet_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            transactionType=instance.transaction_type,
            status=instance.status,
            amount=instance.amount,
            currency=instance.currency,
            balanceBefore=instance.balance_before,
            balanceAfter=instance.balance_after,
            balanceType=instance.balance_type,
            ppvPurchaseId=strawberry.ID(str(instance.ppv_purchase_id)) if instance.ppv_purchase_id else None,
            subscriptionPaymentId=strawberry.ID(str(instance.subscription_payment_id)) if instance.subscription_payment_id else None,
            tipId=strawberry.ID(str(instance.tip_id)) if instance.tip_id else None,
            liveStreamId=strawberry.ID(str(instance.live_stream_id)) if instance.live_stream_id else None,
            creditTransactionId=strawberry.ID(str(instance.credit_transaction_id)) if instance.credit_transaction_id else None,
            payoutId=strawberry.ID(str(instance.payout_id)) if instance.payout_id else None,
            clearsAt=instance.clears_at,
            clearedAt=instance.cleared_at,
            description=instance.description,
            metadata=json.dumps(instance.metadata) if instance.metadata else "{}",
            createdAt=instance.created_at,
        )


@strawberry.type
class PayoutTransactionType:
    id: strawberry.ID
    creatorId: strawberry.ID
    walletId: strawberry.ID
    paymentMethodId: strawberry.ID
    amount: Decimal
    currency: str
    taxWithholdingPercent: Decimal
    taxWithheldAmount: Decimal
    netPayoutAmount: Decimal
    status: str
    gatewayReference: Optional[str]
    gatewayResponse: str
    gatewayFee: Optional[Decimal]
    failureReason: Optional[str]
    failureNote: Optional[str]
    retryCount: int
    lastRetryAt: Optional[datetime]
    reversedAt: Optional[datetime]
    reversalReason: Optional[str]
    reversedBy: Optional[strawberry.ID]
    requiresAdminApproval: bool
    approvedBy: Optional[strawberry.ID]
    approvedAt: Optional[datetime]
    initiatedAt: datetime
    processingAt: Optional[datetime]
    completedAt: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: PayoutTransaction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            walletId=strawberry.ID(str(instance.wallet_id)),
            paymentMethodId=strawberry.ID(str(instance.payment_method_id)),
            amount=instance.amount,
            currency=instance.currency,
            taxWithholdingPercent=instance.tax_withholding_percent,
            taxWithheldAmount=instance.tax_withheld_amount,
            netPayoutAmount=instance.net_payout_amount,
            status=instance.status,
            gatewayReference=instance.gateway_reference,
            gatewayResponse=json.dumps(instance.gateway_response) if instance.gateway_response else "{}",
            gatewayFee=instance.gateway_fee,
            failureReason=instance.failure_reason,
            failureNote=instance.failure_note,
            retryCount=instance.retry_count,
            lastRetryAt=instance.last_retry_at,
            reversedAt=instance.reversed_at,
            reversalReason=instance.reversal_reason,
            reversedBy=strawberry.ID(str(instance.reversed_by_id)) if instance.reversed_by else None,
            requiresAdminApproval=instance.requires_admin_approval,
            approvedBy=strawberry.ID(str(instance.approved_by_id)) if instance.approved_by else None,
            approvedAt=instance.approved_at,
            initiatedAt=instance.initiated_at,
            processingAt=instance.processing_at,
            completedAt=instance.completed_at,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class TransactionType:
    id: strawberry.ID
    fanId: Optional[strawberry.ID]
    creatorId: Optional[strawberry.ID]
    transactionType: str
    status: str
    grossAmount: Decimal
    platformFeePercent: Decimal
    platformFee: Decimal
    netAmount: Decimal
    currency: str
    ppvPurchaseId: Optional[strawberry.ID]
    subscriptionPaymentId: Optional[strawberry.ID]
    tipId: Optional[strawberry.ID]
    creditPurchaseId: Optional[strawberry.ID]
    payoutId: Optional[strawberry.ID]
    paymentMethodId: Optional[strawberry.ID]
    gatewayReference: Optional[str]
    gatewayResponse: str
    refundedAt: Optional[datetime]
    refundAmount: Optional[Decimal]
    refundReason: Optional[str]
    refundedBy: Optional[strawberry.ID]
    disputedAt: Optional[datetime]
    disputeReason: Optional[str]
    disputeResolvedAt: Optional[datetime]
    description: Optional[str]
    metadata: str
    ipAddress: Optional[str]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, instance: Transaction):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fanId=strawberry.ID(str(instance.fan_id)) if instance.fan else None,
            creatorId=strawberry.ID(str(instance.creator_id)) if instance.creator else None,
            transactionType=instance.transaction_type,
            status=instance.status,
            grossAmount=instance.gross_amount,
            platformFeePercent=instance.platform_fee_percent,
            platformFee=instance.platform_fee,
            netAmount=instance.net_amount,
            currency=instance.currency,
            ppvPurchaseId=strawberry.ID(str(instance.ppv_purchase_id)) if instance.ppv_purchase_id else None,
            subscriptionPaymentId=strawberry.ID(str(instance.subscription_payment_id)) if instance.subscription_payment_id else None,
            tipId=strawberry.ID(str(instance.tip_id)) if instance.tip_id else None,
            creditPurchaseId=strawberry.ID(str(instance.credit_purchase_id)) if instance.credit_purchase_id else None,
            payoutId=strawberry.ID(str(instance.payout_id)) if instance.payout_id else None,
            paymentMethodId=strawberry.ID(str(instance.payment_method_id)) if instance.payment_method else None,
            gatewayReference=instance.gateway_reference,
            gatewayResponse=json.dumps(instance.gateway_response) if instance.gateway_response else "{}",
            refundedAt=instance.refunded_at,
            refundAmount=instance.refund_amount,
            refundReason=instance.refund_reason,
            refundedBy=strawberry.ID(str(instance.refunded_by_id)) if instance.refunded_by else None,
            disputedAt=instance.disputed_at,
            disputeReason=instance.dispute_reason,
            disputeResolvedAt=instance.dispute_resolved_at,
            description=instance.description,
            metadata=json.dumps(instance.metadata) if instance.metadata else "{}",
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
        )


@strawberry.type
class WalletClearingJobType:
    id: strawberry.ID
    walletId: strawberry.ID
    walletTransactionId: strawberry.ID
    creatorId: strawberry.ID
    amount: Decimal
    currency: str
    status: str
    scheduledClearAt: datetime
    processedAt: Optional[datetime]
    failureReason: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: WalletClearingJob):
        return cls(
            id=strawberry.ID(str(instance.id)),
            walletId=strawberry.ID(str(instance.wallet_id)),
            walletTransactionId=strawberry.ID(str(instance.wallet_transaction_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            amount=instance.amount,
            currency=instance.currency,
            status=instance.status,
            scheduledClearAt=instance.scheduled_clear_at,
            processedAt=instance.processed_at,
            failureReason=instance.failure_reason,
            createdAt=instance.created_at,
        )


# Statistics Types
@strawberry.type
class WalletStatisticsType:
    totalEarnings: Decimal
    pendingBalance: Decimal
    availableBalance: Decimal
    onHoldBalance: Decimal
    lifetimePayouts: Decimal
    totalTransactions: int
    pendingTransactions: int
    clearedTransactions: int


@strawberry.type
class PayoutStatisticsType:
    totalPayouts: int
    totalPayoutAmount: Decimal
    pendingPayouts: int
    processingPayouts: int
    completedPayouts: int
    failedPayouts: int
    lastPayoutAmount: Optional[Decimal]
    lastPayoutAt: Optional[datetime]


# Input Types
@strawberry.input
class RequestPayoutInput:
    amount: Decimal
    paymentMethodId: strawberry.ID
    taxWithholdingPercent: Decimal = 0


@strawberry.input
class UpdateWalletInput:
    walletId: strawberry.ID
    taxWithholdingPercent: Optional[Decimal] = None


@strawberry.input
class WalletTransactionFilterInput:
    transactionType: Optional[str] = None
    status: Optional[str] = None
    balanceType: Optional[str] = None
    dateFrom: Optional[datetime] = None
    dateTo: Optional[datetime] = None


@strawberry.input
class PayoutFilterInput:
    status: Optional[str] = None
    dateFrom: Optional[datetime] = None
    dateTo: Optional[datetime] = None
