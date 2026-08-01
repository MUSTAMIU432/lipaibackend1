import strawberry
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from ..models import PPVPurchase, PPVAccessLog, PPVAccessType, PPVPurchaseStatus


@strawberry.type
class PPVPurchaseType:
    id: strawberry.ID
    fanId: strawberry.ID
    creatorId: strawberry.ID
    contentId: strawberry.ID
    accessType: str
    amountPaid: Decimal
    currency: str
    platformFeePercent: Decimal
    platformFee: Decimal
    netAmount: Decimal
    status: str
    accessGrantedAt: Optional[datetime]
    expiresAt: Optional[datetime]
    isExpired: bool
    allowDownload: bool
    downloadCount: int
    paymentMethodId: Optional[strawberry.ID]
    gatewayReference: Optional[str]
    refundedAt: Optional[datetime]
    refundReason: Optional[str]
    refundAmount: Optional[Decimal]
    purchasedAt: datetime
    hasAccess: bool

    @classmethod
    def from_model(cls, instance: PPVPurchase):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            contentId=strawberry.ID(str(instance.content_id)),
            accessType=instance.access_type,
            amountPaid=instance.amount_paid,
            currency=instance.currency,
            platformFeePercent=instance.platform_fee_percent,
            platformFee=instance.platform_fee,
            netAmount=instance.net_amount,
            status=instance.status,
            accessGrantedAt=instance.access_granted_at,
            expiresAt=instance.expires_at,
            isExpired=instance.is_expired,
            allowDownload=instance.allow_download,
            downloadCount=instance.download_count,
            paymentMethodId=strawberry.ID(str(instance.payment_method_id)) if instance.payment_method else None,
            gatewayReference=instance.gateway_reference,
            refundedAt=instance.refunded_at,
            refundReason=instance.refund_reason,
            refundAmount=instance.refund_amount,
            purchasedAt=instance.purchased_at,
            hasAccess=instance.has_access,
        )


@strawberry.type
class PPVAccessLogType:
    id: strawberry.ID
    purchaseId: strawberry.ID
    fanId: strawberry.ID
    contentId: strawberry.ID
    ipAddress: Optional[str]
    userAgent: Optional[str]
    deviceType: Optional[str]
    accessedAt: datetime

    @classmethod
    def from_model(cls, instance: PPVAccessLog):
        return cls(
            id=strawberry.ID(str(instance.id)),
            purchaseId=strawberry.ID(str(instance.purchase_id)),
            fanId=strawberry.ID(str(instance.fan_id)),
            contentId=strawberry.ID(str(instance.content_id)),
            ipAddress=str(instance.ip_address) if instance.ip_address else None,
            userAgent=instance.user_agent,
            deviceType=instance.device_type,
            accessedAt=instance.accessed_at,
        )


# Statistics
@strawberry.type
class PPVStatisticsType:
    totalPurchases: int
    totalRevenue: Decimal
    totalPlatformFees: Decimal
    totalNetAmount: Decimal
    completedPurchases: int
    pendingPurchases: int
    refundedPurchases: int


# Input Types
@strawberry.input
class PurchasePPVInput:
    contentId: strawberry.ID
    accessType: str
    paymentMethodId: Optional[strawberry.ID] = None


@strawberry.input
class GrantAccessInput:
    purchaseId: strawberry.ID
    expiresAt: Optional[datetime] = None


@strawberry.input
class RefundPPVInput:
    purchaseId: strawberry.ID
    amount: Optional[Decimal] = None
    reason: Optional[str] = None


@strawberry.input
class LogAccessInput:
    purchaseId: strawberry.ID
    contentId: strawberry.ID
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None
    deviceType: Optional[str] = None
