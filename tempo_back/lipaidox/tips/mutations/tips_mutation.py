import strawberry
from typing import Optional
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from ..models import Tip, TipStatus, TipType
from ..schema.tips_schema import TipType, SendTipInput, RefundTipInput
from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


@strawberry.type
class TipsMutation:
    # Fan Mutations
    @strawberry.mutation
    def send_tip(self, info: strawberry.types.Info, input: SendTipInput) -> TipType:
        """Send a money tip to a creator"""
        user = require_auth(info)
        
        # Get creator
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            creator = CreatorProfile.objects.get(id=input.creatorId)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator not found")
        
        # Validate amount
        if input.amount <= 0:
            raise Exception("Tip amount must be greater than 0")
        
        with transaction.atomic():
            # Create tip
            tip = Tip(
                fan=user,
                creator=creator,
                tenant=user.tenant,
                tip_type=TipType.MONEY,
                amount=input.amount,
                currency=input.currency or 'USD',
                message=input.message,
                is_anonymous=input.isAnonymous,
                platform_fee_percent=Decimal('15.00'),
                status=TipStatus.PENDING
            )
            tip.calculate_fees()
            
            # Set optional references
            if input.contentId:
                from lipaidox.content.models.content import Content
                try:
                    tip.content = Content.objects.get(id=input.contentId)
                except Content.DoesNotExist:
                    pass
            
            if input.liveStreamId:
                tip.live_stream_id = input.liveStreamId
            
            if input.paymentMethodId:
                from lipaidox.payment.models import PaymentMethod
                try:
                    tip.payment_method = PaymentMethod.objects.get(id=input.paymentMethodId)
                except PaymentMethod.DoesNotExist:
                    pass
            
            tip.save()
            
            # Mark as completed (in real implementation, this would be after payment confirmation)
            tip.mark_completed()
        
        return TipType.from_model(tip)
    
    # Admin Mutations
    @strawberry.mutation
    def refund_tip(self, info: strawberry.types.Info, input: RefundTipInput) -> TipType:
        """Refund a tip (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            tip = Tip.objects.get(id=input.tipId)
        except Tip.DoesNotExist:
            raise Exception("Tip not found")
        
        if tip.status != TipStatus.COMPLETED:
            raise Exception("Only completed tips can be refunded")
        
        with transaction.atomic():
            tip.process_refund(reason=input.reason)
        
        return TipType.from_model(tip)
    
    @strawberry.mutation
    def process_tip(self, info: strawberry.types.Info, tipId: strawberry.ID) -> TipType:
        """Manually process a pending tip (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            tip = Tip.objects.get(id=tipId)
        except Tip.DoesNotExist:
            raise Exception("Tip not found")
        
        if tip.status != TipStatus.PENDING:
            raise Exception("Only pending tips can be processed")
        
        tip.mark_completed()
        return TipType.from_model(tip)
