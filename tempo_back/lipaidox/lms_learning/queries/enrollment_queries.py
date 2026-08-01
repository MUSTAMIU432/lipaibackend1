import strawberry
from typing import List, Optional
from ..schema.enrollment_types import EnrollmentNode
from ..models.enrollment import Enrollment

@strawberry.type
class EnrollmentQueries:
    @strawberry.field
    def my_enrollments(self, info) -> List[EnrollmentNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [EnrollmentNode.from_model(e) for e in Enrollment.objects.filter(student__user=user)]

    @strawberry.field
    def enrollment_detail(self, enrollment_id: strawberry.ID) -> Optional[EnrollmentNode]:
        enrollment = Enrollment.objects.filter(id=enrollment_id).first()
        return EnrollmentNode.from_model(enrollment) if enrollment else None
