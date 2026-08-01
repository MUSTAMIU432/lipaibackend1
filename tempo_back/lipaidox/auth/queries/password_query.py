import strawberry
from typing import List, Optional
from ..models import PasswordResetToken
from ..schema.password_schema import PasswordResetTokenType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class PasswordQuery:
    @strawberry.field
    def all_password_resets(self) -> List[PasswordResetTokenType]:
        tenant = get_current_tenant()
        resets = PasswordResetToken.objects.filter(user__tenant_id=tenant.id)
        return [PasswordResetTokenType.from_model(r) for r in resets]
