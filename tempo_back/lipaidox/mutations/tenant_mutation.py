import strawberry
from typing import Optional
from django.db import transaction
from ..models import Tenant
from ..schema.tenant_schema import TenantType, TenantInput, TenantUpdateInput

@strawberry.type
class TenantMutation:
    @strawberry.mutation
    def create_tenant(self, input: TenantInput) -> TenantType:
        if Tenant.objects.filter(domain=input.domain).exists():
            raise Exception(f"A tenant with domain '{input.domain}' already exists.")

        with transaction.atomic():
            tenant = Tenant.objects.create(
                name=input.name,
                domain=input.domain,
                is_active=input.is_active if input.is_active is not None else True
            )
        return TenantType.from_model(tenant)

    @strawberry.mutation
    def update_tenant(self, id: strawberry.ID, input: TenantUpdateInput) -> Optional[TenantType]:
        try:
            tenant = Tenant.objects.get(id=id)
            if input.name:
                tenant.name = input.name
            if input.domain:
                tenant.domain = input.domain
            if input.is_active is not None:
                tenant.is_active = input.is_active
            
            tenant.save()
            return TenantType.from_model(tenant)
        except Tenant.DoesNotExist:
            return None

    @strawberry.mutation
    def delete_tenant(self, id: strawberry.ID) -> bool:
        try:
            tenant = Tenant.objects.get(id=id)
            tenant.delete()
            return True
        except Tenant.DoesNotExist:
            return False
