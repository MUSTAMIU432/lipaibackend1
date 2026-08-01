import strawberry
from datetime import datetime
from ..models.enrollment import Enrollment
from lipaidox.lms_content.schema.course_types import CourseNode

@strawberry.type
class EnrollmentNode:
    id: strawberry.ID
    course: CourseNode
    status: str
    progressPercent: int
    enrolledAt: datetime
    completedAt: datetime
    lastAccessed: datetime

    @classmethod
    def from_model(cls, instance: Enrollment):
        return cls(
            id=strawberry.ID(str(instance.id)),
            course=CourseNode.from_model(instance.course),
            status=instance.status,
            progressPercent=instance.progress_percent,
            enrolledAt=instance.enrolled_at,
            completedAt=instance.completed_at,
            lastAccessed=instance.last_accessed,
        )
