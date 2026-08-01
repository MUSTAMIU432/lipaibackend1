import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from ..models import PPVPurchase, PPVAccessLog, PPVAccessType, PPVPurchaseStatus
from ..schema.ppv_schema import PPVPurchaseType, PPVAccessLogType, PPVStatisticsType
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
class PPVQuery:
    # Fan Queries
    @strawberry.field
    def my_ppv_purchases(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[PPVPurchaseType]:
        """Get current fan's PPV purchase history"""
        user = require_auth(info)
        
        queryset = PPVPurchase.objects.filter(fan=user)
        if status:
            queryset = queryset.filter(status=status)
        
        return [PPVPurchaseType.from_model(p) for p in queryset.order_by('-purchased_at')[:limit]]
    
    @strawberry.field
    def my_ppv_purchase_by_content(
        self,
        info: strawberry.types.Info,
        contentId: strawberry.ID
    ) -> Optional[PPVPurchaseType]:
        """Get PPV purchase for specific content (to check if fan has access)"""
        user = require_auth(info)
        
        try:
            purchase = PPVPurchase.objects.get(fan=user, content_id=contentId)
            return PPVPurchaseType.from_model(purchase)
        except PPVPurchase.DoesNotExist:
            return None
    
    @strawberry.field
    def check_content_access(
        self,
        info: strawberry.types.Info,
        contentId: strawberry.ID
    ) -> bool:
        """Check if current user has PPV access to content"""
        user = require_auth(info)
        
        try:
            purchase = PPVPurchase.objects.get(fan=user, content_id=contentId)
            return purchase.has_access
        except PPVPurchase.DoesNotExist:
            return False
    
    # Creator Queries
    @strawberry.field
    def my_ppv_sales(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[PPVPurchaseType]:
        """Get PPV sales for creator's content"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
            queryset = PPVPurchase.objects.filter(creator=profile)
            if status:
                queryset = queryset.filter(status=status)
            return [PPVPurchaseType.from_model(p) for p in queryset.order_by('-purchased_at')[:limit]]
        except CreatorProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def my_ppv_statistics(self, info: strawberry.types.Info) -> PPVStatisticsType:
        """Get PPV sales statistics for creator"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        from django.db.models import Sum, Count
        
        try:
            profile = CreatorProfile.objects.get(user=user)
            purchases = PPVPurchase.objects.filter(creator=profile)
            
            total = purchases.count()
            completed = purchases.filter(status=PPVPurchaseStatus.COMPLETED).count()
            pending = purchases.filter(status=PPVPurchaseStatus.PENDING).count()
            refunded = purchases.filter(status=PPVPurchaseStatus.REFUNDED).count()
            
            revenue = purchases.filter(status=PPVPurchaseStatus.COMPLETED).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
            
            platform_fees = purchases.filter(status=PPVPurchaseStatus.COMPLETED).aggregate(
                total=Sum('platform_fee')
            )['total'] or Decimal('0')
            
            net = purchases.filter(status=PPVPurchaseStatus.COMPLETED).aggregate(
                total=Sum('net_amount')
            )['total'] or Decimal('0')
            
            return PPVStatisticsType(
                totalPurchases=total,
                totalRevenue=revenue,
                totalPlatformFees=platform_fees,
                totalNetAmount=net,
                completedPurchases=completed,
                pendingPurchases=pending,
                refundedPurchases=refunded
            )
        except CreatorProfile.DoesNotExist:
            return PPVStatisticsType(
                totalPurchases=0,
                totalRevenue=Decimal('0'),
                totalPlatformFees=Decimal('0'),
                totalNetAmount=Decimal('0'),
                completedPurchases=0,
                pendingPurchases=0,
                refundedPurchases=0
            )
    
    # Admin Queries
    @strawberry.field
    def all_ppv_purchases(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        creatorId: Optional[strawberry.ID] = None,
        limit: int = 100
    ) -> List[PPVPurchaseType]:
        """Get all PPV purchases (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = PPVPurchase.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)
        
        return [PPVPurchaseType.from_model(p) for p in queryset.order_by('-purchased_at')[:limit]]
    
    @strawberry.field
    def ppv_access_logs(
        self,
        info: strawberry.types.Info,
        purchaseId: strawberry.ID,
        limit: int = 50
    ) -> List[PPVAccessLogType]:
        """Get access logs for a purchase (admin or the purchase owner)"""
        user = require_auth(info)
        
        try:
            purchase = PPVPurchase.objects.get(id=purchaseId)
            # Only admin or the fan who purchased can see logs
            if user.role not in [UserRoles.ADMIN, 'superadmin'] and purchase.fan != user:
                return []
            
            logs = PPVAccessLog.objects.filter(purchase=purchase).order_by('-accessed_at')[:limit]
            return [PPVAccessLogType.from_model(log) for log in logs]
        except PPVPurchase.DoesNotExist:
            return []
