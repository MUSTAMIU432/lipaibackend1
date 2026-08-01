import strawberry
from typing import List, Optional
from ..schema.certificate_types import CertificateNode
from ..schema.badge_types import SkillBadgeNode
from ..schema.catalog_types import AvailableCertificationNode
from ..models.certificate import Certificate
from ..models.badge import SkillBadge
from ..models.catalog import AvailableCertification

@strawberry.type
class CertificationQueries:
    @strawberry.field
    def my_certificates(self, info) -> List[CertificateNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [CertificateNode.from_model(c) for c in Certificate.objects.filter(student__user=user)]

    @strawberry.field
    def my_badges(self, info) -> List[SkillBadgeNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [SkillBadgeNode.from_model(b) for b in SkillBadge.objects.filter(student__user=user)]

    @strawberry.field
    def available_certifications(self) -> List[AvailableCertificationNode]:
        return [AvailableCertificationNode.from_model(c) for c in AvailableCertification.objects.all()]

    @strawberry.field
    def certificate_by_code(self, code: str) -> Optional[CertificateNode]:
        cert = Certificate.objects.filter(verification_code=code).first()
        return CertificateNode.from_model(cert) if cert else None
