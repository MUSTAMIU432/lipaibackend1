import strawberry
from .study_room_queries import StudyRoomQueries
from .accountability_queries import AccountabilityQueries
from .chat_queries import ChatQueries
from .check_in_queries import CheckInQueries

@strawberry.type
class CommunityQueries(
    StudyRoomQueries,
    AccountabilityQueries,
    ChatQueries,
    CheckInQueries
):
    pass
