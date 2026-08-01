import strawberry
from typing import Optional
from datetime import datetime
from ..models import Tenant

@strawberry.type
class TenantType:
    id: strawberry.ID
    name: str
    domain: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, instance: Tenant):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            domain=instance.domain,
            is_active=instance.is_active,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )

@strawberry.input
class TenantInput:
    name: str
    domain: str
    is_active: Optional[bool] = True

@strawberry.input
class TenantUpdateInput:
    name: Optional[str] = None
    domain: Optional[str] = None
    is_active: Optional[bool] = None
