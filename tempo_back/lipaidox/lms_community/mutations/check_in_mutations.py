import strawberry
from typing import List, Optional
from ..schema.check_in_types import AccountabilityCheckInNode
from ..models.check_in import AccountabilityCheckIn, MoodType
from ..models.accountability_group import AccountabilityMember

@strawberry.type
class CheckInMutations:
    @strawberry.mutation
    def create_check_in(
        self,
        info,
        group_id: strawberry.ID,
        content: str,
        hours_logged: float,
        mood: str = "good",
        achievements: Optional[List[str]] = None,
        blockers: Optional[List[str]] = None
    ) -> AccountabilityCheckInNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        # Check if user is group member
        member = AccountabilityMember.objects.filter(
            group_id=group_id,
            student__user=user
        ).first()
        if not member:
            raise Exception("Not a member of this group")
        
        check_in = AccountabilityCheckIn.objects.create(
            group_id=group_id,
            user=user,
            content=content,
            hours_logged=hours_logged,
            mood=mood,
            achievements=achievements or [],
            blockers=blockers or [],
            tenant=user.tenant
        )
        
        # Update member's current week hours
        member.current_week_hours += hours_logged
        member.save()
        
        return AccountabilityCheckInNode.from_model(check_in)

    @strawberry.mutation
    def update_weekly_goal(
        self,
        info,
        group_id: strawberry.ID,
        weekly_goal_hours: float
    ) -> bool:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        member = AccountabilityMember.objects.filter(
            group_id=group_id,
            student__user=user
        ).first()
        if not member:
            raise Exception("Not a member of this group")
        
        member.weekly_goal_hours = weekly_goal_hours
        member.save()
        return True

    @strawberry.mutation
    def reset_weekly_hours(self, info, group_id: strawberry.ID) -> bool:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        member = AccountabilityMember.objects.filter(
            group_id=group_id,
            student__user=user
        ).first()
        if not member:
            raise Exception("Not a member of this group")
        
        member.current_week_hours = 0
        member.save()
        return True
