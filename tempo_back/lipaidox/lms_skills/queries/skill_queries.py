import strawberry
from typing import List, Optional
from ..schema.skill_types import StudentSkillNode
from ..schema.assessment_types import SkillAssessmentNode
from ..schema.category_types import SkillCategoryNode
from ..models.skill import StudentSkill
from ..models.assessment import SkillAssessment
from ..models.category import SkillCategory

@strawberry.type
class SkillsQueries:
    @strawberry.field
    def my_skills(self, info) -> List[StudentSkillNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [StudentSkillNode.from_model(s) for s in StudentSkill.objects.filter(student__user=user)]

    @strawberry.field
    def skill_assessments(self, info) -> List[SkillAssessmentNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [SkillAssessmentNode.from_model(a) for a in SkillAssessment.objects.filter(student__user=user)]

    @strawberry.field
    def all_skill_categories(self) -> List[SkillCategoryNode]:
        return [SkillCategoryNode.from_model(c) for c in SkillCategory.objects.all()]
