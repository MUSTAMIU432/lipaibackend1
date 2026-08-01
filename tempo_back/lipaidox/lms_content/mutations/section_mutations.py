import strawberry
from ..schema.section_types import CourseSectionNode
from ..models.course import Course
from ..models.section import CourseSection

@strawberry.type
class SectionMutations:
    @strawberry.mutation
    def create_section(
        self,
        course_id: strawberry.ID,
        title: str,
        order_index: int
    ) -> CourseSectionNode:
        course = Course.objects.get(id=course_id)
        section = CourseSection.objects.create(
            course=course,
            title=title,
            order_index=order_index
        )
        return CourseSectionNode.from_model(section)
