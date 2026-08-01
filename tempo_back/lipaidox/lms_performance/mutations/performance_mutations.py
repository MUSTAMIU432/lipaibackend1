import strawberry
from django.utils import timezone
from typing import Optional, List
from ..schema.log_types import ActivityLogNode
from ..schema.submission_types import QuizAttemptNode, AssignmentSubmissionNode
from ..models.logs import LearningActivityLog, ActivityAction
from ..models.submissions import QuizAttempt, AssignmentSubmission
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class PerformanceMutations:
    @strawberry.mutation
    def log_learning_activity(
        self,
        info,
        course_id: strawberry.ID,
        lesson_id: Optional[strawberry.ID],
        action: str,
        duration_seconds: int = 0
    ) -> ActivityLogNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        log = LearningActivityLog.objects.create(
            student=student,
            course_id=course_id,
            lesson_id=lesson_id,
            action=action,
            duration_seconds=duration_seconds,
            tenant=user.tenant
        )
        return ActivityLogNode.from_model(log)

    @strawberry.mutation
    def submit_quiz_attempt(
        self,
        info,
        course_id: strawberry.ID,
        lesson_id: strawberry.ID,
        score: float,
        passed: bool,
        answers: List[str] # Simplified for now
    ) -> QuizAttemptNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        attempt = QuizAttempt.objects.create(
            student=student,
            course_id=course_id,
            lesson_id=lesson_id,
            score=score,
            passed=passed,
            answers=answers,
            tenant=user.tenant
        )
        return QuizAttemptNode.from_model(attempt)

    @strawberry.mutation
    def submit_assignment(
        self,
        info,
        lesson_id: strawberry.ID,
        file_url: Optional[str] = None,
        text_content: Optional[str] = None
    ) -> AssignmentSubmissionNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        submission = AssignmentSubmission.objects.create(
            student=student,
            lesson_id=lesson_id,
            file_url=file_url,
            text_content=text_content,
            tenant=user.tenant
        )
        return AssignmentSubmissionNode.from_model(submission)
