import strawberry
from typing import Optional, List
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from ..models import (
    CreatorWallet, WalletTransaction, PayoutTransaction, Transaction, WalletClearingJob,
    WalletTransactionType, WalletTransactionStatus, PayoutStatus, TransactionType, TransactionStatus
)
from ..schema.wallet_schema import (
    CreatorWalletType, WalletTransactionType, PayoutTransactionType, TransactionType,
    WalletClearingJobType, WalletStatisticsType, PayoutStatisticsType,
    WalletTransactionFilterInput, PayoutFilterInput
)
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
class WalletQuery:
    # Creator Wallet Queries
    @strawberry.field
    def my_wallet(self, info: strawberry.types.Info, currency: str = 'USD') -> Optional[CreatorWalletType]:
        """Get current user's wallet"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
            wallet, created = CreatorWallet.objects.get_or_create(
                creator=profile,
                currency=currency,
                defaults={'tenant': user.tenant}
            )
            return CreatorWalletType.from_model(wallet)
        except CreatorProfile.DoesNotExist:
            return None
    
    @strawberry.field
    def my_wallet_statistics(self, info: strawberry.types.Info, currency: str = 'USD') -> WalletStatisticsType:
        """Get wallet statistics for current user"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        from django.db.models import Count, Q
        
        try:
            profile = CreatorProfile.objects.get(user=user)
            wallet, _ = CreatorWallet.objects.get_or_create(
                creator=profile,
                currency=currency,
                defaults={'tenant': user.tenant}
            )
            
            transactions = WalletTransaction.objects.filter(wallet=wallet)
            total_transactions = transactions.count()
            pending_transactions = transactions.filter(status='pending').count()
            cleared_transactions = transactions.filter(status='cleared').count()
            
            return WalletStatisticsType(
                totalEarnings=wallet.lifetime_earnings,
                pendingBalance=wallet.pending_balance,
                availableBalance=wallet.available_balance,
                onHoldBalance=wallet.on_hold_balance,
                lifetimePayouts=wallet.lifetime_payouts,
                totalTransactions=total_transactions,
                pendingTransactions=pending_transactions,
                clearedTransactions=cleared_transactions
            )
        except CreatorProfile.DoesNotExist:
            return WalletStatisticsType(
                totalEarnings=0,
                pendingBalance=0,
                availableBalance=0,
                onHoldBalance=0,
                lifetimePayouts=0,
                totalTransactions=0,
                pendingTransactions=0,
                clearedTransactions=0
            )
    
    @strawberry.field
    def my_wallet_transactions(
        self,
        info: strawberry.types.Info,
        currency: str = 'USD',
        filter: Optional[WalletTransactionFilterInput] = None,
        limit: int = 50
    ) -> List[WalletTransactionType]:
        """Get wallet transactions for current user"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
            wallet, _ = CreatorWallet.objects.get_or_create(
                creator=profile,
                currency=currency,
                defaults={'tenant': user.tenant}
            )
            
            queryset = WalletTransaction.objects.filter(wallet=wallet)
            
            if filter:
                if filter.transactionType:
                    queryset = queryset.filter(transaction_type=filter.transactionType)
                if filter.status:
                    queryset = queryset.filter(status=filter.status)
                if filter.balanceType:
                    queryset = queryset.filter(balance_type=filter.balanceType)
                if filter.dateFrom:
                    queryset = queryset.filter(created_at__gte=filter.dateFrom)
                if filter.dateTo:
                    queryset = queryset.filter(created_at__lte=filter.dateTo)
            
            return [WalletTransactionType.from_model(tx) for tx in queryset.order_by('-created_at')[:limit]]
        except CreatorProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def my_payout_transactions(
        self,
        info: strawberry.types.Info,
        currency: str = 'USD',
        filter: Optional[PayoutFilterInput] = None,
        limit: int = 50
    ) -> List[PayoutTransactionType]:
        """Get payout transactions for current user"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        try:
            profile = CreatorProfile.objects.get(user=user)
            wallet, _ = CreatorWallet.objects.get_or_create(
                creator=profile,
                currency=currency,
                defaults={'tenant': user.tenant}
            )
            
            queryset = PayoutTransaction.objects.filter(wallet=wallet)
            
            if filter:
                if filter.status:
                    queryset = queryset.filter(status=filter.status)
                if filter.dateFrom:
                    queryset = queryset.filter(created_at__gte=filter.dateFrom)
                if filter.dateTo:
                    queryset = queryset.filter(created_at__lte=filter.dateTo)
            
            return [PayoutTransactionType.from_model(payout) for payout in queryset.order_by('-created_at')[:limit]]
        except CreatorProfile.DoesNotExist:
            return []
    
    @strawberry.field
    def my_payout_statistics(self, info: strawberry.types.Info, currency: str = 'USD') -> PayoutStatisticsType:
        """Get payout statistics for current user"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        from django.db.models import Sum
        
        try:
            profile = CreatorProfile.objects.get(user=user)
            wallet, _ = CreatorWallet.objects.get_or_create(
                creator=profile,
                currency=currency,
                defaults={'tenant': user.tenant}
            )
            
            payouts = PayoutTransaction.objects.filter(wallet=wallet)
            
            total_payouts = payouts.count()
            total_amount = payouts.aggregate(total=Sum('amount'))['total'] or 0
            pending_payouts = payouts.filter(status='pending').count()
            processing_payouts = payouts.filter(status='processing').count()
            completed_payouts = payouts.filter(status='completed').count()
            failed_payouts = payouts.filter(status='failed').count()
            
            last_payout = payouts.order_by('-created_at').first()
            
            return PayoutStatisticsType(
                totalPayouts=total_payouts,
                totalPayoutAmount=total_amount,
                pendingPayouts=pending_payouts,
                processingPayouts=processing_payouts,
                completedPayouts=completed_payouts,
                failedPayouts=failed_payouts,
                lastPayoutAmount=last_payout.amount if last_payout else None,
                lastPayoutAt=last_payout.created_at if last_payout else None
            )
        except CreatorProfile.DoesNotExist:
            return PayoutStatisticsType(
                totalPayouts=0,
                totalPayoutAmount=0,
                pendingPayouts=0,
                processingPayouts=0,
                completedPayouts=0,
                failedPayouts=0,
                lastPayoutAmount=None,
                lastPayoutAt=None
            )
    
    # Admin Queries
    @strawberry.field
    def creator_wallet(
        self,
        info: strawberry.types.Info,
        creatorId: strawberry.ID,
        currency: str = 'USD'
    ) -> Optional[CreatorWalletType]:
        """Get specific creator's wallet (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return None
        
        try:
            wallet = CreatorWallet.objects.get(creator_id=creatorId, currency=currency)
            return CreatorWalletType.from_model(wallet)
        except CreatorWallet.DoesNotExist:
            return None
    
    @strawberry.field
    def all_wallet_transactions(
        self,
        info: strawberry.types.Info,
        filter: Optional[WalletTransactionFilterInput] = None,
        limit: int = 100
    ) -> List[WalletTransactionType]:
        """Get all wallet transactions (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = WalletTransaction.objects.all()
        
        if filter:
            if filter.transactionType:
                queryset = queryset.filter(transaction_type=filter.transactionType)
            if filter.status:
                queryset = queryset.filter(status=filter.status)
            if filter.balanceType:
                queryset = queryset.filter(balance_type=filter.balanceType)
            if filter.dateFrom:
                queryset = queryset.filter(created_at__gte=filter.dateFrom)
            if filter.dateTo:
                queryset = queryset.filter(created_at__lte=filter.dateTo)
        
        return [WalletTransactionType.from_model(tx) for tx in queryset.order_by('-created_at')[:limit]]
    
    @strawberry.field
    def all_payout_transactions(
        self,
        info: strawberry.types.Info,
        filter: Optional[PayoutFilterInput] = None,
        limit: int = 100
    ) -> List[PayoutTransactionType]:
        """Get all payout transactions (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = PayoutTransaction.objects.all()
        
        if filter:
            if filter.status:
                queryset = queryset.filter(status=filter.status)
            if filter.dateFrom:
                queryset = queryset.filter(created_at__gte=filter.dateFrom)
            if filter.dateTo:
                queryset = queryset.filter(created_at__lte=filter.dateTo)
        
        return [PayoutTransactionType.from_model(payout) for payout in queryset.order_by('-created_at')[:limit]]
    
    @strawberry.field
    def clearing_jobs(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[WalletClearingJobType]:
        """Get clearing jobs (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = WalletClearingJob.objects.all()
        if status:
            queryset = queryset.filter(status=status)
        
        return [WalletClearingJobType.from_model(job) for job in queryset.order_by('scheduled_clear_at')[:limit]]
    
    # Platform-wide transaction queries
    @strawberry.field
    def platform_transactions(
        self,
        info: strawberry.types.Info,
        transactionType: Optional[str] = None,
        status: Optional[str] = None,
        creatorId: Optional[strawberry.ID] = None,
        limit: int = 100
    ) -> List[TransactionType]:
        """Get platform-wide transactions (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            return []
        
        queryset = Transaction.objects.all()
        
        if transactionType:
            queryset = queryset.filter(transaction_type=transactionType)
        if status:
            queryset = queryset.filter(status=status)
        if creatorId:
            queryset = queryset.filter(creator_id=creatorId)
        
        return [TransactionType.from_model(tx) for tx in queryset.order_by('-created_at')[:limit]]
