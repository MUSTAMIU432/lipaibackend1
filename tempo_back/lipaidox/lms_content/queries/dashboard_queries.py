import strawberry
from typing import List, Optional
from ..schema.course_types import CourseNode
from ..models.learning_path import LearningPath
from ..models.announcement import CourseAnnouncement
from ..models.recommendation import Recommendation

@strawberry.type
class LearningPathNode:
    id: strawberry.ID
    title: str
    description: str
    skills: List[str]
    estimatedDurationWeeks: int

@strawberry.type
class AnnouncementNode:
    id: strawberry.ID
    title: str
    body: str
    createdAt: str

@strawberry.type
class RecommendationNode:
    id: strawberry.ID
    course: CourseNode
    priority: str
    reasons: List[str]

@strawberry.type
class DashboardQueries:
    @strawberry.field
    def my_learning_paths(self, info) -> List[LearningPathNode]:
        paths = LearningPath.objects.filter(is_active=True)
        return [LearningPathNode(
            id=p.id, 
            title=p.title, 
            description=p.description, 
            skills=p.skills, 
            estimatedDurationWeeks=p.estimated_duration_weeks
        ) for p in paths]

    @strawberry.field
    def my_recommendations(self, info) -> List[RecommendationNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        recs = Recommendation.objects.filter(student__user=user)
        return [RecommendationNode(
            id=r.id,
            course=CourseNode.from_model(r.course),
            priority=r.priority,
            reasons=r.reasons
        ) for r in recs]

    @strawberry.field
    def dashboard_announcements(self, info) -> List[AnnouncementNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        # Get announcements for instructor courses or enrolled courses
        announcements = CourseAnnouncement.objects.all()[:10] # Simplified logic
        return [AnnouncementNode(
            id=a.id,
            title=a.title,
            body=a.body,
            createdAt=a.created_at.isoformat()
        ) for a in announcements]
