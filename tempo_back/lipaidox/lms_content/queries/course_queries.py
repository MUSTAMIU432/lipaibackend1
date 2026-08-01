import strawberry
from typing import List, Optional
from ..schema.course_types import CourseNode
from ..models.course import Course

@strawberry.type
class CourseQueries:
    @strawberry.field
    def all_courses(self) -> List[CourseNode]:
        return [CourseNode.from_model(c) for c in Course.objects.filter(status='published')]

    @strawberry.field
    def course_by_slug(self, slug: str) -> Optional[CourseNode]:
        course = Course.objects.filter(slug=slug).first()
        return CourseNode.from_model(course) if course else None

    @strawberry.field
    def instructor_courses(self, info) -> List[CourseNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [CourseNode.from_model(c) for c in Course.objects.filter(instructor__user=user)]
