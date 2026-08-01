import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class OnboardingStep(models.TextChoices):
    PERSONAL_INFO = 1, 'Personal Information'
    EMPLOYMENT_STATUS = 2, 'Employment Status'
    CAREER_GOALS = 3, 'Career Goals'
    PREFERENCES = 4, 'Preferences & Interests'
    SKILL_ASSESSMENT = 5, 'Skill Assessment'
    COMPLETED = 6, 'Completed'

class OnboardingProgress(TenantAwareModel):
    """
    Track detailed onboarding progress for each student
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    student = models.OneToOneField(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="onboarding_progress"
    )
    
    # Current step tracking
    current_step = models.IntegerField(
        choices=OnboardingStep.choices,
        default=OnboardingStep.PERSONAL_INFO
    )
    completed_steps = models.JSONField(default=list, blank=True)  # List of completed step numbers
    
    # Step completion timestamps
    personal_info_completed_at = models.DateTimeField(null=True, blank=True)
    employment_status_completed_at = models.DateTimeField(null=True, blank=True)
    career_goals_completed_at = models.DateTimeField(null=True, blank=True)
    preferences_completed_at = models.DateTimeField(null=True, blank=True)
    skill_assessment_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Overall completion
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Session tracking
    session_count = models.IntegerField(default=0)
    last_session_at = models.DateTimeField(null=True, blank=True)
    total_time_spent_minutes = models.IntegerField(default=0)
    
    # Skip tracking
    skipped_steps = models.JSONField(default=list, blank=True)  # List of skipped step numbers
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_onboarding_progress"
        app_label = "lms_onboarding"
        indexes = [
            models.Index(fields=['student'], name='idx_onboard_student'),
            models.Index(fields=['current_step'], name='idx_onboard_step'),
            models.Index(fields=['is_completed'], name='idx_onboard_completed'),
            models.Index(fields=['-created_at'], name='idx_onboard_created'),
        ]
    
    def __str__(self):
        return f"Onboarding for {self.student.user.username} - Step {self.current_step}"
    
    def complete_step(self, step_number, time_spent_minutes=0):
        """Mark a step as completed"""
        if step_number not in self.completed_steps:
            self.completed_steps.append(step_number)
            
            # Set completion timestamp
            from django.utils import timezone
            now = timezone.now()
            
            if step_number == OnboardingStep.PERSONAL_INFO:
                self.personal_info_completed_at = now
            elif step_number == OnboardingStep.EMPLOYMENT_STATUS:
                self.employment_status_completed_at = now
            elif step_number == OnboardingStep.CAREER_GOALS:
                self.career_goals_completed_at = now
            elif step_number == OnboardingStep.PREFERENCES:
                self.preferences_completed_at = now
            elif step_number == OnboardingStep.SKILL_ASSESSMENT:
                self.skill_assessment_completed_at = now
            
            # Update total time spent
            self.total_time_spent_minutes += time_spent_minutes
            
            # Move to next step if not completed
            if not self.is_completed:
                next_step = step_number + 1
                if next_step <= OnboardingStep.SKILL_ASSESSMENT:
                    self.current_step = next_step
                else:
                    # Complete onboarding
                    self.complete_onboarding()
            
            self.save()
    
    def skip_step(self, step_number):
        """Skip a step"""
        if step_number not in self.skipped_steps:
            self.skipped_steps.append(step_number)
            
            # Move to next step
            next_step = step_number + 1
            if next_step <= OnboardingStep.SKILL_ASSESSMENT:
                self.current_step = next_step
            else:
                self.complete_onboarding()
            
            self.save()
    
    def complete_onboarding(self):
        """Complete the entire onboarding process"""
        from django.utils import timezone
        self.is_completed = True
        self.completed_at = timezone.now()
        self.current_step = OnboardingStep.COMPLETED
        
        # Update student profile
        self.student.onboarding_completed = True
        self.student.onboarding_completed_at = timezone.now()
        self.student.onboarding_step = OnboardingStep.COMPLETED
        self.student.save()
        
        self.save()
    
    def get_progress_percentage(self):
        """Get progress percentage"""
        total_steps = 5  # Personal info through skill assessment
        completed_count = len(self.completed_steps)
        return int((completed_count / total_steps) * 100)
    
    def get_next_step(self):
        """Get the next step to complete"""
        if self.is_completed:
            return None
        
        for step_num in range(1, 6):  # Steps 1-5
            if step_num not in self.completed_steps and step_num not in self.skipped_steps:
                return step_num
        
        return None

class SkillAssessmentQuestion(TenantAwareModel):
    """
    Questions for skill assessment during onboarding
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=[
            ('multiple_choice', 'Multiple Choice'),
            ('rating', 'Rating Scale'),
            ('text', 'Text Input'),
            ('checkbox', 'Checkbox'),
        ],
        default='multiple_choice'
    )
    
    # Question options for multiple choice
    options = models.JSONField(default=list, blank=True)
    
    # Categorization
    skill_category = models.CharField(max_length=100)  # e.g., 'programming', 'design', 'business'
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ],
        default='beginner'
    )
    
    # Metadata
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_skill_assessment_questions"
        app_label = "lms_onboarding"
        ordering = ['order', 'skill_category', 'difficulty_level']
        indexes = [
            models.Index(fields=['skill_category'], name='idx_question_category'),
            models.Index(fields=['difficulty_level'], name='idx_question_difficulty'),
            models.Index(fields=['is_active'], name='idx_question_active'),
        ]
    
    def __str__(self):
        return f"{self.skill_category} - {self.question_text[:50]}..."

class SkillAssessmentResponse(TenantAwareModel):
    """
    Student responses to skill assessment questions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    student = models.ForeignKey(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="skill_assessment_responses"
    )
    
    question = models.ForeignKey(
        SkillAssessmentQuestion,
        on_delete=models.CASCADE,
        related_name="responses"
    )
    
    # Response data
    response_text = models.TextField(null=True, blank=True)
    response_rating = models.IntegerField(null=True, blank=True)  # For rating questions
    response_options = models.JSONField(default=list, blank=True)  # For multiple choice/checkbox
    
    # Time tracking
    time_spent_seconds = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_skill_assessment_responses"
        app_label = "lms_onboarding"
        unique_together = ('student', 'question')
        indexes = [
            models.Index(fields=['student'], name='idx_response_student'),
            models.Index(fields=['question'], name='idx_response_question'),
        ]
    
    def __str__(self):
        return f"Response by {self.student.user.username} to {self.question.id[:8]}..."

class OnboardingRecommendation(TenantAwareModel):
    """
    Course recommendations based on onboarding responses
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    student = models.ForeignKey(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="onboarding_recommendations"
    )
    
    course = models.ForeignKey(
        "lms_content.Course",
        on_delete=models.CASCADE,
        related_name="onboarding_recommendations"
    )
    
    # Recommendation metadata
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)  # 0-100
    reason = models.TextField()  # Why this course is recommended
    
    # Categorization
    recommendation_type = models.CharField(
        max_length=20,
        choices=[
            ('skill_match', 'Skill Match'),
            ('career_goal', 'Career Goal'),
            ('interest', 'Interest Based'),
            ('popular', 'Popular'),
        ],
        default='skill_match'
    )
    
    # Status
    is_viewed = models.BooleanField(default=False)
    is_enrolled = models.BooleanField(default=False)
    enrolled_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_onboarding_recommendations"
        app_label = "lms_onboarding"
        indexes = [
            models.Index(fields=['student'], name='idx_rec_student'),
            models.Index(fields=['course'], name='idx_rec_course'),
            models.Index(fields=['-score'], name='idx_rec_score'),
            models.Index(fields=['recommendation_type'], name='idx_rec_type'),
        ]
    
    def __str__(self):
        return f"Recommendation: {self.course.title} for {self.student.user.username}"
    
    def mark_enrolled(self):
        """Mark as enrolled"""
        from django.utils import timezone
        self.is_enrolled = True
        self.enrolled_at = timezone.now()
        self.save()
