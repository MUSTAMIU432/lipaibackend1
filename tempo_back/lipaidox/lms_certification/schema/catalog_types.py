import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.catalog import AvailableCertification, CertificationEnrollment

@strawberry.type
class CertificationEnrollmentNode:
    id: strawberry.ID
    progressPercent: int
    enrolledAt: datetime
    completedAt: Optional[datetime]

    @classmethod
    def from_model(cls, instance: CertificationEnrollment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            progressPercent=instance.progress_percent,
            enrolledAt=instance.enrolled_at,
            completedAt=instance.completed_at,
        )

@strawberry.type
class AvailableCertificationNode:
    id: strawberry.ID
    title: str
    provider: str
    certType: str
    difficulty: str
    estimatedHours: int
    price: float
    currency: str
    requirements: List[str]
    skills: List[str]
    enrolledCount: int
    passRate: float

    @classmethod
    def from_model(cls, instance: AvailableCertification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            provider=instance.provider,
            certType=instance.cert_type,
            difficulty=instance.difficulty,
            estimatedHours=instance.estimated_hours,
            price=float(instance.price),
            currency=instance.currency,
            requirements=instance.requirements or [],
            skills=instance.skills or [],
            enrolledCount=instance.enrolled_count,
            passRate=float(instance.pass_rate),
        )
