import strawberry
from django.utils import timezone
from typing import Optional
from ..schema.subscription_types import LmsSubscriptionNode
from ..schema.payment_method_types import StudentPaymentMethodNode
from ..models.plan import LmsPlan
from ..models.subscription import LmsSubscription, SubscriptionStatus
from ..models.payment_method import StudentPaymentMethod, StudentPaymentMethodType
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class FinancialMutations:
    @strawberry.mutation
    def subscribe_to_plan(self, info, plan_id: strawberry.ID, payment_method_id: Optional[strawberry.ID] = None) -> LmsSubscriptionNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        student = StudentProfile.objects.get(user=user)
        plan = LmsPlan.objects.get(id=plan_id)
        
        # Deactivate old active subscriptions (simplified logic)
        LmsSubscription.objects.filter(student=student, status=SubscriptionStatus.ACTIVE).update(
            status=SubscriptionStatus.CANCELLED,
            end_date=timezone.now()
        )
        
        subscription = LmsSubscription.objects.create(
            student=student,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            tenant=user.tenant
        )
        return LmsSubscriptionNode.from_model(subscription)

    @strawberry.mutation
    def cancel_subscription(self, info, subscription_id: strawberry.ID) -> bool:
        sub = LmsSubscription.objects.get(id=subscription_id)
        sub.status = SubscriptionStatus.CANCELLED
        sub.cancel_at_period_end = True
        sub.save()
        return True

    @strawberry.mutation
    def add_payment_method(
        self,
        info,
        method_type: str,
        stripe_payment_method_id: str,
        stripe_customer_id: str,
        is_default: bool = False
    ) -> StudentPaymentMethodNode:
        """Add a new payment method for student"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Validate method type
        try:
            payment_method_type = StudentPaymentMethodType(method_type)
        except ValueError:
            raise Exception("Invalid payment method type")
        
        # Create payment method
        payment_method = StudentPaymentMethod.objects.create(
            user=user,
            method_type=payment_method_type,
            stripe_payment_method_id=stripe_payment_method_id,
            stripe_customer_id=stripe_customer_id,
            tenant=user.tenant
        )
        
        # Set as default if requested
        if is_default:
            payment_method.mark_as_default()
        
        return StudentPaymentMethodNode.from_model(payment_method)

    @strawberry.mutation
    def set_default_payment_method(self, info, payment_method_id: strawberry.ID) -> StudentPaymentMethodNode:
        """Set a payment method as default"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            payment_method = StudentPaymentMethod.objects.get(
                id=payment_method_id,
                user=user
            )
            payment_method.mark_as_default()
            return StudentPaymentMethodNode.from_model(payment_method)
        except StudentPaymentMethod.DoesNotExist:
            raise Exception("Payment method not found")

    @strawberry.mutation
    def remove_payment_method(self, info, payment_method_id: strawberry.ID) -> bool:
        """Remove a payment method"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            payment_method = StudentPaymentMethod.objects.get(
                id=payment_method_id,
                user=user
            )
            
            # Don't allow removing default payment method if there are other active methods
            if payment_method.is_default:
                other_methods = StudentPaymentMethod.get_active_payment_methods(user).exclude(id=payment_method.id)
                if other_methods.exists():
                    raise Exception("Cannot remove default payment method. Set another as default first.")
            
            payment_method.delete()
            return True
        except StudentPaymentMethod.DoesNotExist:
            raise Exception("Payment method not found")
