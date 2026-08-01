import strawberry
from typing import List
from ..models import RefreshToken
from ..schema.token_schema import RefreshTokenType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class TokenQuery:
    @strawberry.field
    def active_refresh_tokens(self) -> List[RefreshTokenType]:
        tenant = get_current_tenant()
        tokens = RefreshToken.objects.filter(user__tenant_id=tenant.id, status="active")
        return [RefreshTokenType.from_model(t) for t in tokens]
