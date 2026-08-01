import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.talent import TalentPoolProfile
from lipaidox.lms_identity.schema.types import StudentNode

@strawberry.type
class TalentPoolProfileNode:
    id: strawberry.ID
    student: StudentNode
    isVisible: bool
    bio: Optional[str]
    skills: List[str]
    desiredSalary: Optional[float]
    availability: str

    @classmethod
    def from_model(cls, instance: TalentPoolProfile):
        return cls(
            id=strawberry.ID(str(instance.id)),
            student=StudentNode.from_model(instance.student),
            isVisible=instance.is_visible,
            bio=instance.bio,
            skills=instance.skills or [],
            desiredSalary=float(instance.desired_salary) if instance.desired_salary else None,
            availability=instance.availability,
        )
