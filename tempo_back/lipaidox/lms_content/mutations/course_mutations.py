import strawberry
from typing import Optional
from ..schema.course_types import CourseNode
from ..models.course import Course
from lipaidox.lms_identity.models import InstructorProfile

@strawberry.type
class CourseMutations:
    @strawberry.mutation
    def create_course(
        self,
        info,
        title: str,
        slug: str,
        subtitle: Optional[str] = None,
        description: Optional[str] = None,
        price: float = 0.00,
        level: str = "all_levels"
    ) -> CourseNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        instructor = InstructorProfile.objects.get(user=user)
        
        course = Course.objects.create(
            instructor=instructor,
            title=title,
            slug=slug,
            subtitle=subtitle,
            description=description,
            price=price,
            level=level,
            tenant=user.tenant 
        )
        return CourseNode.from_model(course)
