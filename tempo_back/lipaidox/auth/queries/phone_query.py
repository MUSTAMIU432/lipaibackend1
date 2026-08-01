import strawberry
from typing import List, Optional
from ..models import PhoneVerification
from ..schema.phone_schema import PhoneVerificationType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class PhoneQuery:
    @strawberry.field
    def all_phone_verifications(self) -> List[PhoneVerificationType]:
        tenant = get_current_tenant()
        verifications = PhoneVerification.objects.filter(user__tenant_id=tenant.id)
        return [PhoneVerificationType.from_model(v) for v in verifications]

    @strawberry.field
    def phone_verification_by_id(self, id: strawberry.ID) -> Optional[PhoneVerificationType]:
        tenant = get_current_tenant()
        try:
            verif = PhoneVerification.objects.get(id=id, user__tenant_id=tenant.id)
            return PhoneVerificationType.from_model(verif)
        except PhoneVerification.DoesNotExist:
            return None
