import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class CourseReviewStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'

class CourseReview(TenantAwareModel):
    """
    Student reviews for courses
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    course = models.ForeignKey(
        "lms_content.Course",
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    student = models.ForeignKey(
        "StudentProfile",
        on_delete=models.CASCADE,
        related_name="course_reviews"
    )
    
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    comment = models.TextField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=CourseReviewStatus.choices,
        default=CourseReviewStatus.PENDING
    )
    
    # Moderation
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_course_reviews"
    )
    review_note = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_course_reviews"
        app_label = "lms_identity"
        unique_together = ('course', 'student')
        indexes = [
            models.Index(fields=['course'], name='idx_course_rev_course'),
            models.Index(fields=['student'], name='idx_course_rev_student'),
            models.Index(fields=['status'], name='idx_course_rev_status'),
            models.Index(fields=['rating'], name='idx_course_rev_rating'),
            models.Index(fields=['-created_at'], name='idx_course_rev_created'),
        ]
    
    def __str__(self):
        return f"{self.rating} stars for {self.course.title}"

class InstructorPayoutStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'

class InstructorPayout(TenantAwareModel):
    """
    Instructor payout records
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    instructor = models.ForeignKey(
        "InstructorProfile",
        on_delete=models.CASCADE,
        related_name="payouts"
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    
    status = models.CharField(
        max_length=20,
        choices=InstructorPayoutStatus.choices,
        default=InstructorPayoutStatus.PENDING
    )
    
    # Stripe integration
    stripe_payout_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_transfer_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    payout_date = models.DateTimeField(null=True, blank=True)
    
    # Breakdown
    course_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Notes
    notes = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_instructor_payouts"
        app_label = "lms_identity"
        indexes = [
            models.Index(fields=['instructor'], name='idx_inst_payout_inst'),
            models.Index(fields=['status'], name='idx_inst_payout_status'),
            models.Index(fields=['-created_at'], name='idx_inst_payout_created'),
            models.Index(fields=['period_start'], name='idx_inst_payout_period'),
        ]
    
    def __str__(self):
        return f"{self.amount} {self.currency} payout to {self.instructor.user.username}"

class InstitutionUserRole(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    INSTRUCTOR = 'instructor', 'Instructor'
    TEACHING_ASSISTANT = 'teaching_assistant', 'Teaching Assistant'

class InstitutionUserStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'

class InstitutionUser(TenantAwareModel):
    """
    Institution team members (co-instructors, TAs, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    institution = models.ForeignKey(
        "InstructorProfile",
        on_delete=models.CASCADE,
        related_name="team_members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="institution_memberships"
    )
    
    role = models.CharField(
        max_length=20,
        choices=InstitutionUserRole.choices,
        default=InstitutionUserRole.INSTRUCTOR
    )
    
    status = models.CharField(
        max_length=20,
        choices=InstitutionUserStatus.choices,
        default=InstitutionUserStatus.PENDING
    )
    
    # Permissions
    can_create_courses = models.BooleanField(default=False)
    can_manage_students = models.BooleanField(default=True)
    can_view_analytics = models.BooleanField(default=True)
    can_manage_payouts = models.BooleanField(default=False)
    
    # Invitation
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invites"
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_institution_users"
        app_label = "lms_identity"
        unique_together = ('institution', 'user')
        indexes = [
            models.Index(fields=['institution'], name='idx_inst_user_inst'),
            models.Index(fields=['user'], name='idx_inst_user_user'),
            models.Index(fields=['role'], name='idx_inst_user_role'),
            models.Index(fields=['status'], name='idx_inst_user_status'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.role} at {self.institution.user.username}"

class CourseAssignmentTeam(TenantAwareModel):
    """
    Course assignments for institution team members
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    course = models.ForeignKey(
        "lms_content.Course",
        on_delete=models.CASCADE,
        related_name="team_assignments"
    )
    institution_user = models.ForeignKey(
        InstitutionUser,
        on_delete=models.CASCADE,
        related_name="course_assignments"
    )
    
    role = models.CharField(
        max_length=20,
        choices=InstitutionUserRole.choices,
        default=InstitutionUserRole.INSTRUCTOR
    )
    
    # Permissions for this specific course
    can_edit_content = models.BooleanField(default=True)
    can_manage_students = models.BooleanField(default=True)
    can_view_analytics = models.BooleanField(default=True)
    can_grade_assignments = models.BooleanField(default=True)
    
    # Timestamps
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_course_assignment_teams"
        app_label = "lms_identity"
        unique_together = ('course', 'institution_user')
        indexes = [
            models.Index(fields=['course'], name='idx_course_team_course'),
            models.Index(fields=['institution_user'], name='idx_course_team_user'),
        ]
    
    def __str__(self):
        return f"{self.institution_user.user.username} assigned to {self.course.title}"
