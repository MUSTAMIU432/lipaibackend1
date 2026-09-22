import re
import strawberry
from typing import List, Optional
from ..models import User
from ..schema.user_schema import UserType
from multitenant.utils.tenant_context import get_current_tenant

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")

@strawberry.type
class UserQuery:
    @strawberry.field
    def all_users(self) -> List[UserType]:
        tenant = get_current_tenant()
        users = User.objects.filter(tenant=tenant)
        return [UserType.from_model(u) for u in users]

    @strawberry.field
    def signup_username_available(self, username: str) -> bool:
        """Live check for the signup form's username field — the exact rule
        `registerUser` itself enforces (uniqueness against `User.username`,
        the field signup actually creates and checks — not the unrelated
        `CreatorProfile.username` the "change username" screen checks)."""
        tenant = get_current_tenant()
        candidate = (username or "").strip().lower()
        if not USERNAME_RE.match(candidate):
            return False
        return not User.objects.filter(username=candidate, tenant=tenant).exists()

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
