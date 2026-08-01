import strawberry
from typing import Optional
from ..schema.lab_types import LabNode
from ..models.lab import Lab

@strawberry.type
class LabQueries:
    @strawberry.field
    def lab_by_id(self, id: strawberry.ID) -> Optional[LabNode]:
        lab = Lab.objects.filter(id=id).first()
        return LabNode.from_model(lab) if lab else None
