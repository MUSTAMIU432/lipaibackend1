import strawberry
from django.db import transaction
from django.utils import timezone
from ..models import CreatorOnboardingStatus, OnboardingStepLog, StepStatus, LogEventType
from ..schema.onboarding_schema import CreatorOnboardingStatusType, UpdateStepInput
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class OnboardingMutation:
    @strawberry.mutation
    def update_onboarding_step(self, info: strawberry.types.Info, input: UpdateStepInput) -> CreatorOnboardingStatusType:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")

        tenant = get_current_tenant()
        
        with transaction.atomic():
            onboarding, created = CreatorOnboardingStatus.objects.get_or_create(
                user=user,
                tenant=tenant
            )
            
            # Record log
            status_field = f"{input.step}_status"
            at_field = f"{input.step}_at"
            
            old_status = getattr(onboarding, status_field, None)
            
            # Map log event
            event_type = LogEventType.STEP_COMPLETED if input.status == StepStatus.COMPLETED else LogEventType.STEP_FAILED
            
            OnboardingStepLog.objects.create(
                user=user,
                tenant=tenant,
                onboarding=onboarding,
                step=input.step,
                event_type=event_type,
                status_before=old_status,
                status_after=input.status,
                triggered_by='creator',
                reason=input.reason,
                metadata=input.metadata
            )
            
            # Update status
            setattr(onboarding, status_field, input.status)
            if input.status == StepStatus.COMPLETED:
                setattr(onboarding, at_field, timezone.now())
                onboarding.current_step = input.step # Simplified progress
            
            onboarding.calculate_completion() # This also saves
            
        return CreatorOnboardingStatusType.from_model(onboarding)
