import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class CourseStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    REVIEW = 'review', 'Under Review'
    PUBLISHED = 'published', 'Published'
    ARCHIVED = 'archived', 'Archived'

class CourseLevel(models.TextChoices):
    BEGINNER = 'beginner', 'Beginner'
    INTERMEDIATE = 'intermediate', 'Intermediate'
    ADVANCED = 'advanced', 'Advanced'
    ALL_LEVELS = 'all_levels', 'All Levels'

class Course(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instructor = models.ForeignKey("lms_identity.InstructorProfile", on_delete=models.CASCADE)
    category = models.ForeignKey("lms_content.CourseCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    sub_category = models.ForeignKey("lms_content.CourseCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="sub_courses")
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    subtitle = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    thumbnail_url = models.URLField(max_length=500, null=True, blank=True)
    preview_video_url = models.URLField(max_length=500, null=True, blank=True)
    
    language = models.CharField(max_length=50, default="en")
    level = models.CharField(max_length=20, choices=CourseLevel.choices, default=CourseLevel.ALL_LEVELS)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="USD")
    
    # Stats (Denormalized)
    total_lessons = models.IntegerField(default=0)
    total_sections = models.IntegerField(default=0)
    total_duration_seconds = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=CourseStatus.choices, default=CourseStatus.DRAFT)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lms_courses"
        app_label = "lms_content"

    def __str__(self):
        return self.title
