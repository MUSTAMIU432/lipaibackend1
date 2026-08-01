import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.onboarding import (
    OnboardingProgress,
    SkillAssessmentQuestion,
    SkillAssessmentResponse,
    OnboardingRecommendation
)

@strawberry.type
class SkillAssessmentQuestionNode:
    id: strawberry.ID
    questionText: str
    questionType: str
    options: List[str]
    skillCategory: str
    difficultyLevel: str
    order: int
    isActive: bool
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: SkillAssessmentQuestion):
        return cls(
            id=strawberry.ID(str(instance.id)),
            questionText=instance.question_text,
            questionType=instance.question_type,
            options=instance.options,
            skillCategory=instance.skill_category,
            difficultyLevel=instance.difficulty_level,
            order=instance.order,
            isActive=instance.is_active,
            createdAt=instance.created_at,
        )

@strawberry.type
class SkillAssessmentResponseNode:
    id: strawberry.ID
    studentId: strawberry.ID
    studentName: str
    questionId: strawberry.ID
    questionText: str
    responseText: Optional[str]
    responseRating: Optional[int]
    responseOptions: List[str]
    timeSpentSeconds: int
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: SkillAssessmentResponse):
        return cls(
            id=strawberry.ID(str(instance.id)),
            studentId=strawberry.ID(str(instance.student.id)),
            studentName=instance.student.user.username,
            questionId=strawberry.ID(str(instance.question.id)),
            questionText=instance.question.question_text,
            responseText=instance.response_text,
            responseRating=instance.response_rating,
            responseOptions=instance.response_options,
            timeSpentSeconds=instance.time_spent_seconds,
            createdAt=instance.created_at,
        )

@strawberry.type
class OnboardingRecommendationNode:
    id: strawberry.ID
    studentId: strawberry.ID
    courseId: strawberry.ID
    courseTitle: str
    courseDescription: Optional[str]
    score: float
    reason: str
    recommendationType: str
    isViewed: bool
    isEnrolled: bool
    enrolledAt: Optional[datetime]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: OnboardingRecommendation):
        return cls(
            id=strawberry.ID(str(instance.id)),
            studentId=strawberry.ID(str(instance.student.id)),
            courseId=strawberry.ID(str(instance.course.id)),
            courseTitle=instance.course.title,
            courseDescription=instance.course.description,
            score=float(instance.score),
            reason=instance.reason,
            recommendationType=instance.recommendation_type,
            isViewed=instance.is_viewed,
            isEnrolled=instance.is_enrolled,
            enrolledAt=instance.enrolled_at,
            createdAt=instance.created_at,
        )

@strawberry.type
class OnboardingProgressNode:
    id: strawberry.ID
    studentId: strawberry.ID
    studentName: str
    currentStep: int
    currentStepName: str
    completedSteps: List[int]
    skippedSteps: List[int]
    
    # Step completion timestamps
    personalInfoCompletedAt: Optional[datetime]
    employmentStatusCompletedAt: Optional[datetime]
    careerGoalsCompletedAt: Optional[datetime]
    preferencesCompletedAt: Optional[datetime]
    skillAssessmentCompletedAt: Optional[datetime]
    
    # Overall completion
    isCompleted: bool
    completedAt: Optional[datetime]
    progressPercentage: int
    
    # Session tracking
    sessionCount: int
    lastSessionAt: Optional[datetime]
    totalTimeSpentMinutes: int
    
    # Timestamps
    createdAt: datetime
    updatedAt: datetime
    
    # Related data
    recommendations: List[OnboardingRecommendationNode]
    skillResponses: List[SkillAssessmentResponseNode]

    @classmethod
    def from_model(cls, instance: OnboardingProgress, include_recommendations=False, include_responses=False):
        recommendations = []
        skill_responses = []
        
        if include_recommendations:
            recommendations = [
                OnboardingRecommendationNode.from_model(rec)
                for rec in instance.student.onboarding_recommendations.all()[:10]
            ]
        
        if include_responses:
            skill_responses = [
                SkillAssessmentResponseNode.from_model(response)
                for response in instance.student.skill_assessment_responses.all()
            ]
        
        return cls(
            id=strawberry.ID(str(instance.id)),
            studentId=strawberry.ID(str(instance.student.id)),
            studentName=instance.student.user.username,
            currentStep=instance.current_step,
            currentStepName=instance.get_current_step_display(),
            completedSteps=instance.completed_steps,
            skippedSteps=instance.skipped_steps,
            personalInfoCompletedAt=instance.personal_info_completed_at,
            employmentStatusCompletedAt=instance.employment_status_completed_at,
            careerGoalsCompletedAt=instance.career_goals_completed_at,
            preferencesCompletedAt=instance.preferences_completed_at,
            skillAssessmentCompletedAt=instance.skill_assessment_completed_at,
            isCompleted=instance.is_completed,
            completedAt=instance.completed_at,
            progressPercentage=instance.get_progress_percentage(),
            sessionCount=instance.session_count,
            lastSessionAt=instance.last_session_at,
            totalTimeSpentMinutes=instance.total_time_spent_minutes,
            createdAt=instance.created_at,
            updatedAt=instance.updated_at,
            recommendations=recommendations,
            skillResponses=skill_responses,
        )

@strawberry.type
class OnboardingStepInfo:
    stepNumber: int
    stepName: str
    isCompleted: bool
    isCurrent: bool
    canSkip: bool
    estimatedTimeMinutes: int

@strawberry.type
class OnboardingWizardData:
    currentProgress: OnboardingProgressNode
    availableSteps: List[OnboardingStepInfo]
    skillQuestions: List[SkillAssessmentQuestionNode]
    recommendations: List[OnboardingRecommendationNode]
