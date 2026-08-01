import strawberry
from datetime import datetime
from typing import List
from ..models.check_in import AccountabilityCheckIn

@strawberry.type
class AccountabilityCheckInNode:
    id: strawberry.ID
    content: str
    hoursLogged: float
    mood: str
    achievements: List[str]
    blockers: List[str]
    username: str
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: AccountabilityCheckIn):
        return cls(
            id=strawberry.ID(str(instance.id)),
            content=instance.content,
            hoursLogged=float(instance.hours_logged),
            mood=instance.mood,
            achievements=instance.achievements or [],
            blockers=instance.blockers or [],
            username=instance.user.username,
            createdAt=instance.created_at,
        )
