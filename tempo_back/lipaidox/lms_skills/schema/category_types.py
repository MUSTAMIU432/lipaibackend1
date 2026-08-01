import strawberry
from typing import Optional
from ..models.category import SkillCategory

@strawberry.type
class SkillCategoryNode:
    id: strawberry.ID
    name: str
    description: Optional[str]

    @classmethod
    def from_model(cls, instance: SkillCategory):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            description=instance.description,
        )
