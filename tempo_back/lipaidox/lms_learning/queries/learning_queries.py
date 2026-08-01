import strawberry
from typing import List, Optional
from ..schema.types import (
    EnrollmentNode, WishlistNode, LessonProgressNode, LessonNoteNode
)
from ..models import Enrollment, Wishlist, LessonProgress, Note

@strawberry.type
class LearningQueries:
    @strawberry.field
    def my_enrollments(self, info, status: Optional[str] = None) -> List[EnrollmentNode]:
        user = info.context.request.user
        qs = Enrollment.objects.filter(student__user=user)
        if status:
            qs = qs.filter(status=status)
        
        return [EnrollmentNode(
            id=strawberry.ID(str(e.id)),
            courseId=strawberry.ID(str(e.course_id)),
            status=e.status,
            progressPercent=e.progress_percent,
            enrolledAt=e.enrolled_at,
            lastAccessed=e.last_accessed
        ) for e in qs]

    @strawberry.field
    def my_wishlist(self, info) -> List[WishlistNode]:
        user = info.context.request.user
        wishlist = Wishlist.objects.filter(student__user=user)
        return [WishlistNode(
            id=strawberry.ID(str(w.id)),
            courseId=strawberry.ID(str(w.course_id)),
            savedAt=w.saved_at
        ) for w in wishlist]

    @strawberry.field
    def lesson_progress(self, info, lesson_id: strawberry.ID) -> Optional[LessonProgressNode]:
        user = info.context.request.user
        progress = LessonProgress.objects.filter(
            enrollment__student__user=user, 
            lesson_id=lesson_id
        ).first()
        
        if not progress: return None
        return LessonProgressNode(
            id=strawberry.ID(str(progress.id)),
            lessonId=strawberry.ID(str(progress.lesson_id)),
            watchTimeSeconds=progress.watch_time_seconds,
            lastPositionSeconds=progress.last_position_seconds,
            isCompleted=progress.is_completed,
            completedAt=progress.completed_at
        )

    @strawberry.field
    def my_lesson_notes(self, info, lesson_id: strawberry.ID) -> List[LessonNoteNode]:
        user = info.context.request.user
        notes = Note.objects.filter(
            enrollment__student__user=user,
            lesson_id=lesson_id
        )
        return [LessonNoteNode(
            id=strawberry.ID(str(n.id)),
            lessonId=strawberry.ID(str(n.lesson_id)),
            content=n.content,
            timestampSeconds=n.timestamp_seconds,
            createdAt=n.created_at
        ) for n in notes]
