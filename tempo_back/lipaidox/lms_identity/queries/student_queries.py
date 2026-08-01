import strawberry
from typing import Optional, List
from ..schema.types import (
    StudentNode, InstructorNode, WorkExperienceNode, 
    EducationRecordNode, StudentProjectNode, ExternalCertificationNode,
    NotificationPreferenceNode, PrivacySettingNode, AppearanceSettingNode, DataSettingNode,
    RoleNode, UserRoleNode
)
from ..models import (
    StudentProfile, InstructorProfile, WorkExperience, 
    EducationRecord, Project, ExternalCertification, 
    NotificationPreference, PrivacySetting, AppearanceSetting, DataSetting,
    Role, UserRole
)

@strawberry.type
class StudentQueries:
    @strawberry.field
    def all_instructors(self) -> List[InstructorNode]:
        return [InstructorNode.from_model(i) for i in InstructorProfile.objects.filter(status='approved')]

    @strawberry.field
    def instructor_detail(self, instructor_id: strawberry.ID) -> Optional[InstructorNode]:
        profile = InstructorProfile.objects.filter(id=instructor_id).first()
        return InstructorNode.from_model(profile) if profile else None

    @strawberry.field
    def my_roles(self, info) -> List[UserRoleNode]:
        user = info.context.request.user
        if not user.is_authenticated:
            return []
        roles = UserRole.objects.filter(user=user)
        return [UserRoleNode.from_model(r) for r in roles]

    # Existing Queries
    @strawberry.field
    def me_as_student(self, info) -> Optional[StudentNode]:
        user = info.context.request.user
        profile = StudentProfile.objects.filter(user=user).first()
        return StudentNode.from_model(profile) if profile else None

    # Settings Queries
    @strawberry.field
    def my_notification_settings(self, info) -> Optional[NotificationPreferenceNode]:
        user = info.context.request.user
        pref = NotificationPreference.objects.filter(student__user=user).first()
        return NotificationPreferenceNode.from_model(pref) if pref else None

    @strawberry.field
    def my_privacy_settings(self, info) -> Optional[PrivacySettingNode]:
        user = info.context.request.user
        setting = PrivacySetting.objects.filter(student__user=user).first()
        return PrivacySettingNode.from_model(setting) if setting else None

    # Professional Queries
    @strawberry.field
    def my_experiences(self, info) -> List[WorkExperienceNode]:
        user = info.context.request.user
        exps = WorkExperience.objects.filter(student__user=user)
        return [WorkExperienceNode.from_model(e) for e in exps]

    @strawberry.field
    def my_projects(self, info) -> List[StudentProjectNode]:
        user = info.context.request.user
        projects = Project.objects.filter(student__user=user)
        return [StudentProjectNode.from_model(p) for p in projects]
