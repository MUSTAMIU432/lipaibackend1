import strawberry
from typing import Optional
from ..schema.types import (
    NotificationPreferenceNode, PrivacySettingNode, 
    AppearanceSettingNode, DataSettingNode
)
from ..models import (
    StudentProfile, NotificationPreference, 
    PrivacySetting, AppearanceSetting, DataSetting
)

@strawberry.type
class SettingsMutations:
    @strawberry.mutation
    def update_notification_preferences(
        self,
        info,
        email_enabled: Optional[bool] = None,
        push_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None,
        course_updates: Optional[bool] = None,
        new_lessons: Optional[bool] = None,
        quiz_reminders: Optional[bool] = None,
        assignment_due: Optional[bool] = None,
        cohort_sessions: Optional[bool] = None,
        streak_reminders: Optional[bool] = None,
        certificate_earned: Optional[bool] = None,
        badge_earned: Optional[bool] = None,
        job_matches: Optional[bool] = None,
        marketing_emails: Optional[bool] = None
    ) -> NotificationPreferenceNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        pref, _ = NotificationPreference.objects.get_or_create(student=student)
        
        for field, value in locals().items():
            if field in ['self', 'info', 'pref', 'user', 'student', '_'] or value is None:
                continue
            setattr(pref, field, value)
        
        pref.save()
        return NotificationPreferenceNode.from_model(pref)

    @strawberry.mutation
    def update_privacy_settings(
        self,
        info,
        profile_visibility: Optional[str] = None,
        show_progress: Optional[bool] = None,
        show_badges: Optional[bool] = None,
        show_certificates: Optional[bool] = None,
        show_activity: Optional[bool] = None,
        allow_messaging: Optional[bool] = None,
        show_in_talent_pool: Optional[bool] = None,
        allow_employer_contact: Optional[bool] = None
    ) -> PrivacySettingNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        setting, _ = PrivacySetting.objects.get_or_create(student=student)
        
        if profile_visibility: setting.profile_visibility = profile_visibility
        if show_progress is not None: setting.show_progress = show_progress
        if show_badges is not None: setting.show_badges = show_badges
        if show_certificates is not None: setting.show_certificates = show_certificates
        if show_activity is not None: setting.show_activity = show_activity
        if allow_messaging is not None: setting.allow_messaging = allow_messaging
        if show_in_talent_pool is not None: setting.show_in_talent_pool = show_in_talent_pool
        if allow_employer_contact is not None: setting.allow_employer_contact = allow_employer_contact
        
        setting.save()
        return PrivacySettingNode.from_model(setting)

    @strawberry.mutation
    def update_appearance_settings(
        self,
        info,
        theme: Optional[str] = None,
        language: Optional[str] = None,
        timezone: Optional[str] = None,
        date_format: Optional[str] = None,
        time_format: Optional[str] = None
    ) -> AppearanceSettingNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        setting, _ = AppearanceSetting.objects.get_or_create(student=student)
        
        if theme: setting.theme = theme
        if language: setting.language = language
        if timezone: setting.timezone = timezone
        if date_format: setting.date_format = date_format
        if time_format: setting.time_format = time_format
        
        setting.save()
        return AppearanceSettingNode.from_model(setting)

    @strawberry.mutation
    def update_data_settings(
        self,
        info,
        low_data_mode: Optional[bool] = None,
        auto_download: Optional[bool] = None,
        download_wifi_only: Optional[bool] = None,
        video_quality: Optional[str] = None
    ) -> DataSettingNode:
        user = info.context.request.user
        student = StudentProfile.objects.get(user=user)
        setting, _ = DataSetting.objects.get_or_create(student=student)
        
        if low_data_mode is not None: setting.low_data_mode = low_data_mode
        if auto_download is not None: setting.auto_download = auto_download
        if download_wifi_only is not None: setting.download_wifi_only = download_wifi_only
        if video_quality: setting.video_quality = video_quality
        
        setting.save()
        return DataSettingNode.from_model(setting)
