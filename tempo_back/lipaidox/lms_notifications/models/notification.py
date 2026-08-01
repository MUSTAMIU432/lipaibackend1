import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class NotificationType(models.TextChoices):
    # Course notifications
    COURSE_ENROLLED = 'course_enrolled', 'Course Enrolled'
    COURSE_COMPLETED = 'course_completed', 'Course Completed'
    LESSON_COMPLETED = 'lesson_completed', 'Lesson Completed'
    ASSIGNMENT_DUE = 'assignment_due', 'Assignment Due'
    ASSIGNMENT_SUBMITTED = 'assignment_submitted', 'Assignment Submitted'
    ASSIGNMENT_GRADED = 'assignment_graded', 'Assignment Graded'
    QUIZ_COMPLETED = 'quiz_completed', 'Quiz Completed'
    QUIZ_PASSED = 'quiz_passed', 'Quiz Passed'
    QUIZ_FAILED = 'quiz_failed', 'Quiz Failed'
    
    # Community notifications
    STUDY_ROOM_INVITED = 'study_room_invited', 'Study Room Invited'
    STUDY_ROOM_MESSAGE = 'study_room_message', 'Study Room Message'
    ACCOUNTABILITY_CHECK_IN = 'accountability_check_in', 'Accountability Check-In'
    
    # Certification notifications
    CERTIFICATION_EARNED = 'certification_earned', 'Certification Earned'
    SKILL_BADGE_EARNED = 'skill_badge_earned', 'Skill Badge Earned'
    
    # Performance notifications
    STREAK_ACHIEVED = 'streak_achieved', 'Streak Achieved'
    WEEKLY_PROGRESS = 'weekly_progress', 'Weekly Progress'
    
    # Career notifications
    JOB_APPLICATION_VIEWED = 'job_application_viewed', 'Job Application Viewed'
    JOB_APPLICATION_SHORTLISTED = 'job_application_shortlisted', 'Job Application Shortlisted'
    
    # System notifications
    SYSTEM_ANNOUNCEMENT = 'system_announcement', 'System Announcement'
    PAYMENT_CONFIRMED = 'payment_confirmed', 'Payment Confirmed'
    SUBSCRIPTION_RENEWAL = 'subscription_renewal', 'Subscription Renewal'

class LmsNotification(TenantAwareModel):
    """
    LMS Notifications for educational events and updates
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Recipient
    user = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="lms_notifications"
    )
    
    # Content
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM_ANNOUNCEMENT
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    
    # Action
    action_url = models.URLField(max_length=500, null=True, blank=True)
    action_text = models.CharField(max_length=100, null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # Additional data like course_id, etc.
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_notifications"
        app_label = "lms_notifications"
        indexes = [
            models.Index(fields=['user'], name='idx_notif_user'),
            models.Index(fields=['-created_at'], name='idx_notif_created'),
            models.Index(fields=['is_read'], name='idx_notif_read'),
            models.Index(fields=['notification_type'], name='idx_notif_type'),
        ]
    
    def __str__(self):
        return f"Notification: {self.title} for {self.user.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    @classmethod
    def create_notification(
        cls,
        user,
        notification_type,
        title,
        body,
        action_url=None,
        action_text=None,
        metadata=None,
        tenant=None
    ):
        """Create a new notification"""
        if tenant is None:
            tenant = user.tenant
            
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata or {},
            tenant=tenant
        )
    
    @classmethod
    def get_user_notifications(cls, user, unread_only=False, limit=20):
        """Get notifications for user"""
        queryset = cls.objects.filter(user=user)
        if unread_only:
            queryset = queryset.filter(is_read=False)
        return queryset.order_by('-created_at')[:limit]
    
    @classmethod
    def get_unread_count(cls, user):
        """Get unread notification count for user"""
        return cls.objects.filter(user=user, is_read=False).count()
    
    @classmethod
    def mark_all_read(cls, user):
        """Mark all notifications as read for user"""
        from django.utils import timezone
        unread_notifications = cls.objects.filter(user=user, is_read=False)
        count = unread_notifications.count()
        unread_notifications.update(is_read=True, read_at=timezone.now())
        return count
    
    @classmethod
    def create_course_notification(cls, user, notification_type, course, title, body, **kwargs):
        """Create a course-related notification"""
        metadata = kwargs.get('metadata', {})
        metadata.update({
            'course_id': str(course.id),
            'course_title': course.title
        })
        
        action_url = kwargs.get('action_url', f'/courses/{course.id}')
        
        return cls.create_notification(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            action_url=action_url,
            action_text=kwargs.get('action_text', 'View Course'),
            metadata=metadata
        )
    
    @classmethod
    def create_assignment_notification(cls, user, notification_type, assignment, title, body, **kwargs):
        """Create an assignment-related notification"""
        metadata = kwargs.get('metadata', {})
        metadata.update({
            'assignment_id': str(assignment.id),
            'assignment_title': assignment.title,
            'course_id': str(assignment.course.id),
            'course_title': assignment.course.title
        })
        
        action_url = kwargs.get('action_url', f'/courses/{assignment.course.id}/assignments/{assignment.id}')
        
        return cls.create_notification(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            action_url=action_url,
            action_text=kwargs.get('action_text', 'View Assignment'),
            metadata=metadata
        )
