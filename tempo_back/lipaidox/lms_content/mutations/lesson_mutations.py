import strawberry
from typing import Optional
from ..schema.lesson_types import LessonNode
from ..models.course import Course
from ..models.section import CourseSection
from ..models.lesson import Lesson

@strawberry.type
class LessonMutations:
    @strawberry.mutation
    def add_lesson(
        self,
        course_id: strawberry.ID,
        section_id: strawberry.ID,
        title: str,
        slug: str,
        lesson_type: str,
        content_url: Optional[str] = None,
        order_index: int = 0
    ) -> LessonNode:
        course = Course.objects.get(id=course_id)
        section = CourseSection.objects.get(id=section_id)
        
        lesson = Lesson.objects.create(
            course=course,
            section=section,
            title=title,
            slug=slug,
            lesson_type=lesson_type,
            content_url=content_url,
            order_index=order_index
        )
        return LessonNode.from_model(lesson)
