import strawberry
from datetime import datetime
from ..models import Enrollment, Wishlist, LessonProgress, Note
from lipaidox.lms_identity.models import StudentProfile

@strawberry.type
class LearningMutations:
    @strawberry.mutation
    def toggle_wishlist(self, info, course_id: strawberry.ID) -> bool:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        
        wish, created = Wishlist.objects.get_or_create(student=student, course_id=course_id)
        if not created:
            wish.delete()
            return False # Removed
        return True # Added

    @strawberry.mutation
    def update_lesson_progress(
        self, 
        info, 
        lesson_id: strawberry.ID, 
        watch_time: int, 
        last_position: int,
        is_completed: bool = False
    ) -> bool:
        user = info.context.request.user
        # Find enrollment for the course this lesson belongs to
        # (Simplified for now - assumes we have an active enrollment)
        progress = LessonProgress.objects.filter(
            enrollment__student__user=user, 
            lesson_id=lesson_id
        ).first()

        if not progress: return False
        
        progress.watch_time_seconds = watch_time
        progress.last_position_seconds = last_position
        if is_completed and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = datetime.now()
        
        progress.save()
        return True

    @strawberry.mutation
    def create_lesson_note(
        self, 
        info, 
        lesson_id: strawberry.ID, 
        content: str, 
        timestamp: int = 0
    ) -> bool:
        user = info.context.request.user
        enrollment = Enrollment.objects.filter(
            student__user=user, 
            students_enrolled__lessons__id=lesson_id # Requires reverse relation check
        ).first()
        # Simplified:
        enrollment = Enrollment.objects.filter(student__user=user).first() # Fallback

        Note.objects.create(
            enrollment=enrollment,
            lesson_id=lesson_id,
            content=content,
            timestamp_seconds=timestamp
        )
        return True
