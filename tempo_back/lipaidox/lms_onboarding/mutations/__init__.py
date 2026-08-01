import strawberry
from .onboarding_mutations import OnboardingMutations

@strawberry.type
class LmsOnboardingMutations(OnboardingMutations):
    pass
