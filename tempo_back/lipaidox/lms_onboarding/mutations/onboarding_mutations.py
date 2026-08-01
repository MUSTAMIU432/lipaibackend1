import strawberry
from typing import Optional
from ..schema.onboarding_types import (
    OnboardingProgressNode,
    SkillAssessmentResponseNode,
    OnboardingRecommendationNode,
    OnboardingWizardData,
    OnboardingStepInfo
)
from ..models.onboarding import (
    OnboardingProgress,
    OnboardingStep,
    SkillAssessmentQuestion,
    SkillAssessmentResponse,
    OnboardingRecommendation
)

@strawberry.type
class OnboardingMutations:
    @strawberry.mutation
    def start_onboarding(self, info) -> OnboardingProgressNode:
        """Start or resume onboarding for current student"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
        except:
            raise Exception("Student profile not found")
        
        # Get or create onboarding progress
        progress, created = OnboardingProgress.objects.get_or_create(
            student=student,
            defaults={
                'current_step': OnboardingStep.PERSONAL_INFO,
                'tenant': user.tenant
            }
        )
        
        # Update session tracking
        from django.utils import timezone
        progress.session_count += 1
        progress.last_session_at = timezone.now()
        progress.save()
        
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def update_personal_info(
        self,
        info,
        headline: Optional[str] = None,
        bio: Optional[str] = None,
        location: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        linkedin: Optional[str] = None,
        github: Optional[str] = None,
        portfolio: Optional[str] = None,
        time_spent_minutes: int = 0
    ) -> OnboardingProgressNode:
        """Update personal information step"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        # Update student profile
        if headline is not None:
            student.headline = headline
        if bio is not None:
            student.bio = bio
        if location is not None:
            student.location = location
        if phone is not None:
            student.phone = phone
        if website is not None:
            student.website = website
        if linkedin is not None:
            student.linkedin = linkedin
        if github is not None:
            student.github = github
        if portfolio is not None:
            student.portfolio = portfolio
        
        student.save()
        
        # Complete step
        progress.complete_step(OnboardingStep.PERSONAL_INFO, time_spent_minutes)
        
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def update_employment_status(
        self,
        info,
        employment_status: str,
        years_of_experience: int,
        career_goals: Optional[list[str]] = None,
        desired_roles: Optional[list[str]] = None,
        remote_preference: bool = False,
        willing_to_relocate: bool = False,
        time_spent_minutes: int = 0
    ) -> OnboardingProgressNode:
        """Update employment status step"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        # Update student profile
        student.employment_status = employment_status
        student.years_of_experience = years_of_experience
        student.career_goals = career_goals or []
        student.desired_roles = desired_roles or []
        student.remote_preference = remote_preference
        student.willing_to_relocate = willing_to_relocate
        
        student.save()
        
        # Complete step
        progress.complete_step(OnboardingStep.EMPLOYMENT_STATUS, time_spent_minutes)
        
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def update_career_goals(
        self,
        info,
        career_goals: list[str],
        desired_roles: list[str],
        target_salary: Optional[int] = None,
        timeline_months: Optional[int] = None,
        time_spent_minutes: int = 0
    ) -> OnboardingProgressNode:
        """Update career goals step"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        # Update student profile
        student.career_goals = career_goals
        student.desired_roles = desired_roles
        
        # Store additional goals in learning preferences
        learning_prefs = student.learning_preferences or {}
        if target_salary:
            learning_prefs['target_salary'] = target_salary
        if timeline_months:
            learning_prefs['timeline_months'] = timeline_months
        student.learning_preferences = learning_prefs
        
        student.save()
        
        # Complete step
        progress.complete_step(OnboardingStep.CAREER_GOALS, time_spent_minutes)
        
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def update_preferences(
        self,
        info,
        preferred_categories: list[str],
        interests: list[str],
        learning_style: Optional[str] = None,
        time_commitment_hours: Optional[int] = None,
        time_spent_minutes: int = 0
    ) -> OnboardingProgressNode:
        """Update preferences and interests step"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        # Store preferences in learning preferences
        learning_prefs = student.learning_preferences or {}
        learning_prefs.update({
            'preferred_categories': preferred_categories,
            'interests': interests,
            'learning_style': learning_style,
            'time_commitment_hours': time_commitment_hours
        })
        student.learning_preferences = learning_prefs
        
        student.save()
        
        # Complete step
        progress.complete_step(OnboardingStep.PREFERENCES, time_spent_minutes)
        
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def submit_skill_assessment(
        self,
        info,
        responses_json_str: str,  # JSON string instead of list[dict]
        time_spent_minutes: int = 0
    ) -> OnboardingProgressNode:
        """Submit skill assessment responses"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        # Parse JSON string
        import json
        try:
            responses = json.loads(responses_json_str)
        except json.JSONDecodeError:
            raise Exception("Invalid responses JSON")
        
        # Process responses
        for response_data in responses:
            question_id = response_data.get('question_id')
            response_value = response_data.get('response_data')
            time_spent_seconds = response_data.get('time_spent_seconds', 0)
            
            try:
                question = SkillAssessmentQuestion.objects.get(id=question_id)
                
                # Create or update response
                response, created = SkillAssessmentResponse.objects.update_or_create(
                    student=student,
                    question=question,
                    defaults={
                        'response_text': response_value.get('text') if isinstance(response_value, dict) else str(response_value),
                        'response_rating': response_value.get('rating') if isinstance(response_value, dict) else None,
                        'response_options': response_value.get('options') if isinstance(response_value, dict) else [],
                        'time_spent_seconds': time_spent_seconds,
                        'tenant': user.tenant
                    }
                )
                
            except SkillAssessmentQuestion.DoesNotExist:
                continue  # Skip invalid questions
        
        # Complete step
        progress.complete_step(OnboardingStep.SKILL_ASSESSMENT, time_spent_minutes)
        
        # Generate recommendations based on responses
        self._generate_recommendations(student)
        
        return OnboardingProgressNode.from_model(progress, include_recommendations=True)
    
    @strawberry.mutation
    def skip_onboarding_step(
        self,
        info,
        step_number: int
    ) -> OnboardingProgressNode:
        """Skip an onboarding step"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        progress.skip_step(step_number)
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def complete_onboarding(
        self,
        info
    ) -> OnboardingProgressNode:
        """Manually complete onboarding"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            progress = student.onboarding_progress
        except:
            raise Exception("Onboarding not started")
        
        progress.complete_onboarding()
        return OnboardingProgressNode.from_model(progress)
    
    @strawberry.mutation
    def mark_recommendation_viewed(
        self,
        info,
        recommendation_id: strawberry.ID
    ) -> OnboardingRecommendationNode:
        """Mark a recommendation as viewed"""
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        try:
            student = user.student_profile
            recommendation = OnboardingRecommendation.objects.get(
                id=recommendation_id,
                student=student
            )
        except (StudentProfile.DoesNotExist, OnboardingRecommendation.DoesNotExist):
            raise Exception("Recommendation not found")
        
        recommendation.is_viewed = True
        recommendation.save()
        
        return OnboardingRecommendationNode.from_model(recommendation)
    
    def _generate_recommendations(self, student):
        """Generate course recommendations based on onboarding responses"""
        from lipaidox.lms_content.models import Course
        
        # Get student's interests and goals
        learning_prefs = student.learning_preferences or {}
        preferred_categories = learning_prefs.get('preferred_categories', [])
        career_goals = student.career_goals
        desired_roles = student.desired_roles
        
        # Get skill assessment responses
        skill_responses = student.skill_assessment_responses.all()
        skill_categories = set()
        
        for response in skill_responses:
            skill_categories.add(response.question.skill_category)
        
        # Find matching courses
        courses = Course.objects.filter(
            is_active=True,
            category__name__in=preferred_categories
        ) | Course.objects.filter(
            is_active=True,
            tags__name__in=list(career_goals) + list(desired_roles)
        )
        
        courses = courses.distinct()[:10]  # Limit to top 10
        
        # Create recommendations
        for course in courses:
            # Calculate score based on multiple factors
            score = 0.0
            reasons = []
            
            # Category match
            if course.category.name in preferred_categories:
                score += 30
                reasons.append(f"Matches your interest in {course.category.name}")
            
            # Skill match
            if any(cat in course.description.lower() for cat in skill_categories):
                score += 25
                reasons.append("Aligns with your skill assessment")
            
            # Career goal match
            if any(goal in course.title.lower() or goal in course.description.lower() 
                   for goal in career_goals + desired_roles):
                score += 25
                reasons.append("Supports your career goals")
            
            # Popularity bonus
            if course.enrollments.count() > 100:
                score += 10
                reasons.append("Popular among students")
            
            # Ensure minimum score
            score = max(score, 20.0)
            
            # Create recommendation
            OnboardingRecommendation.objects.get_or_create(
                student=student,
                course=course,
                defaults={
                    'score': score,
                    'reason': '; '.join(reasons),
                    'recommendation_type': 'interest_based',
                    'tenant': student.tenant
                }
            )
