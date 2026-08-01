import strawberry
from datetime import datetime, date
from typing import List, Optional
from ..models.accountability_group import AccountabilityGroup, AccountabilityMember, DailyGoal
from lipaidox.lms_identity.schema.types import StudentNode
from lipaidox.lms_content.schema.course_types import CourseNode

@strawberry.type
class DailyGoalNode:
    id: strawberry.ID
    date: datetime
    goalDescription: str
    isCompleted: bool
    completedAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: DailyGoal):
        return cls(
            id=strawberry.ID(str(instance.id)),
            date=instance.date,
            goalDescription=instance.goal_description,
            isCompleted=instance.is_completed,
            completedAt=instance.completed_at,
        )

@strawberry.type
class AccountabilityMemberNode:
    id: strawberry.ID
    student: StudentNode
    username: str
    role: str
    weeklyGoalHours: float
    currentWeekHours: float
    currentStreak: int
    bestStreak: int
    joinedAt: datetime
    dailyGoals: List[DailyGoalNode]

    @classmethod
    def from_model(cls, instance: AccountabilityMember):
        return cls(
            id=strawberry.ID(str(instance.id)),
            student=StudentNode.from_model(instance.student),
            username=instance.student.user.username,
            role=instance.role,
            weeklyGoalHours=float(instance.weekly_goal_hours),
            currentWeekHours=float(instance.current_week_hours),
            currentStreak=instance.current_streak,
            bestStreak=instance.best_streak,
            joinedAt=instance.joined_at,
            dailyGoals=[DailyGoalNode.from_model(g) for g in instance.goals.all().order_by('-date')],
        )

@strawberry.type
class AccountabilityGroupNode:
    id: strawberry.ID
    name: str
    description: Optional[str]
    slug: str
    maxMembers: int
    streakThresholdDays: int
    members: List[AccountabilityMemberNode]

    @classmethod
    def from_model(cls, instance: AccountabilityGroup):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            description=instance.description,
            slug=instance.slug,
            maxMembers=instance.max_members,
            streakThresholdDays=instance.streak_threshold_days,
            members=[AccountabilityMemberNode.from_model(m) for m in instance.members.all()],
        )
