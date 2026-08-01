import strawberry
from datetime import datetime
from ..models.progress import LessonProgress
from lipaidox.lms_content.schema.lesson_types import LessonNode

@strawberry.type
class LessonProgressNode:
    id: strawberry.ID
    lesson: LessonNode
    watchTimeSeconds: int
    isCompleted: bool
    completedAt: datetime
    lastAccessed: datetime

    @classmethod
    def from_model(cls, instance: LessonProgress):
        return cls(
            id=strawberry.ID(str(instance.id)),
            lesson=LessonNode.from_model(instance.lesson),
            watchTimeSeconds=instance.watch_time_seconds,
            isCompleted=instance.is_completed,
            completedAt=instance.completed_at,
            lastAccessed=instance.last_accessed,
        )
