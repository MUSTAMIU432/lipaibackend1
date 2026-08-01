import enum
import strawberry
from typing import Optional
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from ..models import PPVPurchase, PPVAccessLog, PPVAccessType, PPVPurchaseStatus
from ..schema.ppv_schema import (
    PPVPurchaseType, PPVAccessLogType,
    PurchasePPVInput, GrantAccessInput, RefundPPVInput, LogAccessInput
)
from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


@strawberry.enum
class PaymentSource(enum.Enum):
    WALLET = "wallet"
    GATEWAY = "gateway"


@strawberry.enum
class PurchaseAccessType(enum.Enum):
    ONE_TIME = "one_time"
    TIMED = "timed"


@strawberry.type
class PurchaseContentResult:
    success: bool
    code: str          # "OK" | "INSUFFICIENT_FUNDS" | "ALREADY_PURCHASED" | "PAYMENT_FAILED" | "INVALID"
    message: str
    purchase: Optional[PPVPurchaseType]
    wallet_balance: float


def _timed_expiry(content):
    """Compute expiry for timed access from the content's duration config."""
    value = content.timed_duration_value or 24
    unit = (content.timed_duration_unit or "hours").lower()
    delta = timedelta(days=value) if unit == "days" else timedelta(hours=value)
    return timezone.now() + delta


@strawberry.type
class PPVMutation:
    # Fan Mutations
    @strawberry.mutation
    def purchase_ppv(self, info: strawberry.types.Info, input: PurchasePPVInput) -> PPVPurchaseType:
        """Purchase PPV content access"""
        user = require_auth(info)
        
        # Get content
        from lipaidox.content.models.content import Content
        try:
            content = Content.objects.get(id=input.contentId)
        except Content.DoesNotExist:
            raise Exception("Content not found")
        
        # Check if content is PPV (paid one-time/timed access)
        from lipaidox.content.models.content import ContentAccessType
        if content.access_type not in (ContentAccessType.ONE_TIME, ContentAccessType.TIMED):
            raise Exception("Content is not available for PPV purchase")
        
        # Check if user already has active purchase
        existing = PPVPurchase.objects.filter(
            fan=user,
            content=content
        ).first()
        
        if existing and existing.has_access:
            raise Exception("You already have active access to this content")
        
        # Validate access type
        if input.accessType not in [PPVAccessType.ONE_TIME, PPVAccessType.TIMED]:
            raise Exception(f"Invalid access type. Must be one of: {PPVAccessType.ONE_TIME}, {PPVAccessType.TIMED}")
        
        # Get pricing based on access type
        if input.accessType == PPVAccessType.TIMED:
            amount = content.timed_price or content.one_time_price
        else:
            amount = content.one_time_price
        
        if not amount or amount <= 0:
            raise Exception("Content price not set")
        
        # Get creator
        creator = content.creator if hasattr(content, 'creator') else None
        if not creator:
            raise Exception("Content creator not found")
        
        with transaction.atomic():
            # Create purchase
            purchase = PPVPurchase(
                fan=user,
                creator=creator,
                content=content,
                tenant=user.tenant,
                access_type=input.accessType,
                amount_paid=amount,
                currency='USD',
                platform_fee_percent=Decimal('15.00'),
                allow_download=getattr(content, 'allow_download', False),
                status=PPVPurchaseStatus.PENDING
            )
            purchase.calculate_fees()
            
            if input.paymentMethodId:
                from lipaidox.payment.models import PaymentMethod
                try:
                    purchase.payment_method = PaymentMethod.objects.get(id=input.paymentMethodId)
                except PaymentMethod.DoesNotExist:
                    pass
            
            purchase.save()
            
            # Grant access immediately (in real implementation, this would be after payment confirmation)
            purchase.grant_access()
            
            # Set expiry for timed access
            if input.accessType == PPVAccessType.TIMED:
                # Default 24 hours for timed access
                purchase.expires_at = timezone.now() + timedelta(hours=24)
                purchase.save()
        
        return PPVPurchaseType.from_model(purchase)
    
    @strawberry.mutation
    def purchase_content(
        self,
        info: strawberry.types.Info,
        content_id: strawberry.ID,
        access_type: PurchaseAccessType,
        payment_source: PaymentSource = PaymentSource.WALLET,
        method: Optional[str] = None,
        simulate: Optional[str] = None,
    ) -> PurchaseContentResult:
        """
        Unlock paid content. Debits the fan wallet (WALLET) or charges the gateway
        then funds the wallet (GATEWAY), settles the creator's cut net of platform
        fee, and records/grants a PPVPurchase. Idempotent per (fan, content).
        """
        user = require_auth(info)

        from lipaidox.content.models.content import Content, ContentAccessType
        from lipaidox.wallet.services import (
            settle, credit_fan_wallet, get_or_create_fan_wallet, InsufficientFunds,
        )
        from lipaidox.wallet.models import TransactionType

        def _balance():
            return float(get_or_create_fan_wallet(user).balance)

        try:
            content = Content.objects.select_related("creator").get(id=content_id)
        except Content.DoesNotExist:
            return PurchaseContentResult(
                success=False, code="INVALID", message="Content not found",
                purchase=None, wallet_balance=_balance(),
            )

        if content.access_type not in (ContentAccessType.ONE_TIME, ContentAccessType.TIMED):
            return PurchaseContentResult(
                success=False, code="INVALID", message="Content is not purchasable",
                purchase=None, wallet_balance=_balance(),
            )

        # Price for the requested access mode.
        if access_type == PurchaseAccessType.TIMED:
            amount = content.timed_price or content.one_time_price
            ppv_access = PPVAccessType.TIMED
        else:
            amount = content.one_time_price
            ppv_access = PPVAccessType.ONE_TIME
        if not amount or amount <= 0:
            return PurchaseContentResult(
                success=False, code="INVALID", message="Content price not set",
                purchase=None, wallet_balance=_balance(),
            )
        amount = Decimal(str(amount))

        # Idempotent: an active purchase already grants access.
        existing = PPVPurchase.objects.filter(fan=user, content=content).first()
        if existing and existing.has_access:
            return PurchaseContentResult(
                success=True, code="ALREADY_PURCHASED",
                message="You already have access to this content",
                purchase=PPVPurchaseType.from_model(existing), wallet_balance=_balance(),
            )

        # GATEWAY: charge the provider, then fund the wallet (top-up-then-spend).
        if payment_source == PaymentSource.GATEWAY:
            from lipaidox.payment.gateways.registry import get_gateway
            from lipaidox.payment.models import ChargePurpose, ChargeStatus
            metadata = {}
            if method:
                metadata["method"] = method
            if simulate:
                metadata["simulate"] = simulate
            charge = get_gateway().create_charge(
                user=user, amount=amount, purpose=ChargePurpose.PPV, metadata=metadata,
            )
            if charge.status != ChargeStatus.SUCCEEDED:
                return PurchaseContentResult(
                    success=False, code="PAYMENT_FAILED", message="Payment failed",
                    purchase=None, wallet_balance=_balance(),
                )
            credit_fan_wallet(user, amount)

        expires_at = _timed_expiry(content) if ppv_access == PPVAccessType.TIMED else None

        try:
            with transaction.atomic():
                purchase = existing or PPVPurchase(fan=user, content=content, creator=content.creator)
                purchase.creator = content.creator
                purchase.tenant = user.tenant
                purchase.access_type = ppv_access
                purchase.amount_paid = amount
                purchase.currency = "USD"
                purchase.platform_fee_percent = content.platform_fee_percent or Decimal("15.00")
                purchase.allow_download = content.allow_download
                purchase.expires_at = expires_at
                purchase.is_expired = False
                purchase.calculate_fees()
                purchase.status = PPVPurchaseStatus.PENDING
                purchase.save()

                # Move money: fan wallet -> creator wallet (net of platform fee).
                fan_wallet, _txn = settle(
                    fan_user=user,
                    creator_profile=content.creator,
                    gross=amount,
                    fee_percent=purchase.platform_fee_percent,
                    tx_type=TransactionType.PPV_PURCHASE,
                    description=f"PPV unlock: {content.title}",
                    ppv_purchase_id=purchase.id,
                )

                purchase.grant_access()

                content.purchase_count = (content.purchase_count or 0) + 1
                content.total_revenue = (content.total_revenue or 0) + amount
                content.save(update_fields=["purchase_count", "total_revenue", "updated_at"])
        except InsufficientFunds:
            return PurchaseContentResult(
                success=False, code="INSUFFICIENT_FUNDS",
                message="Insufficient wallet balance. Top up to continue.",
                purchase=None, wallet_balance=_balance(),
            )

        return PurchaseContentResult(
            success=True, code="OK", message="Content unlocked",
            purchase=PPVPurchaseType.from_model(purchase),
            wallet_balance=float(fan_wallet.balance),
        )

    @strawberry.mutation
    def log_ppv_access(self, info: strawberry.types.Info, input: LogAccessInput) -> PPVAccessLogType:
        """Log access to PPV content (called when fan views content)"""
        user = require_auth(info)
        
        try:
            purchase = PPVPurchase.objects.get(id=input.purchaseId, fan=user)
        except PPVPurchase.DoesNotExist:
            raise Exception("Purchase not found")
        
        if not purchase.has_access:
            raise Exception("Access expired or not granted")
        
        # Create access log
        log = PPVAccessLog.objects.create(
            purchase=purchase,
            fan=user,
            content_id=input.contentId,
            tenant=user.tenant,
            ip_address=input.ipAddress,
            user_agent=input.userAgent,
            device_type=input.deviceType
        )
        
        return PPVAccessLogType.from_model(log)
    
    @strawberry.mutation
    def increment_ppv_download(self, info: strawberry.types.Info, purchaseId: strawberry.ID) -> PPVPurchaseType:
        """Increment download counter for PPV purchase"""
        user = require_auth(info)
        
        try:
            purchase = PPVPurchase.objects.get(id=purchaseId, fan=user)
        except PPVPurchase.DoesNotExist:
            raise Exception("Purchase not found")
        
        if not purchase.has_access:
            raise Exception("Access expired or not granted")
        
        if not purchase.allow_download:
            raise Exception("Downloads not allowed for this content")
        
        purchase.increment_download()
        return PPVPurchaseType.from_model(purchase)
    
    # Admin Mutations
    @strawberry.mutation
    def grant_ppv_access(self, info: strawberry.types.Info, input: GrantAccessInput) -> PPVPurchaseType:
        """Manually grant PPV access (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            purchase = PPVPurchase.objects.get(id=input.purchaseId)
        except PPVPurchase.DoesNotExist:
            raise Exception("Purchase not found")
        
        with transaction.atomic():
            purchase.grant_access()
            if input.expiresAt:
                purchase.expires_at = input.expiresAt
                purchase.save()
        
        return PPVPurchaseType.from_model(purchase)
    
    @strawberry.mutation
    def refund_ppv_purchase(self, info: strawberry.types.Info, input: RefundPPVInput) -> PPVPurchaseType:
        """Refund a PPV purchase (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            purchase = PPVPurchase.objects.get(id=input.purchaseId)
        except PPVPurchase.DoesNotExist:
            raise Exception("Purchase not found")
        
        with transaction.atomic():
            purchase.process_refund(
                amount=input.amount,
                reason=input.reason
            )
        
        return PPVPurchaseType.from_model(purchase)
    
    @strawberry.mutation
    def expire_ppv_access(self, info: strawberry.types.Info, purchaseId: strawberry.ID) -> PPVPurchaseType:
        """Manually expire PPV access (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            purchase = PPVPurchase.objects.get(id=purchaseId)
        except PPVPurchase.DoesNotExist:
            raise Exception("Purchase not found")
        
        purchase.mark_expired()
        return PPVPurchaseType.from_model(purchase)
