import strawberry
from typing import Optional, List
from ..schema.progress_types import LessonProgressNode
from ..models.progress import LessonProgress

@strawberry.type
class ProgressQueries:
    @strawberry.field
    def my_all_lesson_progress(self, enrollment_id: strawberry.ID) -> List[LessonProgressNode]:
        progress = LessonProgress.objects.filter(enrollment_id=enrollment_id)
        return [LessonProgressNode.from_model(p) for p in progress]

    @strawberry.field
    def lesson_progress_detail(self, enrollment_id: strawberry.ID, lesson_id: strawberry.ID) -> Optional[LessonProgressNode]:
        progress = LessonProgress.objects.filter(enrollment_id=enrollment_id, lesson_id=lesson_id).first()
        return LessonProgressNode.from_model(progress) if progress else None
