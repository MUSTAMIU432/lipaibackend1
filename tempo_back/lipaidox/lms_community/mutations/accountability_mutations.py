import strawberry
from django.utils import timezone
from typing import Optional
from ..schema.accountability_types import AccountabilityGroupNode, DailyGoalNode
from ..models.accountability_group import AccountabilityGroup, AccountabilityMember, DailyGoal
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class AccountabilityMutations:
    @strawberry.mutation
    def create_accountability_group(
        self,
        info,
        name: str,
        slug: str,
        max_members: int = 10
    ) -> AccountabilityGroupNode:
        user = info.context.request.user
        group = AccountabilityGroup.objects.create(
            name=name,
            slug=slug,
            max_members=max_members,
            tenant=user.tenant
        )
        student = StudentProfile.objects.get(user=user)
        AccountabilityMember.objects.create(group=group, student=student)
        return AccountabilityGroupNode.from_model(group)

    @strawberry.mutation
    def join_group(self, info, group_id: strawberry.ID) -> AccountabilityGroupNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        group = AccountabilityGroup.objects.get(id=group_id)
        AccountabilityMember.objects.get_or_create(group=group, student=student)
        return AccountabilityGroupNode.from_model(group)

    @strawberry.mutation
    def set_daily_goal(
        self,
        info,
        group_id: strawberry.ID,
        goal_description: str
    ) -> DailyGoalNode:
        user = info.context.request.user
        member = AccountabilityMember.objects.get(group_id=group_id, student__user=user)
        goal, created = DailyGoal.objects.get_or_create(
            member=member,
            date=timezone.now().date(),
            defaults={'goal_description': goal_description}
        )
        if not created:
            goal.goal_description = goal_description
            goal.save()
        return DailyGoalNode.from_model(goal)

    @strawberry.mutation
    def complete_daily_goal(self, info, goal_id: int) -> DailyGoalNode:
        goal = DailyGoal.objects.get(id=goal_id)
        goal.is_completed = True
        goal.completed_at = timezone.now()
        goal.save()
        
        # Streak logic
        member = goal.member
        member.current_streak += 1
        if member.current_streak > member.best_streak:
            member.best_streak = member.current_streak
        member.save()
        
        return DailyGoalNode.from_model(goal)
