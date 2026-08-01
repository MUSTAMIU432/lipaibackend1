import strawberry
from typing import List, Optional
from ..schema.note_types import NoteNode
from ..models.notes import Note

@strawberry.type
class NoteQueries:
    @strawberry.field
    def my_notes(self, info) -> List[NoteNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [NoteNode.from_model(n) for n in Note.objects.filter(enrollment__student__user=user)]

    @strawberry.field
    def lesson_notes(self, enrollment_id: strawberry.ID, lesson_id: strawberry.ID) -> List[NoteNode]:
        return [NoteNode.from_model(n) for n in Note.objects.filter(enrollment_id=enrollment_id, lesson_id=lesson_id)]
