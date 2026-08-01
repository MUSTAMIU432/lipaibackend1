import strawberry
from typing import List, Optional
from datetime import datetime
from ..models.course import Course
from .section_types import CourseSectionNode
from lipaidox.lms_identity.schema.types import InstructorNode

@strawberry.type
class CourseNode:
    id: strawberry.ID
    instructor: InstructorNode
    title: str
    slug: str
    subtitle: Optional[str]
    description: Optional[str]
    thumbnailUrl: Optional[str]
    previewVideoUrl: Optional[str]
    language: str
    level: str
    price: float
    discountPrice: Optional[float]
    currency: str
    totalLessons: int
    totalSections: int
    totalDurationSeconds: int
    averageRating: float
    status: str
    sections: List[CourseSectionNode]
    createdAt: datetime

    @classmethod
    def from_model(cls, instance: Course):
        return cls(
            id=strawberry.ID(str(instance.id)),
            instructor=InstructorNode.from_model(instance.instructor),
            title=instance.title,
            slug=instance.slug,
            subtitle=instance.subtitle,
            description=instance.description,
            thumbnailUrl=instance.thumbnail_url,
            previewVideoUrl=instance.preview_video_url,
            language=instance.language,
            level=instance.level,
            price=float(instance.price),
            discountPrice=float(instance.discount_price) if instance.discount_price else None,
            currency=instance.currency,
            totalLessons=instance.total_lessons,
            totalSections=instance.total_sections,
            totalDurationSeconds=instance.total_duration_seconds,
            averageRating=float(instance.average_rating),
            status=instance.status,
            sections=[CourseSectionNode.from_model(s) for s in instance.sections.all().order_by('order_index')],
            createdAt=instance.created_at,
        )
