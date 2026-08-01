import strawberry
from typing import Optional
from ..schema.section_types import CourseSectionNode
from ..models.section import CourseSection

@strawberry.type
class SectionQueries:
    @strawberry.field
    def section_by_id(self, id: strawberry.ID) -> Optional[CourseSectionNode]:
        section = CourseSection.objects.filter(id=id).first()
        return CourseSectionNode.from_model(section) if section else None
