import strawberry
from datetime import datetime
from ..models.skill import StudentSkill
from .category_types import SkillCategoryNode

@strawberry.type
class StudentSkillNode:
    id: strawberry.ID
    skillName: str
    proficiencyLevel: int
    isVerified: bool
    lastUpdated: datetime
    category: SkillCategoryNode

    @classmethod
    def from_model(cls, instance: StudentSkill):
        return cls(
            id=strawberry.ID(str(instance.id)),
            skillName=instance.skill_name,
            proficiencyLevel=instance.proficiency_level,
            isVerified=instance.is_verified,
            lastUpdated=instance.last_updated,
            category=SkillCategoryNode.from_model(instance.category),
        )
