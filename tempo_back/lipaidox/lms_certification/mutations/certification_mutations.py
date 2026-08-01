import strawberry
import uuid
from typing import Optional
from ..schema.certificate_types import CertificateNode
from ..schema.badge_types import SkillBadgeNode
from ..schema.catalog_types import CertificationEnrollmentNode
from ..models.certificate import Certificate, CertificateType, CertificateGrade
from ..models.badge import SkillBadge, BadgeEndorsement
from ..models.catalog import AvailableCertification, CertificationEnrollment
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class CertificationMutations:
    @strawberry.mutation
    def enroll_in_certification(self, info, certification_id: strawberry.ID) -> CertificationEnrollmentNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        student = StudentProfile.objects.get(user=user)
        cert = AvailableCertification.objects.get(id=certification_id)
        
        enrollment, created = CertificationEnrollment.objects.get_or_create(
            student=student,
            certification=cert
        )
        return CertificationEnrollmentNode.from_model(enrollment)

    @strawberry.mutation
    def endorse_badge(self, info, badge_id: strawberry.ID) -> SkillBadgeNode:
        user = info.context.request.user
        badge = SkillBadge.objects.get(id=badge_id)
        
        BadgeEndorsement.objects.get_or_create(
            badge=badge,
            endorsed_by=user
        )
        
        # Update denormalized count
        badge.endorsements_count = badge.endorsements.count()
        badge.save()
        
        return SkillBadgeNode.from_model(badge)

    @strawberry.mutation
    def generate_completion_certificate(
        self,
        info,
        course_id: strawberry.ID,
        title: str
    ) -> CertificateNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        # Generation logic (simplified for now)
        code = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        
        certificate = Certificate.objects.create(
            student=student,
            course_id=course_id,
            title=title,
            verification_code=code,
            tenant=user.tenant
        )
        return CertificateNode.from_model(certificate)
