import strawberry
from ..schema.resource_types import ResourceNode
from ..models.lesson import Lesson
from ..models.resource import Resource

@strawberry.type
class ResourceMutations:
    @strawberry.mutation
    def add_resource(
        self,
        lesson_id: strawberry.ID,
        title: str,
        url: str,
        resource_type: str = "pdf",
        file_size_kb: int = 0
    ) -> ResourceNode:
        lesson = Lesson.objects.get(id=lesson_id)
        resource = Resource.objects.create(
            lesson=lesson,
            title=title,
            url=url,
            resource_type=resource_type,
            file_size_kb=file_size_kb
        )
        return ResourceNode.from_model(resource)
