import strawberry
from datetime import datetime
from ..models.notes import Note
from lipaidox.lms_content.schema.lesson_types import LessonNode

@strawberry.type
class NoteNode:
    id: strawberry.ID
    lesson: LessonNode
    content: str
    timestampSeconds: int
    isPrivate: bool
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: Note):
        return cls(
            id=strawberry.ID(str(instance.id)),
            lesson=LessonNode.from_model(instance.lesson),
            content=instance.content,
            timestampSeconds=instance.timestamp_seconds,
            isPrivate=instance.is_private,
            createdAt=instance.created_at,
        )
