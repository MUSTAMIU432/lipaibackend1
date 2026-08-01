import strawberry
from typing import List, Optional
from ..schema.accountability_types import AccountabilityGroupNode, AccountabilityMemberNode
from ..models.accountability_group import AccountabilityGroup, AccountabilityMember

@strawberry.type
class AccountabilityQueries:
    @strawberry.field
    def all_groups(self) -> List[AccountabilityGroupNode]:
        return [AccountabilityGroupNode.from_model(g) for g in AccountabilityGroup.objects.filter(is_private=False)]

    @strawberry.field
    def my_groups(self, info) -> List[AccountabilityGroupNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [AccountabilityGroupNode.from_model(m.group) for m in AccountabilityMember.objects.filter(student__user=user)]

    @strawberry.field
    def group_members(self, group_id: strawberry.ID) -> List[AccountabilityMemberNode]:
        return [AccountabilityMemberNode.from_model(m) for m in AccountabilityMember.objects.filter(group_id=group_id).order_by('-current_week_hours')]

    @strawberry.field
    def my_group_membership(self, info, group_id: strawberry.ID) -> Optional[AccountabilityMemberNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        member = AccountabilityMember.objects.filter(group_id=group_id, student__user=user).first()
        return AccountabilityMemberNode.from_model(member) if member else None
