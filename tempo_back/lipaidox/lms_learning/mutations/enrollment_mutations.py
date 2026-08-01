import strawberry
from ..schema.enrollment_types import EnrollmentNode
from ..models.enrollment import Enrollment, EnrollmentStatus
from lipaidox.lms_identity.models import StudentProfile
from lipaidox.lms_content.models import Course

@strawberry.type
class EnrollmentMutations:
    @strawberry.mutation
    def enroll_in_course(self, info, course_id: strawberry.ID) -> EnrollmentNode:
        user = info.context.request.user
        if not user.is_authenticated:
            raise Exception("Authentication required")
        
        student = StudentProfile.objects.get(user=user)
        course = Course.objects.get(id=course_id)
        
        enrollment, created = Enrollment.objects.get_or_create(
            student=student,
            course=course,
            defaults={'tenant': user.tenant}
        )
        return EnrollmentNode.from_model(enrollment)

    @strawberry.mutation
    def update_enrollment_status(self, enrollment_id: strawberry.ID, status: str) -> EnrollmentNode:
        enrollment = Enrollment.objects.get(id=enrollment_id)
        enrollment.status = status
        enrollment.save()
        return EnrollmentNode.from_model(enrollment)

    @strawberry.mutation
    def delete_enrollment(self, enrollment_id: strawberry.ID) -> bool:
        Enrollment.objects.filter(id=enrollment_id).delete()
        return True
