import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import CreatorOnboardingStatus, OnboardingStepLog

@strawberry.type
class OnboardingStepLogType:
    id: strawberry.ID
    step: str
    event_type: str
    status_before: Optional[str]
    status_after: Optional[str]
    triggered_by: str
    reason: Optional[str]
    metadata: Optional[strawberry.scalars.JSON]
    created_at: datetime

    @classmethod
    def from_model(cls, instance: OnboardingStepLog):
        return cls(
            id=strawberry.ID(str(instance.id)),
            step=instance.step,
            event_type=instance.event_type,
            status_before=instance.status_before,
            status_after=instance.status_after,
            triggered_by=instance.triggered_by,
            reason=instance.reason,
            metadata=instance.metadata,
            created_at=instance.created_at,
        )

@strawberry.type
class CreatorOnboardingStatusType:
    id: strawberry.ID
    userId: strawberry.ID
    overall_status: str
    current_step: str
    completion_percentage: float
    
    account_created_status: str
    email_verified_status: str
    phone_verified_status: str
    profile_setup_status: str
    content_classification_status: str
    identity_verification_status: str
    payment_setup_status: str
    monetization_setup_status: str
    
    completed_at: Optional[datetime]
    activated_at: Optional[datetime]
    updated_at: datetime

    @classmethod
    def from_model(cls, instance: CreatorOnboardingStatus):
        return cls(
            id=strawberry.ID(str(instance.id)),
            userId=strawberry.ID(str(instance.user_id)),
            overall_status=instance.overall_status,
            current_step=instance.current_step,
            completion_percentage=float(instance.completion_percentage),
            account_created_status=instance.account_created_status,
            email_verified_status=instance.email_verified_status,
            phone_verified_status=instance.phone_verified_status,
            profile_setup_status=instance.profile_setup_status,
            content_classification_status=instance.content_classification_status,
            identity_verification_status=instance.identity_verification_status,
            payment_setup_status=instance.payment_setup_status,
            monetization_setup_status=instance.monetization_setup_status,
            completed_at=instance.completed_at,
            activated_at=instance.activated_at,
            updated_at=instance.updated_at,
        )

@strawberry.input
class UpdateStepInput:
    step: str
    status: str
    reason: Optional[str] = None
    metadata: Optional[strawberry.scalars.JSON] = None
