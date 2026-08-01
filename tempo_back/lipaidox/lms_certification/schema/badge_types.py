import strawberry
from datetime import datetime
from typing import List
from ..models.badge import SkillBadge, BadgeEndorsement
from lipaidox.lms_identity.schema.types import StudentNode

@strawberry.type
class BadgeEndorsementNode:
    endorsedByUsername: str
    endorsedAt: datetime

    @classmethod
    def from_model(cls, instance: BadgeEndorsement):
        return cls(
            endorsedByUsername=instance.endorsed_by.username,
            endorsedAt=instance.endorsed_at,
        )

@strawberry.type
class SkillBadgeNode:
    id: strawberry.ID
    skillName: str
    badgeType: str
    score: int
    assessmentsCount: int
    endorsementsCount: int
    earnedAt: datetime
    verificationCode: str
    endorsements: List[BadgeEndorsementNode]

    @classmethod
    def from_model(cls, instance: SkillBadge):
        return cls(
            id=strawberry.ID(str(instance.id)),
            skillName=instance.skill_name,
            badgeType=instance.badge_type,
            score=instance.score,
            assessmentsCount=instance.assessments_count,
            endorsementsCount=instance.endorsements_count,
            earnedAt=instance.earned_at,
            verificationCode=instance.verification_code,
            endorsements=[BadgeEndorsementNode.from_model(e) for e in instance.endorsements.all()],
        )
