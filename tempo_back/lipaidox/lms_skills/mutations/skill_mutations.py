import strawberry
from typing import Optional
from ..schema.skill_types import StudentSkillNode
from ..schema.assessment_types import SkillAssessmentNode
from ..models.skill import StudentSkill
from ..models.assessment import SkillAssessment
from ..models.category import SkillCategory
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class SkillsMutations:
    @strawberry.mutation
    def add_student_skill(
        self,
        info,
        category_id: strawberry.ID,
        skill_name: str,
        proficiency_level: int = 1
    ) -> StudentSkillNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        student = StudentProfile.objects.get(user=user)
        category = SkillCategory.objects.get(id=category_id)
        
        skill, created = StudentSkill.objects.get_or_create(
            student=student,
            skill_name=skill_name,
            defaults={'category': category, 'proficiency_level': proficiency_level}
        )
        if not created:
            skill.proficiency_level = proficiency_level
            skill.save()
            
        return StudentSkillNode.from_model(skill)

    @strawberry.mutation
    def record_assessment_score(
        self,
        info,
        skill_id: strawberry.ID,
        score: int,
        passed: bool = False
    ) -> SkillAssessmentNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        student_skill = StudentSkill.objects.get(id=skill_id)
        
        assessment = SkillAssessment.objects.create(
            student=student,
            student_skill=student_skill,
            score=score,
            passed=passed
        )
        
        # Auto-update skill verification if passed
        if passed:
            student_skill.is_verified = True
            student_skill.save()
            
        return SkillAssessmentNode.from_model(assessment)
