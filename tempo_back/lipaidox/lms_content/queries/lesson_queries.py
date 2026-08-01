import strawberry
from typing import Optional, List
from ..schema.lesson_types import LessonNode
from ..schema.resource_types import ResourceNode
from ..models.lesson import Lesson
from ..models.resource import Resource

@strawberry.type
class LessonQueries:
    @strawberry.field
    def lesson_by_id(self, id: strawberry.ID) -> Optional[LessonNode]:
        lesson = Lesson.objects.filter(id=id).first()
        return LessonNode.from_model(lesson) if lesson else None

    @strawberry.field
    def lesson_resources(self, lesson_id: strawberry.ID) -> List[ResourceNode]:
        resources = Resource.objects.filter(lesson_id=lesson_id)
        return [ResourceNode.from_model(r) for r in resources]
