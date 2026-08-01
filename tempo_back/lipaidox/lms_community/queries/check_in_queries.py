import strawberry
from typing import List, Optional
from ..schema.check_in_types import AccountabilityCheckInNode
from ..models.check_in import AccountabilityCheckIn

@strawberry.type
class CheckInQueries:
    @strawberry.field
    def group_check_ins(self, group_id: strawberry.ID, limit: int = 20) -> List[AccountabilityCheckInNode]:
        return [AccountabilityCheckInNode.from_model(c) for c in AccountabilityCheckIn.objects.filter(group_id=group_id).order_by('-created_at')[:limit]]

    @strawberry.field
    def my_check_ins(self, info, group_id: strawberry.ID, limit: int = 10) -> List[AccountabilityCheckInNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [AccountabilityCheckInNode.from_model(c) for c in AccountabilityCheckIn.objects.filter(group_id=group_id, user=user).order_by('-created_at')[:limit]]

    @strawberry.field
    def today_check_ins(self, group_id: strawberry.ID) -> List[AccountabilityCheckInNode]:
        from django.utils import timezone
        today = timezone.now().date()
        return [AccountabilityCheckInNode.from_model(c) for c in AccountabilityCheckIn.objects.filter(group_id=group_id, created_at__date=today).order_by('-created_at')]
