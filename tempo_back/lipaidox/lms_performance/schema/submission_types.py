import strawberry
from datetime import datetime
from typing import List, Optional
from ..models.submissions import QuizAttempt, AssignmentSubmission
from lipaidox.lms_content.schema.lesson_types import LessonNode

@strawberry.type
class QuizAttemptNode:
    id: strawberry.ID
    score: float
    passed: bool
    attemptedAt: datetime
    lesson: Optional[LessonNode]

    @classmethod
    def from_model(cls, instance: QuizAttempt):
        return cls(
            id=strawberry.ID(str(instance.id)),
            score=float(instance.score),
            passed=instance.passed,
            attemptedAt=instance.attempted_at,
            lesson=LessonNode.from_model(instance.lesson) if instance.lesson else None,
        )

@strawberry.type
class AssignmentSubmissionNode:
    id: strawberry.ID
    fileUrl: Optional[str]
    textContent: Optional[str]
    score: Optional[float]
    feedback: Optional[str]
    submittedAt: datetime
    gradedAt: Optional[datetime]
    lesson: LessonNode

    @classmethod
    def from_model(cls, instance: AssignmentSubmission):
        return cls(
            id=strawberry.ID(str(instance.id)),
            fileUrl=instance.file_url,
            textContent=instance.text_content,
            score=float(instance.score) if instance.score is not None else None,
            feedback=instance.feedback,
            submittedAt=instance.submitted_at,
            gradedAt=instance.graded_at,
            lesson=LessonNode.from_model(instance.lesson),
        )
