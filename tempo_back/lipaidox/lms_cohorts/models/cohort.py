import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class CohortStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    UPCOMING = 'upcoming', 'Upcoming'
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'

class Cohort(TenantAwareModel):
    """
    Course cohorts for structured learning groups
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    # Relationships
    course = models.ForeignKey(
        "lms_content.Course",
        on_delete=models.CASCADE,
        related_name="cohorts"
    )
    instructor = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="instructed_cohorts"
    )
    
    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Capacity
    max_students = models.PositiveIntegerField(default=30)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=CohortStatus.choices,
        default=CohortStatus.DRAFT
    )
    
    # Settings
    is_public = models.BooleanField(default=True)  # Students can discover and join
    requires_approval = models.BooleanField(default=False)  # Instructor approval required
    
    # Meeting Information
    default_meeting_url = models.URLField(max_length=500, null=True, blank=True)
    meeting_schedule = models.JSONField(default=dict, blank=True)  # e.g., {"days": ["monday", "wednesday"], "time": "18:00"}
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_cohorts"
        app_label = "lms_cohorts"
        indexes = [
            models.Index(fields=['course'], name='idx_cohort_course'),
            models.Index(fields=['instructor'], name='idx_cohort_instructor'),
            models.Index(fields=['status'], name='idx_cohort_status'),
            models.Index(fields=['start_date'], name='idx_cohort_start'),
            models.Index(fields=['-created_at'], name='idx_cohort_created'),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.course.title}"
    
    @property
    def current_enrollment(self):
        """Get current number of enrolled students"""
        return self.members.count()
    
    @property
    def available_slots(self):
        """Get number of available slots"""
        return max(0, self.max_students - self.current_enrollment)
    
    @property
    def is_full(self):
        """Check if cohort is full"""
        return self.current_enrollment >= self.max_students
    
    @property
    def is_enrollment_open(self):
        """Check if enrollment is open"""
        from django.utils import timezone
        now = timezone.now()
        return (
            self.status in [CohortStatus.UPCOMING, CohortStatus.ACTIVE] and
            now < self.end_date and
            not self.is_full
        )
    
    def can_student_join(self, student):
        """Check if student can join this cohort"""
        # Check if already a member
        if self.members.filter(student=student).exists():
            return False, "Already enrolled"
        
        # Check if cohort is full
        if self.is_full:
            return False, "Cohort is full"
        
        # Check if enrollment period is valid
        if not self.is_enrollment_open:
            return False, "Enrollment is closed"
        
        # Check if student is enrolled in the course
        if not self.course.enrollments.filter(student=student).exists():
            return False, "Must be enrolled in the course first"
        
        return True, "Can join"
    
    def add_student(self, student, approved_by=None):
        """Add a student to the cohort"""
        can_join, reason = self.can_student_join(student)
        if not can_join:
            raise Exception(reason)
        
        if self.requires_approval and not approved_by:
            # Create pending membership
            return CohortMember.objects.create(
                cohort=self,
                student=student,
                status=CohortMemberStatus.PENDING,
                tenant=self.tenant
            )
        else:
            # Direct enrollment
            return CohortMember.objects.create(
                cohort=self,
                student=student,
                status=CohortMemberStatus.ACTIVE,
                approved_by=approved_by,
                tenant=self.tenant
            )
    
    @classmethod
    def get_available_cohorts(cls, student):
        """Get cohorts available for student to join"""
        # Get courses student is enrolled in
        enrolled_courses = student.enrollments.values_list('course', flat=True)
        
        # Get available cohorts from those courses
        available_cohorts = cls.objects.filter(
            course__in=enrolled_courses,
            is_public=True,
            status__in=[CohortStatus.UPCOMING, CohortStatus.ACTIVE]
        ).exclude(
            members__student=student
        )
        
        return available_cohorts

class CohortMemberStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    COMPLETED = 'completed', 'Completed'
    DROPPED = 'dropped', 'Dropped'

class CohortMember(TenantAwareModel):
    """
    Students enrolled in cohorts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="members"
    )
    student = models.ForeignKey(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="cohort_memberships"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=CohortMemberStatus.choices,
        default=CohortMemberStatus.ACTIVE
    )
    
    # Approval
    approved_by = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_cohort_members"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Progress
    completion_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_cohort_members"
        app_label = "lms_cohorts"
        unique_together = ('cohort', 'student')
        indexes = [
            models.Index(fields=['cohort'], name='idx_member_cohort'),
            models.Index(fields=['student'], name='idx_member_student'),
            models.Index(fields=['status'], name='idx_member_status'),
            models.Index(fields=['-joined_at'], name='idx_member_joined'),
        ]
    
    def __str__(self):
        return f"{self.student.user.username} in {self.cohort.name}"
    
    def approve(self, approved_by):
        """Approve a pending membership"""
        if self.status != CohortMemberStatus.PENDING:
            raise Exception("Only pending memberships can be approved")
        
        from django.utils import timezone
        self.status = CohortMemberStatus.ACTIVE
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save()
    
    def drop(self):
        """Drop student from cohort"""
        self.status = CohortMemberStatus.DROPPED
        self.save()

class CohortSession(TenantAwareModel):
    """
    Scheduled sessions for cohorts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    # Relationship
    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="sessions"
    )
    
    # Schedule
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    
    # Meeting URLs
    meet_url = models.URLField(max_length=500, null=True, blank=True)
    recording_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Status
    is_cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(null=True, blank=True)
    
    # Attendance tracking
    attended_by = models.ManyToManyField(
        "lms_identity.StudentProfile",
        related_name="attended_sessions",
        blank=True
    )
    
    # Instructor
    instructor = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="conducted_sessions"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_cohort_sessions"
        app_label = "lms_cohorts"
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['cohort'], name='idx_session_cohort'),
            models.Index(fields=['instructor'], name='idx_session_instructor'),
            models.Index(fields=['scheduled_at'], name='idx_session_scheduled'),
            models.Index(fields=['is_cancelled'], name='idx_session_cancelled'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.cohort.name}"
    
    @property
    def is_past(self):
        """Check if session is in the past"""
        from django.utils import timezone
        return self.scheduled_at < timezone.now()
    
    @property
    def is_upcoming(self):
        """Check if session is upcoming"""
        from django.utils import timezone
        return self.scheduled_at > timezone.now() and not self.is_cancelled
    
    def mark_attendance(self, student):
        """Mark student as attended"""
        if not self.cohort.members.filter(student=student, status=CohortMemberStatus.ACTIVE).exists():
            raise Exception("Student is not an active member of this cohort")
        
        self.attended_by.add(student)
    
    def cancel(self, reason=None):
        """Cancel the session"""
        self.is_cancelled = True
        self.cancellation_reason = reason
        self.save()
