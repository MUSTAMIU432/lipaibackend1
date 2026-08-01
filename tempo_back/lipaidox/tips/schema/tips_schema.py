import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..models import Tip, TipStatus, TipType


@strawberry.type
class TipType:
    id: strawberry.ID
    fanId: strawberry.ID
    creatorId: strawberry.ID
    tipType: str
    amount: Decimal
    currency: str
    message: Optional[str]
    isAnonymous: bool
    platformFeePercent: Decimal
    platformFee: Decimal
    netAmount: Decimal
    status: str
    paymentMethodId: Optional[strawberry.ID]
    gatewayReference: Optional[str]
    contentId: Optional[strawberry.ID]
    liveStreamId: Optional[str]
    refundedAt: Optional[datetime]
    refundReason: Optional[str]
    sentAt: datetime
    processedAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: Tip):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            tipType=instance.tip_type,
            amount=instance.amount,
            currency=instance.currency,
            message=instance.message,
            isAnonymous=instance.is_anonymous,
            platformFeePercent=instance.platform_fee_percent,
            platformFee=instance.platform_fee,
            netAmount=instance.net_amount,
            status=instance.status,
            paymentMethodId=strawberry.ID(str(instance.payment_method_id)) if instance.payment_method else None,
            gatewayReference=instance.gateway_reference,
            contentId=strawberry.ID(str(instance.content_id)) if instance.content else None,
            liveStreamId=instance.live_stream_id,
            refundedAt=instance.refunded_at,
            refundReason=instance.refund_reason,
            sentAt=instance.sent_at,
            processedAt=instance.processed_at,
        )


# Statistics
@strawberry.type
class TipStatisticsType:
    totalTips: int
    totalAmount: Decimal
    totalPlatformFees: Decimal
    totalNetAmount: Decimal
    completedTips: int
    pendingTips: int
    refundedTips: int


# Input Types
@strawberry.input
class SendTipInput:
    creatorId: strawberry.ID
    amount: Decimal
    currency: Optional[str] = 'USD'
    message: Optional[str] = None
    isAnonymous: bool = False
    contentId: Optional[strawberry.ID] = None
    liveStreamId: Optional[str] = None
    paymentMethodId: Optional[strawberry.ID] = None


@strawberry.input
class RefundTipInput:
    tipId: strawberry.ID
    reason: Optional[str] = None
