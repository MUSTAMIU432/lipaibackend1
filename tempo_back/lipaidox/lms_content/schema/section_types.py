import strawberry
from typing import List
from ..models.section import CourseSection
from .lesson_types import LessonNode

@strawberry.type
class CourseSectionNode:
    id: strawberry.ID
    title: str
    orderIndex: int
    lessons: List[LessonNode]

    @classmethod
    def from_model(cls, instance: CourseSection):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            orderIndex=instance.order_index,
            lessons=[LessonNode.from_model(l) for l in instance.lessons.all().order_by('order_index')],
        )
