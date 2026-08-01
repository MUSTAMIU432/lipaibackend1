import strawberry
from typing import List, Optional
from ..schema.study_room_types import StudyRoomNode, StudyRoomMemberNode
from ..models.study_room import StudyRoom, StudyRoomMember

@strawberry.type
class StudyRoomQueries:
    @strawberry.field
    def all_study_rooms(self) -> List[StudyRoomNode]:
        return [StudyRoomNode.from_model(r) for r in StudyRoom.objects.filter(room_type='public', is_active=True)]

    @strawberry.field
    def study_room_by_slug(self, slug: str) -> Optional[StudyRoomNode]:
        room = StudyRoom.objects.filter(slug=slug, is_active=True).first()
        return StudyRoomNode.from_model(room) if room else None

    @strawberry.field
    def my_study_rooms(self, info) -> List[StudyRoomNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        return [StudyRoomNode.from_model(m.room) for m in user.student_profile.studyroommember_set.all()]

    @strawberry.field
    def room_members(self, room_id: strawberry.ID) -> List[StudyRoomMemberNode]:
        return [StudyRoomMemberNode.from_model(m) for m in StudyRoomMember.objects.filter(room_id=room_id).order_by('-is_online', 'role')]

    @strawberry.field
    def online_members(self, room_id: strawberry.ID) -> List[StudyRoomMemberNode]:
        return [StudyRoomMemberNode.from_model(m) for m in StudyRoomMember.objects.filter(room_id=room_id, is_online=True)]
