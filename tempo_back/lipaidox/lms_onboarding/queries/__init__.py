import strawberry
from .onboarding_queries import OnboardingQueries

@strawberry.type
class LmsOnboardingQueries(OnboardingQueries):
    pass
