import strawberry
from typing import Optional
from ..models.lab import Lab

@strawberry.type
class LabNode:
    id: strawberry.ID
    title: str
    labType: str
    instructions: str
    starterCode: Optional[str]
    solutionCode: Optional[str]
    language: str
    timeLimitMins: int

    @classmethod
    def from_model(cls, instance: Lab):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            labType=instance.lab_type,
            instructions=instance.instructions,
            starterCode=instance.starter_code,
            solutionCode=instance.solution_code,
            language=instance.language,
            timeLimitMins=instance.time_limit_mins,
        )
