import strawberry
from typing import List, Optional
from ..models import User
from ..schema.user_schema import UserType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class UserQuery:
    @strawberry.field
    def all_users(self) -> List[UserType]:
        tenant = get_current_tenant()
        users = User.objects.filter(tenant=tenant)
        return [UserType.from_model(u) for u in users]

    @strawberry.field
    def me(self, info: strawberry.types.Info) -> Optional[UserType]:
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        return UserType.from_model(user)

    @strawberry.field
    def user_by_id(self, user_id: strawberry.ID) -> Optional[UserType]:
        tenant = get_current_tenant()
        try:
            user = User.objects.get(id=user_id, tenant=tenant)
            return UserType.from_model(user)
        except User.DoesNotExist:
            return None
