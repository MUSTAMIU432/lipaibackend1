import strawberry
from .study_room_mutations import StudyRoomMutations
from .accountability_mutations import AccountabilityMutations
from .chat_mutations import ChatMutations
from .check_in_mutations import CheckInMutations

@strawberry.type
class CommunityMutations(
    StudyRoomMutations,
    AccountabilityMutations,
    ChatMutations,
    CheckInMutations
):
    pass
