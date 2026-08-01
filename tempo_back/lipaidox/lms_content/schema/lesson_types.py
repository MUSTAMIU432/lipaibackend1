import strawberry
from typing import List, Optional
from ..models.lesson import Lesson
from .resource_types import ResourceNode
from .lab_types import LabNode

@strawberry.type
class LessonNode:
    id: strawberry.ID
    title: str
    slug: str
    lessonType: str
    contentUrl: Optional[str]
    description: Optional[str]
    durationSeconds: int
    orderIndex: int
    isFreePreview: bool
    isPublished: bool
    resources: List[ResourceNode]
    labs: List[LabNode]

    @classmethod
    def from_model(cls, instance: Lesson):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            slug=instance.slug,
            lessonType=instance.lesson_type,
            contentUrl=instance.content_url,
            description=instance.description,
            durationSeconds=instance.duration_seconds,
            orderIndex=instance.order_index,
            isFreePreview=instance.is_free_preview,
            isPublished=instance.is_published,
            resources=[ResourceNode.from_model(r) for r in instance.resources.all()],
            labs=[LabNode.from_model(l) for l in instance.labs.all()],
        )
