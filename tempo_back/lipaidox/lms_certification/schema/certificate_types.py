import strawberry
from datetime import datetime
from typing import Optional
from ..models.certificate import Certificate
from lipaidox.lms_content.schema.course_types import CourseNode

@strawberry.type
class CertificateNode:
    id: strawberry.ID
    title: str
    certificateType: str
    grade: str
    score: float
    issueDate: datetime
    verificationCode: str
    publicUrl: Optional[str]
    qrCodeUrl: Optional[str]
    blockchainHash: Optional[str]
    blockchainNetwork: str
    isPublic: bool
    viewCount: int
    downloadCount: int
    course: Optional[CourseNode]

    @classmethod
    def from_model(cls, instance: Certificate):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            certificateType=instance.certificate_type,
            grade=instance.grade,
            score=float(instance.score),
            issueDate=instance.issue_date,
            verificationCode=instance.verification_code,
            publicUrl=instance.public_url,
            qrCodeUrl=instance.qr_code_url,
            blockchainHash=instance.blockchain_hash,
            blockchainNetwork=instance.blockchain_network,
            isPublic=instance.is_public,
            viewCount=instance.view_count,
            downloadCount=instance.download_count,
            course=CourseNode.from_model(instance.course) if instance.course else None,
        )
