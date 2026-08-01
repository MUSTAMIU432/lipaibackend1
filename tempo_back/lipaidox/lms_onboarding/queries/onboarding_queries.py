import strawberry
from typing import List, Optional
from ..schema.onboarding_types import (
    OnboardingProgressNode,
    SkillAssessmentQuestionNode,
    SkillAssessmentResponseNode,
    OnboardingRecommendationNode,
    OnboardingStepInfo,
    OnboardingWizardData
)
from ..models.onboarding import (
    OnboardingProgress,
    SkillAssessmentQuestion,
    SkillAssessmentResponse,
    OnboardingRecommendation,
    OnboardingStep
)

@strawberry.type
class OnboardingQueries:
    @strawberry.field
    def my_onboarding_progress(
        self,
        info,
        include_recommendations: bool = False,
        include_responses: bool = False
    ) -> Optional[OnboardingProgressNode]:
        """Get current user's onboarding progress"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
            return OnboardingProgressNode.from_model(
                progress,
                include_recommendations=include_recommendations,
                include_responses=include_responses
            )
        except:
            return None
    
    @strawberry.field
    def onboarding_wizard_data(self, info) -> Optional[OnboardingWizardData]:
        """Get complete onboarding wizard data"""
        user = info.context.request.user
        if not user.is_authenticated:
            return None
        
        try:
            student = user.student_profile
            progress, created = OnboardingProgress.objects.get_or_create(
                student=student,
                defaults={
                    'current_step': OnboardingStep.PERSONAL_INFO,
                    'tenant': user.tenant
                }
            )
            
            # Get available steps
            available_steps = self._get_available_steps(progress)
            
            # Get skill questions for skill assessment step
            skill_questions = []
            if progress.current_step == OnboardingStep.SKILL_ASSESSMENT:
                skill_questions = [
                    SkillAssessmentQuestionNode.from_model(q)
                    for q in SkillAssessmentQuestion.objects.filter(is_active=True)
                    .order_by('order')[:10]  # Limit to 10 questions
                ]
            
            # Get recommendations if onboarding is complete
            recommendations = []
            if progress.is_completed:
                recommendations = [
                    OnboardingRecommendationNode.from_model(rec)
                    for rec in student.onboarding_recommendations.all()[:10]
                ]
            
            return OnboardingWizardData(
                currentProgress=OnboardingProgressNode.from_model(
                    progress,
                    include_recommendations=True,
                    include_responses=True
                ),
                availableSteps=available_steps,
                skillQuestions=skill_questions,
                recommendations=recommendations
            )
        except:
            return None
    
    @strawberry.field
    def skill_assessment_questions(
        self,
        info,
        skill_category: Optional[str] = None,
        difficulty_level: Optional[str] = None,
        limit: int = 20
    ) -> List[SkillAssessmentQuestionNode]:
        """Get skill assessment questions"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        questions = SkillAssessmentQuestion.objects.filter(is_active=True)
        
        if skill_category:
            questions = questions.filter(skill_category=skill_category)
        
        if difficulty_level:
            questions = questions.filter(difficulty_level=difficulty_level)
        
        questions = questions.order_by('order', 'skill_category')[:limit]
        return [SkillAssessmentQuestionNode.from_model(q) for q in questions]
    
    @strawberry.field
    def my_onboarding_recommendations(
        self,
        info,
        limit: int = 20
    ) -> List[OnboardingRecommendationNode]:
        """Get user's onboarding recommendations"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            student = user.student_profile
            recommendations = student.onboarding_recommendations.order_by('-score')[:limit]
            return [OnboardingRecommendationNode.from_model(rec) for rec in recommendations]
        except:
            return []
    
    @strawberry.field
    def my_skill_assessment_responses(
        self,
        info
    ) -> List[SkillAssessmentResponseNode]:
        """Get user's skill assessment responses"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            student = user.student_profile
            responses = student.skill_assessment_responses.select_related('question').all()
            return [SkillAssessmentResponseNode.from_model(response) for response in responses]
        except:
            return []
    
    @strawberry.field
    def onboarding_step_info(self, info) -> List[OnboardingStepInfo]:
        """Get information about all onboarding steps"""
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            return []
        
        return self._get_available_steps(progress)
    
    def _get_available_steps(self, progress: OnboardingProgress) -> List[OnboardingStepInfo]:
        """Get available onboarding steps with their status"""
        steps = []
        
        step_configs = {
            OnboardingStep.PERSONAL_INFO: {
                'name': 'Personal Information',
                'can_skip': False,
                'estimated_time': 5
            },
            OnboardingStep.EMPLOYMENT_STATUS: {
                'name': 'Employment Status',
                'can_skip': True,
                'estimated_time': 3
            },
            OnboardingStep.CAREER_GOALS: {
                'name': 'Career Goals',
                'can_skip': True,
                'estimated_time': 5
            },
            OnboardingStep.PREFERENCES: {
                'name': 'Preferences & Interests',
                'can_skip': True,
                'estimated_time': 4
            },
            OnboardingStep.SKILL_ASSESSMENT: {
                'name': 'Skill Assessment',
                'can_skip': True,
                'estimated_time': 10
            }
        }
        
        for step_num, config in step_configs.items():
            is_completed = step_num in progress.completed_steps
            is_current = progress.current_step == step_num and not progress.is_completed
            
            steps.append(OnboardingStepInfo(
                stepNumber=step_num,
                stepName=config['name'],
                isCompleted=is_completed,
                isCurrent=is_current,
                canSkip=config['can_skip'],
                estimatedTimeMinutes=config['estimated_time']
            ))
        
        return steps
