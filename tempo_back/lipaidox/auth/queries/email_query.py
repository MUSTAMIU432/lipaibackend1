import strawberry
from typing import List, Optional
from ..models import EmailVerification
from ..schema.email_schema import EmailVerificationType
from multitenant.utils.tenant_context import get_current_tenant

@strawberry.type
class EmailQuery:
    @strawberry.field
    def all_email_verifications(self) -> List[EmailVerificationType]:
        tenant = get_current_tenant()
        verifications = EmailVerification.objects.filter(user__tenant_id=tenant.id)
        return [EmailVerificationType.from_model(v) for v in verifications]

    @strawberry.field
    def email_verification_by_id(self, id: strawberry.ID) -> Optional[EmailVerificationType]:
        tenant = get_current_tenant()
        try:
            verif = EmailVerification.objects.get(id=id, user__tenant_id=tenant.id)
            return EmailVerificationType.from_model(verif)
        except EmailVerification.DoesNotExist:
            return None
