import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from ..models import Tip, TipStatus, TipType
from ..schema.tips_schema import TipType, TipStatisticsType, SendTipInput, RefundTipInput
from lipaidox.auth.permissions import UserRoles


def require_auth(info):
    """Check if user is authenticated"""
    user = info.context.request.user
    if not user.is_authenticated:
        raise Exception("Authentication required")
    return user


def require_creator(user):
    """Check if user is a creator"""
    if user.role != UserRoles.CREATOR:
        raise Exception("Creator access required")
    return True


@strawberry.type
class TipsQuery:
    # Fan Queries
    @strawberry.field
    def my_sent_tips(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[TipType]:
        """Get tips sent by current user"""
        user = require_auth(info)
        
        queryset = Tip.objects.filter(fan=user)
        if status:
            queryset = queryset.filter(status=status)
        
        return [TipType.from_model(t) for t in queryset.order_by('-sent_at')[:limit]]
    
    # Creator Queries
    @strawberry.field
    def my_received_tips(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[TipType]:
        """Get tips received by creator"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
            queryset = Tip.objects.filter(creator=profile)
            if status:
                queryset = queryset.filter(status=status)
            return [TipType.from_model(t) for t in queryset.order_by('-sent_at')[:limit]]
        except CreatorProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def my_tip_statistics(self, info: strawberry.types.Info) -> TipStatisticsType:
        """Get tip statistics for creator"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        from django.db.models import Sum, Count
        
        try:
            profile = CreatorProfile.objects.get(user=user)
            tips = Tip.objects.filter(creator=profile)
            
            total = tips.count()
            completed = tips.filter(status=TipStatus.COMPLETED).count()
            pending = tips.filter(status=TipStatus.PENDING).count()
            refunded = tips.filter(status=TipStatus.REFUNDED).count()
            
            total_amount = tips.filter(status=TipStatus.COMPLETED).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')
            
            platform_fees = tips.filter(status=TipStatus.COMPLETED).aggregate(
                total=Sum('platform_fee')
            )['total'] or Decimal('0')
            
            net_amount = tips.filter(status=TipStatus.COMPLETED).aggregate(
                total=Sum('net_amount')
            )['total'] or Decimal('0')
            
            return TipStatisticsType(
                totalTips=total,
                totalAmount=total_amount,
                totalPlatformFees=platform_fees,
                totalNetAmount=net_amount,
                completedTips=completed,
                pendingTips=pending,
                refundedTips=refunded
            )
        except CreatorProfile.DoesNotExist:
            return TipStatisticsType(
                totalTips=0,
                totalAmount=Decimal('0'),
                totalPlatformFees=Decimal('0'),
                totalNetAmount=Decimal('0'),
                completedTips=0,
                pendingTips=0,
                refundedTips=0
            )
    
    # Admin Queries
    @strawberry.field
    def all_tips(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        creatorId: Optional[strawberry.ID] = None,
        limit: int = 100
    ) -> List[TipType]:
        """Get all tips (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = Tip.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)
        
        return [TipType.from_model(t) for t in queryset.order_by('-sent_at')[:limit]]
