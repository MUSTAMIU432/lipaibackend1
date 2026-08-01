import strawberry
from typing import List, Optional
from ..schema.log_types import ActivityLogNode
from ..schema.submission_types import QuizAttemptNode, AssignmentSubmissionNode
from ..schema.stats_types import PerformanceStatsNode
from ..models.logs import LearningActivityLog
from ..models.submissions import QuizAttempt, AssignmentSubmission

@strawberry.type
class PerformanceQueries:
    @strawberry.field
    def learning_stats(self, info) -> PerformanceStatsNode:
        # Placeholder for complex analytics logic
        return PerformanceStatsNode(
            totalHours=25.5, 
            completionRate=0.82, 
            currentStreak=12,
            totalAssessments=5,
            averageScore=88.5
        )

    @strawberry.field
    def my_activity_logs(self, info) -> List[ActivityLogNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [ActivityLogNode.from_model(l) for l in LearningActivityLog.objects.filter(student__user=user)]

    @strawberry.field
    def my_quiz_attempts(self, info) -> List[QuizAttemptNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [QuizAttemptNode.from_model(q) for q in QuizAttempt.objects.filter(student__user=user)]

    @strawberry.field
    def my_assignment_submissions(self, info) -> List[AssignmentSubmissionNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [AssignmentSubmissionNode.from_model(a) for a in AssignmentSubmission.objects.filter(student__user=user)]
