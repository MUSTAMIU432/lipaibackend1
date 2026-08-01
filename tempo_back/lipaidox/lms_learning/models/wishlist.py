import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class Wishlist(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("lms_identity.StudentProfile", on_delete=models.CASCADE, related_name="wishlist")
    course = models.ForeignKey("lms_content.Course", on_delete=models.CASCADE)
    
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_course_wishlists"
        app_label = "lms_learning"
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.user.username} saved {self.course.title}"
