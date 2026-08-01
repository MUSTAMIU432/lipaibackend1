import strawberry
from datetime import datetime
from ..models.assessment import SkillAssessment

@strawberry.type
class SkillAssessmentNode:
    id: strawberry.ID
    score: int
    maxScore: int
    passed: bool
    takenAt: datetime

    @classmethod
    def from_model(cls, instance: SkillAssessment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            score=instance.score,
            maxScore=instance.max_score,
            passed=instance.passed,
            takenAt=instance.taken_at,
        )
