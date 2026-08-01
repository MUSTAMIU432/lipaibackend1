import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class RoomType(models.TextChoices):
    PUBLIC = 'public', 'Public'
    PRIVATE = 'private', 'Private'
    COURSE_ONLY = 'course_only', 'Course Only'

class StudyRoom(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("lms_content.Course", on_delete=models.CASCADE, related_name="study_rooms", null=True, blank=True)
    creator = models.ForeignKey("lipaidox_auth.User", on_delete=models.CASCADE, related_name="created_study_rooms")
    
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.PUBLIC)
    max_members = models.IntegerField(default=50)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_study_rooms"
        app_label = "lms_community"

class MemberRole(models.TextChoices):
    OWNER = 'owner', 'Owner'
    MODERATOR = 'moderator', 'Moderator'
    MEMBER = 'member', 'Member'

class StudyRoomMember(models.Model):
    room = models.ForeignKey(StudyRoom, on_delete=models.CASCADE, related_name="members")
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE)
    
    role = models.CharField(max_length=20, choices=MemberRole.choices, default=MemberRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "lms_study_room_members"
        app_label = "lms_community"
        unique_together = ('room', 'student')
