import strawberry
from datetime import datetime
from typing import List
from ..models.qa import Question, Answer
from lipaidox.lms_content.schema.lesson_types import LessonNode
from lipaidox.lms_identity.schema.types import StudentNode

@strawberry.type
class AnswerNode:
    id: strawberry.ID
    content: str
    isAccepted: bool
    upvotes: int
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: Answer):
        return cls(
            id=strawberry.ID(str(instance.id)),
            content=instance.content,
            isAccepted=instance.is_accepted,
            upvotes=instance.upvotes,
            createdAt=instance.created_at,
        )

@strawberry.type
class QuestionNode:
    id: strawberry.ID
    student: StudentNode
    lesson: LessonNode
    title: str
    content: str
    isResolved: bool
    upvotes: int
    answers: List[AnswerNode]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: Question):
        return cls(
            id=strawberry.ID(str(instance.id)),
            student=StudentNode.from_model(instance.student),
            lesson=LessonNode.from_model(instance.lesson),
            title=instance.title,
            content=instance.content,
            isResolved=instance.is_resolved,
            upvotes=instance.upvotes,
            answers=[AnswerNode.from_model(a) for a in instance.answers.all()],
            createdAt=instance.created_at,
        )
