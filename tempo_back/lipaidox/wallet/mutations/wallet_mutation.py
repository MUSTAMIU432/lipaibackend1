import strawberry
from typing import Optional
from django.db import transaction
from django.utils import timezone
from ..models import (
    CreatorWallet, WalletTransaction, PayoutTransaction, WalletClearingJob,
    WalletTransactionType, WalletTransactionStatus, PayoutStatus
)
from ..schema.wallet_schema import (
    CreatorWalletType, WalletTransactionType, PayoutTransactionType,
    RequestPayoutInput, UpdateWalletInput
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
class WalletMutation:
    # Creator Mutations
    @strawberry.mutation
    def request_payout(self, info: strawberry.types.Info, input: RequestPayoutInput) -> PayoutTransactionType:
        """Request a payout from available balance"""
        user = require_auth(info)
        require_creator(user)
        
        from lipaidox.creator_profile.models import CreatorProfile
        from lipaidox_payment.models import PaymentMethod
        
        try:
            profile = CreatorProfile.objects.get(user=user)
            wallet = CreatorWallet.objects.get(creator=profile, currency='USD')
            payment_method = PaymentMethod.objects.get(id=input.paymentMethodId, user=user)
        except CreatorProfile.DoesNotExist:
            raise Exception("Creator profile not found")
        except CreatorWallet.DoesNotExist:
            raise Exception("Wallet not found")
        except PaymentMethod.DoesNotExist:
            raise Exception("Payment method not found")
        
        # Check minimum payout threshold (e.g., $50)
        MINIMUM_PAYOUT_THRESHOLD = 50.00
        if wallet.available_balance < MINIMUM_PAYOUT_THRESHOLD:
            raise Exception(f"Minimum payout threshold is ${MINIMUM_PAYOUT_THRESHOLD}")
        
        if input.amount > wallet.available_balance:
            raise Exception("Insufficient available balance")
        
        with transaction.atomic():
            # Create payout transaction
            payout = PayoutTransaction.objects.create(
                creator=profile,
                wallet=wallet,
                payment_method=payment_method,
                tenant=user.tenant,
                amount=input.amount,
                currency='USD',
                tax_withholding_percent=input.taxWithholdingPercent,
            )
            
            # Calculate taxes
            payout.calculate_taxes()
            payout.save()
            
            # Deduct from wallet
            wallet.deduct_available_balance(input.amount)
            
            # Create wallet transaction
            WalletTransaction.create_payout_transaction(
                wallet=wallet,
                amount=input.amount,
                payout_id=payout.id,
                description=f"Payout request - {payment_method.display_name}"
            )
            
            # Start processing (in real implementation, this would be async)
            payout.start_processing()
        
        return PayoutTransactionType.from_model(payout)
    
    @strawberry.mutation
    def cancel_payout_request(self, info: strawberry.types.Info, payoutId: strawberry.ID) -> PayoutTransactionType:
        """Cancel a pending payout request"""
        user = require_auth(info)
        require_creator(user)
        
        try:
            payout = PayoutTransaction.objects.get(id=payoutId)
            if payout.creator.user != user:
                raise Exception("You can only cancel your own payouts")
            
            if payout.status not in ['pending', 'processing']:
                raise Exception("Can only cancel pending or processing payouts")
        except PayoutTransaction.DoesNotExist:
            raise Exception("Payout not found")
        
        with transaction.atomic():
            # Return funds to wallet
            payout.wallet.add_available_balance(payout.amount)
            
            # Create reversal transaction
            WalletTransaction.create_payout_reversal_transaction(
                wallet=payout.wallet,
                amount=payout.amount,
                payout_id=payout.id,
                description="Payout request cancelled"
            )
            
            # Cancel payout
            payout.status = PayoutStatus.CANCELLED
            payout.save()
        
        return PayoutTransactionType.from_model(payout)
    
    # Admin Mutations
    @strawberry.mutation
    def approve_payout(self, info: strawberry.types.Info, payoutId: strawberry.ID) -> PayoutTransactionType:
        """Approve a payout request (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        from lipaidox_admin_panel.models import AdminAccount
        
        try:
            admin = AdminAccount.objects.get(user=user)
            payout = PayoutTransaction.objects.get(id=payoutId)
        except AdminAccount.DoesNotExist:
            raise Exception("Admin account not found")
        except PayoutTransaction.DoesNotExist:
            raise Exception("Payout not found")
        
        if payout.status != 'pending':
            raise Exception("Payout is not pending")
        
        payout.approve_payout(admin)
        return PayoutTransactionType.from_model(payout)
    
    @strawberry.mutation
    def complete_payout(
        self,
        info: strawberry.types.Info,
        payoutId: strawberry.ID,
        gatewayReference: Optional[str] = None,
        gatewayResponse: Optional[str] = None
    ) -> PayoutTransactionType:
        """Mark a payout as completed (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            payout = PayoutTransaction.objects.get(id=payoutId)
        except PayoutTransaction.DoesNotExist:
            raise Exception("Payout not found")
        
        if payout.status not in ['processing', 'pending']:
            raise Exception("Payout is not being processed")
        
        with transaction.atomic():
            # Complete payout
            payout.complete_payout(gatewayReference, gatewayResponse)
            
            # Record in wallet
            payout.wallet.record_payout(payout.net_payout_amount)
        
        return PayoutTransactionType.from_model(payout)
    
    @strawberry.mutation
    def fail_payout(
        self,
        info: strawberry.types.Info,
        payoutId: strawberry.ID,
        failureReason: str,
        failureNote: Optional[str] = None
    ) -> PayoutTransactionType:
        """Mark a payout as failed (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            payout = PayoutTransaction.objects.get(id=payoutId)
        except PayoutTransaction.DoesNotExist:
            raise Exception("Payout not found")
        
        if payout.status not in ['processing', 'pending']:
            raise Exception("Payout is not being processed")
        
        with transaction.atomic():
            # Fail payout
            payout.fail_payout(failureReason, failureNote)
            
            # Return funds to wallet
            payout.wallet.add_available_balance(payout.amount)
            
            # Create reversal transaction
            WalletTransaction.create_payout_reversal_transaction(
                wallet=payout.wallet,
                amount=payout.amount,
                payout_id=payout.id,
                description=f"Payout failed: {failureReason}"
            )
        
        return PayoutTransactionType.from_model(payout)
    
    @strawberry.mutation
    def reverse_payout(
        self,
        info: strawberry.types.Info,
        payoutId: strawberry.ID,
        reversalReason: str
    ) -> PayoutTransactionType:
        """Reverse a completed payout (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        from lipaidox_admin_panel.models import AdminAccount
        
        try:
            admin = AdminAccount.objects.get(user=user)
            payout = PayoutTransaction.objects.get(id=payoutId)
        except AdminAccount.DoesNotExist:
            raise Exception("Admin account not found")
        except PayoutTransaction.DoesNotExist:
            raise Exception("Payout not found")
        
        if payout.status != 'completed':
            raise Exception("Can only reverse completed payouts")
        
        payout.reverse_payout(reversalReason, admin)
        return PayoutTransactionType.from_model(payout)
    
    @strawberry.mutation
    def hold_wallet_balance(
        self,
        info: strawberry.types.Info,
        creatorId: strawberry.ID,
        amount: float,
        reason: str
    ) -> CreatorWalletType:
        """Hold creator balance (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            wallet = CreatorWallet.objects.get(creator_id=creatorId, currency='USD')
        except CreatorWallet.DoesNotExist:
            raise Exception("Wallet not found")
        
        with transaction.atomic():
            # Hold balance
            wallet.hold_balance(amount)
            
            # Create transaction record
            WalletTransaction.create_earning_transaction(
                wallet=wallet,
                amount=-amount,
                transaction_type='adjustment',
                description=f"Balance held: {reason}"
            )
        
        return CreatorWalletType.from_model(wallet)
    
    @strawberry.mutation
    def release_wallet_hold(
        self,
        info: strawberry.types.Info,
        creatorId: strawberry.ID,
        amount: float,
        reason: str
    ) -> CreatorWalletType:
        """Release held balance (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            wallet = CreatorWallet.objects.get(creator_id=creatorId, currency='USD')
        except CreatorWallet.DoesNotExist:
            raise Exception("Wallet not found")
        
        with transaction.atomic():
            # Release hold
            wallet.release_hold_balance(amount)
            
            # Create transaction record
            WalletTransaction.create_earning_transaction(
                wallet=wallet,
                amount=amount,
                transaction_type='adjustment',
                description=f"Balance hold released: {reason}"
            )
        
        return CreatorWalletType.from_model(wallet)
    
    @strawberry.mutation
    def process_clearing_jobs(self, info: strawberry.types.Info) -> str:
        """Process pending clearing jobs (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        result = WalletClearingJob.process_pending_jobs()
        return f"Processed {result['total']} jobs: {result['processed']} successful, {result['failed']} failed"
    
    @strawberry.mutation
    def add_wallet_bonus(
        self,
        info: strawberry.types.Info,
        creatorId: strawberry.ID,
        amount: float,
        reason: str
    ) -> WalletTransactionType:
        """Add bonus to creator wallet (admin only)"""
        user = require_auth(info)
        if user.role not in [UserRoles.ADMIN, 'superadmin']:
            raise Exception("Admin access required")
        
        try:
            wallet = CreatorWallet.objects.get(creator_id=creatorId, currency='USD')
        except CreatorWallet.DoesNotExist:
            raise Exception("Wallet not found")
        
        with transaction.atomic():
            # Add to available balance directly (bonus)
            wallet.add_available_balance(amount)
            
            # Create transaction
            wallet_transaction = WalletTransaction.create_earning_transaction(
                wallet=wallet,
                amount=amount,
                transaction_type='bonus',
                description=f"Bonus: {reason}"
            )
            
            # Mark as cleared immediately
            wallet_transaction.mark_cleared()
        
        return WalletTransactionType.from_model(wallet_transaction)
