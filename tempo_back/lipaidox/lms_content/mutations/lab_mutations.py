import strawberry
from typing import Optional
from ..schema.lab_types import LabNode
from ..models.lesson import Lesson
from ..models.lab import Lab

@strawberry.type
class LabMutations:
    @strawberry.mutation
    def create_lab(
        self,
        lesson_id: strawberry.ID,
        title: str,
        instructions: str,
        lab_type: str = "code",
        starter_code: Optional[str] = None,
        language: str = "python"
    ) -> LabNode:
        lesson = Lesson.objects.get(id=lesson_id)
        lab = Lab.objects.create(
            lesson=lesson,
            title=title,
            instructions=instructions,
            lab_type=lab_type,
            starter_code=starter_code,
            language=language
        )
        return LabNode.from_model(lab)
