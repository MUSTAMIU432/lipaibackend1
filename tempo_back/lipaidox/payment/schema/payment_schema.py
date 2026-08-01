import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import PaymentMethod, MobileMoneyProvider

@strawberry.type
class MobileMoneyProviderType:
    id: strawberry.ID
    providerName: str
    countryName: str
    countryCode: str
    dialCode: str
    isActive: bool

    @classmethod
    def from_model(cls, instance: MobileMoneyProvider):
        return cls(
            id=strawberry.ID(str(instance.id)),
            providerName=instance.provider_name,
            countryName=instance.country_name,
            countryCode=instance.country_code,
            dialCode=instance.dial_code,
            isActive=instance.is_active,
        )

@strawberry.type
class PaymentMethodType:
    id: strawberry.ID
    methodType: str
    status: str
    isPrimary: bool
    isVerified: bool
    bankName: Optional[str]
    bankAccountHolderName: Optional[str]
    bankAccountNumberLast4: Optional[str]
    mobileMoneyProvider: Optional[str]
    mobileMoneyPhoneNumber: Optional[str]
    mobileMoneyPhoneCountryCode: Optional[str]
    mobileMoneyAccountName: Optional[str]
    cardLast4: Optional[str]
    cardBrand: Optional[str]
    payoutCurrency: str
    payoutFrequency: str
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: PaymentMethod):
        return cls(
            id=strawberry.ID(str(instance.id)),
            methodType=instance.method_type,
            status=instance.status,
            isPrimary=instance.is_primary,
            isVerified=instance.is_verified,
            bankName=instance.bank_name,
            bankAccountHolderName=instance.bank_account_holder_name,
            bankAccountNumberLast4=instance.bank_account_number_last4,
            mobileMoneyProvider=instance.mobile_money_provider,
            mobileMoneyPhoneNumber=instance.mobile_money_phone_number,
            mobileMoneyPhoneCountryCode=instance.mobile_money_phone_country_code,
            mobileMoneyAccountName=instance.mobile_money_account_name,
            cardLast4=instance.card_last4,
            cardBrand=instance.card_brand,
            payoutCurrency=instance.payout_currency,
            payoutFrequency=instance.payout_frequency,
            createdAt=instance.created_at,
        )

@strawberry.input
class BankTransferInput:
    bankName: str
    bankAccountHolderName: str
    bankAccountNumber: str
    bankSwiftCode: Optional[str] = None
    bankIban: Optional[str] = None
    bankCountry: Optional[str] = None

@strawberry.input
class MobileMoneyInput:
    provider: str
    phoneNumber: str
    countryCode: str
    accountName: str

@strawberry.input
class CardInput:
    holderName: str
    gatewayToken: str
    brand: str
    last4: str
    expiryMonth: int
    expiryYear: int
