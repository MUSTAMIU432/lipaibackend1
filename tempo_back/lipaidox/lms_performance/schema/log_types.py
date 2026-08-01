import strawberry
from datetime import datetime
from typing import Optional
from ..models.logs import LearningActivityLog
from lipaidox.lms_content.schema.course_types import CourseNode
from lipaidox.lms_content.schema.lesson_types import LessonNode

@strawberry.type
class ActivityLogNode:
    id: strawberry.ID
    action: str
    durationSeconds: int
    loggedAt: datetime
    course: CourseNode
    lesson: Optional[LessonNode]

    @classmethod
    def from_model(cls, instance: LearningActivityLog):
        return cls(
            id=strawberry.ID(str(instance.id)),
            action=instance.action,
            durationSeconds=instance.duration_seconds,
            loggedAt=instance.logged_at,
            course=CourseNode.from_model(instance.course),
            lesson=LessonNode.from_model(instance.lesson) if instance.lesson else None,
        )
