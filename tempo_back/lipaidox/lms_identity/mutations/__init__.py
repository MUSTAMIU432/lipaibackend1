import strawberry
from .profile_mutations import ProfileMutations
from .settings_mutations import SettingsMutations
from .professional_mutations import ProfessionalMutations

@strawberry.type
class IdentityMutations(
    ProfileMutations,
    SettingsMutations,
    ProfessionalMutations
):
    pass
