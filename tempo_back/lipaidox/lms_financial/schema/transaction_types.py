import strawberry
from datetime import datetime
from typing import Optional
from ..models.transaction import LmsPayment, LmsInvoice

@strawberry.type
class LmsPaymentNode:
    id: strawberry.ID
    amount: float
    currency: str
    status: str
    paymentMethod: Optional[str]
    stripePaymentId: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: LmsPayment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            amount=float(instance.amount),
            currency=instance.currency,
            status=instance.status,
            paymentMethod=instance.payment_method,
            stripePaymentId=instance.stripe_payment_id,
            createdAt=instance.created_at,
        )

@strawberry.type
class LmsInvoiceNode:
    id: strawberry.ID
    amount: float
    status: str
    invoiceUrl: Optional[str]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: LmsInvoice):
        return cls(
            id=strawberry.ID(str(instance.id)),
            amount=float(instance.amount),
            status=instance.status,
            invoiceUrl=instance.invoice_url,
            createdAt=instance.created_at,
        )
