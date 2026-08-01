import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class Conversation(TenantAwareModel):
    """
    Educational conversations between students and instructors
    Limited to enrolled students in specific courses
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "lipaidox.Tenant",
        on_delete=models.CASCADE,
        related_name="lms_conversation_instances"
    )
    
    # Course this conversation belongs to
    course = models.ForeignKey(
        "lms_content.Course",
        on_delete=models.CASCADE,
        related_name="conversations"
    )
    
    # Participants - student and instructor
    student = models.ForeignKey(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="conversations"
    )
    instructor = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="instructor_conversations"
    )
    
    # Conversation status
    is_active = models.BooleanField(default=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ended_conversations"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "lms_conversations"
        app_label = "lms_messages"
        unique_together = ('course', 'student', 'instructor')
        indexes = [
            models.Index(fields=['course'], name='idx_conv_course'),
            models.Index(fields=['student'], name='idx_conv_student'),
            models.Index(fields=['instructor'], name='idx_conv_instructor'),
            models.Index(fields=['-last_message_at'], name='idx_conv_last_msg'),
            models.Index(fields=['is_active'], name='idx_conv_active'),
        ]
    
    def __str__(self):
        return f"Conversation: {self.student.user.username} ↔ {self.instructor.username} ({self.course.title})"
    
    def end_conversation(self, ended_by):
        """End the conversation"""
        from django.utils import timezone
        self.is_active = False
        self.ended_at = timezone.now()
        self.ended_by = ended_by
        self.save()
    
    def can_participate(self, user):
        """Check if user can participate in this conversation"""
        # Check if user is the student
        if hasattr(user, 'student_profile') and user.student_profile == self.student:
            return True
        
        # Check if user is the instructor
        if user == self.instructor:
            return True
        
        return False
    
    @classmethod
    def get_or_create_conversation(cls, course, student, instructor):
        """Get or create conversation between student and instructor for course"""
        conversation, created = cls.objects.get_or_create(
            course=course,
            student=student,
            instructor=instructor,
            defaults={
                'tenant': course.tenant,
                'is_active': True
            }
        )
        return conversation, created
    
    @classmethod
    def get_student_conversations(cls, student, active_only=True):
        """Get all conversations for a student"""
        queryset = cls.objects.filter(student=student)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('-last_message_at', '-created_at')
    
    @classmethod
    def get_instructor_conversations(cls, instructor, active_only=True):
        """Get all conversations for an instructor"""
        queryset = cls.objects.filter(instructor=instructor)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('-last_message_at', '-created_at')
