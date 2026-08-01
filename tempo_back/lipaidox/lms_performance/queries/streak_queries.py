import strawberry
from typing import Optional
from ..models.streak import LearningStreak

@strawberry.type
class LearningStreakNode:
    currentStreak: int
    longestStreak: int
    lastActivityDate: Optional[str]

@strawberry.type
class StreakQueries:
    @strawberry.field
    def my_learning_streak(self, info) -> Optional[LearningStreakNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        streak = LearningStreak.objects.filter(student__user=user).first()
        return LearningStreakNode(
            currentStreak=streak.current_streak,
            longestStreak=streak.longest_streak,
            lastActivityDate=streak.last_activity_date.isoformat() if streak and streak.last_activity_date else None
        ) if streak else None
