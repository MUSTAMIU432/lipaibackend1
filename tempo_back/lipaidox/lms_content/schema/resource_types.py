import strawberry
from ..models.resource import Resource

@strawberry.type
class ResourceNode:
    id: strawberry.ID
    title: str
    resourceType: str
    url: str
    fileSizeKb: int

    @classmethod
    def from_model(cls, instance: Resource):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            resourceType=instance.resource_type,
            url=instance.url,
            fileSizeKb=instance.file_size_kb,
        )
