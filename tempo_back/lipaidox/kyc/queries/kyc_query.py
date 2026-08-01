import strawberry
from typing import List, Optional
from ..models import KYCStatus, VerificationDocument
from ..schema.kyc_schema import KYCStatusType, VerificationDocumentType
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator, require_admin

@strawberry.type
class KYCQuery:
    @strawberry.field
    @require_creator
    def my_kyc_status(self, info: strawberry.types.Info) -> Optional[KYCStatusType]:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        try:
            status = KYCStatus.objects.get(creator__user=user)
            return KYCStatusType.from_model(status)
        except KYCStatus.DoesNotExist:
            return None

    @strawberry.field
    @require_creator
    def my_verification_history(self, info: strawberry.types.Info) -> List[VerificationDocumentType]:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator
        docs = VerificationDocument.objects.filter(creator__user=user).order_by('-submitted_at')
        return [VerificationDocumentType.from_model(d) for d in docs]

    @strawberry.field
    @require_admin
    def admin_get_kyc_status(self, creator_id: strawberry.ID) -> Optional[KYCStatusType]:
        tenant = get_current_tenant()
        try:
            status = KYCStatus.objects.get(creator_id=creator_id, tenant=tenant)
            return KYCStatusType.from_model(status)
        except KYCStatus.DoesNotExist:
            return None
