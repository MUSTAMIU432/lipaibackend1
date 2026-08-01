import strawberry
from datetime import datetime
from typing import Optional
from ..models.payment_method import StudentPaymentMethod

@strawberry.type
class StudentPaymentMethodNode:
    id: strawberry.ID
    userId: strawberry.ID
    methodType: str
    status: str
    isDefault: bool
    stripePaymentMethodId: Optional[str]
    stripeCustomerId: Optional[str]
    
    # Card details
    cardBrand: Optional[str]
    cardLast4: Optional[str]
    cardExpMonth: Optional[int]
    cardExpYear: Optional[int]
    
    # Bank account details
    bankName: Optional[str]
    bankAccountLast4: Optional[str]
    
    # Mobile money details
    mobileMoneyProvider: Optional[str]
    mobileMoneyNumber: Optional[str]
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime
    expiresAt: Optional[datetime]
    
    # Display name
    displayName: str

    @classmethod
    def from_model(cls, instance: StudentPaymentMethod):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user.id)),
            methodType=instance.method_type,
            status=instance.status,
            isDefault=instance.is_default,
            stripePaymentMethodId=instance.stripe_payment_method_id,
            stripeCustomerId=instance.stripe_customer_id,
            cardBrand=instance.card_brand,
            cardLast4=instance.card_last4,
            cardExpMonth=instance.card_exp_month,
            cardExpYear=instance.card_exp_year,
            bankName=instance.bank_name,
            bankAccountLast4=instance.bank_account_last4,
            mobileMoneyProvider=instance.mobile_money_provider,
            mobileMoneyNumber=instance.mobile_money_number,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
            expiresAt=instance.expires_at,
            displayName=str(instance)
        )
