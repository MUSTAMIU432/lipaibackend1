import strawberry
from .course_mutations import CourseMutations
from .section_mutations import SectionMutations
from .lesson_mutations import LessonMutations
from .resource_mutations import ResourceMutations
from .lab_mutations import LabMutations

@strawberry.type
class ContentMutations(
    CourseMutations,
    SectionMutations,
    LessonMutations,
    ResourceMutations,
    LabMutations
):
    pass
