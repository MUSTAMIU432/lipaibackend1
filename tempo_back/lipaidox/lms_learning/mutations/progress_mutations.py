import strawberry
from django.utils import timezone
from ..schema.progress_types import LessonProgressNode
from ..models.progress import LessonProgress

@strawberry.type
class ProgressMutations:
    @strawberry.mutation
    def update_lesson_progress(
        self,
        enrollment_id: strawberry.ID,
        lesson_id: strawberry.ID,
        watch_time_seconds: int,
        is_completed: bool = False
    ) -> LessonProgressNode:
        progress, created = LessonProgress.objects.get_or_create(
            enrollment_id=enrollment_id,
            lesson_id=lesson_id
        )
        
        progress.watch_time_seconds = watch_time_seconds
        if is_completed and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
        
        progress.save()
        return LessonProgressNode.from_model(progress)

    @strawberry.mutation
    def reset_lesson_progress(self, enrollment_id: strawberry.ID, lesson_id: strawberry.ID) -> bool:
        LessonProgress.objects.filter(enrollment_id=enrollment_id, lesson_id=lesson_id).delete()
        return True
