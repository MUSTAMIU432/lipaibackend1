import strawberry
from typing import List, Optional
from ..schema.plan_types import LmsPlanNode
from ..schema.subscription_types import LmsSubscriptionNode
from ..schema.transaction_types import LmsPaymentNode, LmsInvoiceNode
from ..schema.payment_method_types import StudentPaymentMethodNode
from ..models.plan import LmsPlan
from ..models.subscription import LmsSubscription
from ..models.transaction import LmsPayment, LmsInvoice
from ..models.payment_method import StudentPaymentMethod

@strawberry.type
class FinancialQueries:
    @strawberry.field
    def available_plans(self) -> List[LmsPlanNode]:
        return [LmsPlanNode.from_model(p) for p in LmsPlan.objects.filter(is_active=True)]

    @strawberry.field
    def current_subscription(self, info) -> Optional[LmsSubscriptionNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        sub = LmsSubscription.objects.filter(student__user=user, status='active').first()
        return LmsSubscriptionNode.from_model(sub) if sub else None

    @strawberry.field
    def my_payment_history(self, info) -> List[LmsPaymentNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [LmsPaymentNode.from_model(p) for p in LmsPayment.objects.filter(user=user)]

    @strawberry.field
    def my_invoices(self, info) -> List[LmsInvoiceNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [LmsInvoiceNode.from_model(i) for i in LmsInvoice.objects.filter(user=user)]

    @strawberry.field
    def my_student_payment_methods(self, info) -> List[StudentPaymentMethodNode]:
        """Get student's LMS payment methods (distinct from creator payout methods)."""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        payment_methods = StudentPaymentMethod.get_active_payment_methods(user)
        return [StudentPaymentMethodNode.from_model(pm) for pm in payment_methods]

    @strawberry.field
    def default_student_payment_method(self, info) -> Optional[StudentPaymentMethodNode]:
        """Get student's default LMS payment method."""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        payment_method = StudentPaymentMethod.get_default_payment_method(user)
        return StudentPaymentMethodNode.from_model(payment_method) if payment_method else None
