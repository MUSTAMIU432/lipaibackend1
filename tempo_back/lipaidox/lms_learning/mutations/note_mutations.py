import strawberry
from ..schema.note_types import NoteNode
from ..models.notes import Note

@strawberry.type
class NoteMutations:
    @strawberry.mutation
    def add_lesson_note(
        self,
        enrollment_id: strawberry.ID,
        lesson_id: strawberry.ID,
        content: str,
        timestamp_seconds: int = 0,
        is_private: bool = True
    ) -> NoteNode:
        note = Note.objects.create(
            enrollment_id=enrollment_id,
            lesson_id=lesson_id,
            content=content,
            timestamp_seconds=timestamp_seconds,
            is_private=is_private
        )
        return NoteNode.from_model(note)

    @strawberry.mutation
    def update_lesson_note(self, note_id: strawberry.ID, content: str) -> NoteNode:
        note = Note.objects.get(id=note_id)
        note.content = content
        note.save()
        return NoteNode.from_model(note)

    @strawberry.mutation
    def delete_lesson_note(self, note_id: strawberry.ID) -> bool:
        Note.objects.filter(id=note_id).delete()
        return True
