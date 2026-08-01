import strawberry
from typing import Optional
from ..schema.resource_types import ResourceNode
from ..models.resource import Resource

@strawberry.type
class ResourceQueries:
    @strawberry.field
    def resource_by_id(self, id: strawberry.ID) -> Optional[ResourceNode]:
        resource = Resource.objects.filter(id=id).first()
        return ResourceNode.from_model(resource) if resource else None
