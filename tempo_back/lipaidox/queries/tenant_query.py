import strawberry
from typing import List, Optional
from ..models import Tenant
from ..schema.tenant_schema import TenantType

@strawberry.type
class TenantQuery:
    @strawberry.field
    def all_tenants(self) -> List[TenantType]:
        tenants = Tenant.objects.all()
        return [TenantType.from_model(t) for t in tenants]

    @strawberry.field
    def tenant_by_id(self, id: strawberry.ID) -> Optional[TenantType]:
        try:
            tenant = Tenant.objects.get(id=id)
            return TenantType.from_model(tenant)
        except Tenant.DoesNotExist:
            return None

    @strawberry.field
    def tenant_by_domain(self, domain: str) -> Optional[TenantType]:
        try:
            tenant = Tenant.objects.get(domain=domain)
            return TenantType.from_model(tenant)
        except Tenant.DoesNotExist:
            return None
