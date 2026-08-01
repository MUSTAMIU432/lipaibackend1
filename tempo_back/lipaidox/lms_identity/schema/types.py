import strawberry
from typing import List, Optional
from datetime import datetime, date
from ..models import (
    StudentProfile, UserRole, Role, InstructorProfile,
    WorkExperience, EducationRecord, ExternalCertification, Project,
    NotificationPreference, PrivacySetting, AppearanceSetting, DataSetting
)

@strawberry.type
class NotificationPreferenceNode:
    emailEnabled: bool
    pushEnabled: bool
    smsEnabled: bool
    courseUpdates: bool
    newLessons: bool
    quizReminders: bool
    assignmentDue: bool
    cohortSessions: bool
    streakReminders: bool
    certificateEarned: bool
    badgeEarned: bool
    jobMatches: bool
    marketingEmails: bool

    @classmethod
    def from_model(cls, instance: NotificationPreference):
        return cls(
            emailEnabled=instance.email_enabled,
            pushEnabled=instance.push_enabled,
            smsEnabled=instance.sms_enabled,
            courseUpdates=instance.course_updates,
            newLessons=instance.new_lessons,
            quizReminders=instance.quiz_reminders,
            assignmentDue=instance.assignment_due,
            cohortSessions=instance.cohort_sessions,
            streakReminders=instance.streak_reminders,
            certificateEarned=instance.certificate_earned,
            badgeEarned=instance.badge_earned,
            jobMatches=instance.job_matches,
            marketingEmails=instance.marketing_emails,
        )

@strawberry.type
class PrivacySettingNode:
    profileVisibility: str
    showProgress: bool
    showBadges: bool
    showCertificates: bool
    showActivity: bool
    allowMessaging: bool
    showInTalentPool: bool
    allowEmployerContact: bool

    @classmethod
    def from_model(cls, instance: PrivacySetting):
        return cls(
            profileVisibility=instance.profile_visibility,
            showProgress=instance.show_progress,
            showBadges=instance.show_badges,
            showCertificates=instance.show_certificates,
            showActivity=instance.show_activity,
            allowMessaging=instance.allow_messaging,
            showInTalentPool=instance.show_in_talent_pool,
            allowEmployerContact=instance.allow_employer_contact,
        )

@strawberry.type
class AppearanceSettingNode:
    theme: str
    language: str
    timezone: str
    dateFormat: str
    timeFormat: str

    @classmethod
    def from_model(cls, instance: AppearanceSetting):
        return cls(
            theme=instance.theme,
            language=instance.language,
            timezone=instance.timezone,
            dateFormat=instance.date_format,
            timeFormat=instance.time_format,
        )

@strawberry.type
class DataSettingNode:
    lowDataMode: bool
    autoDownload: bool
    downloadWifiOnly: bool
    videoQuality: str

    @classmethod
    def from_model(cls, instance: DataSetting):
        return cls(
            lowDataMode=instance.low_data_mode,
            autoDownload=instance.auto_download,
            downloadWifiOnly=instance.download_wifi_only,
            videoQuality=instance.video_quality,
        )

@strawberry.type
class WorkExperienceNode:
    id: strawberry.ID
    company: str
    position: str
    location: Optional[str]
    locationType: str
    startDate: date
    endDate: Optional[date]
    isCurrent: bool
    description: Optional[str]
    achievements: List[str]
    skills: List[str]

    @classmethod
    def from_model(cls, instance: WorkExperience):
        return cls(
            id=strawberry.ID(str(instance.id)),
            company=instance.company,
            position=instance.position,
            location=instance.location,
            locationType=instance.location_type,
            startDate=instance.start_date,
            endDate=instance.end_date,
            isCurrent=instance.is_current,
            description=instance.description,
            achievements=instance.achievements or [],
            skills=instance.skills or [],
        )

@strawberry.type
class EducationRecordNode:
    id: strawberry.ID
    institution: str
    degree: str
    fieldOfStudy: str
    startDate: date
    endDate: Optional[date]
    isCurrent: bool
    description: Optional[str]
    location: Optional[str]

    @classmethod
    def from_model(cls, instance: EducationRecord):
        return cls(
            id=strawberry.ID(str(instance.id)),
            institution=instance.institution,
            degree=instance.degree,
            fieldOfStudy=instance.field_of_study,
            startDate=instance.start_date,
            endDate=instance.end_date,
            isCurrent=instance.is_current,
            description=instance.description,
            location=instance.location,
        )

@strawberry.type
class ExternalCertificationNode:
    id: strawberry.ID
    name: str
    issuer: str
    issueDate: date
    expiryDate: Optional[date]
    credentialId: Optional[str]
    credentialUrl: Optional[str]
    skills: List[str]

    @classmethod
    def from_model(cls, instance: ExternalCertification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            issuer=instance.issuer,
            issueDate=instance.issue_date,
            expiryDate=instance.expiry_date,
            credentialId=instance.credential_id,
            credentialUrl=instance.credential_url,
            skills=instance.skills or [],
        )

@strawberry.type
class StudentProjectNode:
    id: strawberry.ID
    title: str
    description: str
    url: Optional[str]
    githubUrl: Optional[str]
    technologies: List[str]
    isFeatured: bool

    @classmethod
    def from_model(cls, instance: Project):
        return cls(
            id=strawberry.ID(str(instance.id)),
            title=instance.title,
            description=instance.description,
            url=instance.url,
            githubUrl=instance.github_url,
            technologies=instance.technologies or [],
            isFeatured=instance.is_featured,
        )

@strawberry.type
class StudentNode:
    id: strawberry.ID
    headline: Optional[str]
    bio: Optional[str]
    location: Optional[str]
    phone: Optional[str]
    employmentStatus: Optional[str]
    yearsOfExperience: int
    careerGoals: List[str]
    desiredRoles: List[str]
    onboardingCompleted: bool
    onboardingStep: int
    totalCoursesEnrolled: int
    totalCoursesCompleted: int
    totalLearningMins: int
    website: Optional[str]
    linkedin: Optional[str]
    github: Optional[str]
    portfolio: Optional[str]
    remotePreference: bool
    willingToRelocate: bool

    # Professional History
    workExperiences: List[WorkExperienceNode]
    educationRecords: List[EducationRecordNode]
    externalCertifications: List[ExternalCertificationNode]
    projects: List[StudentProjectNode]

    # Settings
    notificationPreferences: Optional[NotificationPreferenceNode]
    privacySettings: Optional[PrivacySettingNode]
    appearanceSettings: Optional[AppearanceSettingNode]
    dataSettings: Optional[DataSettingNode]

    @classmethod
    def from_model(cls, instance: StudentProfile):
        return cls(
            id=strawberry.ID(str(instance.id)),
            headline=instance.headline,
            bio=instance.bio,
            location=instance.location,
            phone=instance.phone,
            employmentStatus=instance.employment_status,
            yearsOfExperience=instance.years_of_experience,
            careerGoals=instance.career_goals or [],
            desiredRoles=instance.desired_roles or [],
            onboardingCompleted=instance.onboarding_completed,
            onboardingStep=instance.onboarding_step,
            totalCoursesEnrolled=instance.total_courses_enrolled,
            totalCoursesCompleted=instance.total_courses_completed,
            totalLearningMins=instance.total_learning_mins,
            website=instance.website,
            linkedin=instance.linkedin,
            github=instance.github,
            portfolio=instance.portfolio,
            remotePreference=instance.remote_preference,
            willingToRelocate=instance.willing_to_relocate,
            
            workExperiences=[WorkExperienceNode.from_model(exp) for exp in instance.experiences.all()],
            educationRecords=[EducationRecordNode.from_model(edu) for edu in instance.education.all()],
            externalCertifications=[ExternalCertificationNode.from_model(cert) for cert in instance.external_certifications.all()],
            projects=[StudentProjectNode.from_model(p) for p in instance.projects.all()],
            
            notificationPreferences=NotificationPreferenceNode.from_model(instance.notificationpreference) if hasattr(instance, 'notificationpreference') else None,
            privacySettings=PrivacySettingNode.from_model(instance.privacysetting) if hasattr(instance, 'privacysetting') else None,
            appearanceSettings=AppearanceSettingNode.from_model(instance.appearancesetting) if hasattr(instance, 'appearancesetting') else None,
            dataSettings=DataSettingNode.from_model(instance.datasetting) if hasattr(instance, 'datasetting') else None,
        )

@strawberry.type
class InstructorNode:
    id: strawberry.ID
    bio: Optional[str]
    headline: Optional[str]
    specializations: List[str]
    averageRating: float
    status: str

    @classmethod
    def from_model(cls, instance: InstructorProfile):
        return cls(
            id=strawberry.ID(str(instance.id)),
            bio=instance.bio,
            headline=instance.headline,
            specializations=instance.specializations or [],
            averageRating=float(instance.average_rating),
            status=instance.status,
        )

@strawberry.type
class RoleNode:
    id: strawberry.ID
    name: str

    @classmethod
    def from_model(cls, instance: Role):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
        )

@strawberry.type
class UserRoleNode:
    id: strawberry.ID
    role: RoleNode
    assignedAt: datetime

    @classmethod
    def from_model(cls, instance: UserRole):
        return cls(
            id=strawberry.ID(str(instance.id)),
            role=RoleNode.from_model(instance.role),
            assignedAt=instance.assigned_at,
        )
