import strawberry
from typing import List, Optional
from ..models import CreatorOnboardingStatus, OnboardingStepLog
from ..schema.onboarding_schema import CreatorOnboardingStatusType, OnboardingStepLogType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class OnboardingQuery:
    @strawberry.field
    def my_onboarding_status(self, info: strawberry.types.Info) -> Optional[CreatorOnboardingStatusType]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        try:
            status = CreatorOnboardingStatus.objects.get(user=user)
            return CreatorOnboardingStatusType.from_model(status)
        except CreatorOnboardingStatus.DoesNotExist:
            return None

    @strawberry.field
    def onboarding_logs(self, info: strawberry.types.Info) -> List[OnboardingStepLogType]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        logs = OnboardingStepLog.objects.filter(user=user).order_by('-created_at')
        return [OnboardingStepLogType.from_model(log) for log in logs]

    @strawberry.field
    def admin_get_onboarding(self, user_id: strawberry.ID) -> Optional[CreatorOnboardingStatusType]:
        tenant = get_current_tenant()
        try:
            status = CreatorOnboardingStatus.objects.get(user_id=user_id, tenant=tenant)
            return CreatorOnboardingStatusType.from_model(status)
        except CreatorOnboardingStatus.DoesNotExist:
            return None
