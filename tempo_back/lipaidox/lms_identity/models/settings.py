import uuid
from django.db import models
from multitenant.models import TenantAwareModel

class NotificationPreference(models.Model):
    student = models.OneToOneField("lms_identity.StudentProfile", on_delete=models.CASCADE, primary_key=True)
    
    # Channels
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    # Alerts
    course_updates = models.BooleanField(default=True)
    new_lessons = models.BooleanField(default=True)
    quiz_reminders = models.BooleanField(default=True)
    assignment_due = models.BooleanField(default=True)
    cohort_sessions = models.BooleanField(default=True)
    streak_reminders = models.BooleanField(default=True)
    certificate_earned = models.BooleanField(default=True)
    badge_earned = models.BooleanField(default=True)
    job_matches = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=False)

    class Meta:
        db_table = "lms_notification_preferences"
        app_label = "lms_identity"

class PrivacySetting(models.Model):
    student = models.OneToOneField("lms_identity.StudentProfile", on_delete=models.CASCADE, primary_key=True)
    
    profile_visibility = models.CharField(max_length=20, choices=[('public', 'Public'), ('connections', 'Connections'), ('private', 'Private')], default='public')
    show_progress = models.BooleanField(default=True)
    show_badges = models.BooleanField(default=True)
    show_certificates = models.BooleanField(default=True)
    show_activity = models.BooleanField(default=True)
    
    allow_messaging = models.BooleanField(default=True)
    show_in_talent_pool = models.BooleanField(default=True)
    allow_employer_contact = models.BooleanField(default=True)

    class Meta:
        db_table = "lms_privacy_settings"
        app_label = "lms_identity"

class AppearanceSetting(models.Model):
    student = models.OneToOneField("lms_identity.StudentProfile", on_delete=models.CASCADE, primary_key=True)
    
    theme = models.CharField(max_length=20, choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')], default='system')
    language = models.CharField(max_length=10, default="en")
    timezone = models.CharField(max_length=100, default="UTC")
    date_format = models.CharField(max_length=30, default="YYYY-MM-DD")
    time_format = models.CharField(max_length=30, choices=[('12h', '12h'), ('24h', '24h')], default='12h')

    class Meta:
        db_table = "lms_appearance_settings"
        app_label = "lms_identity"

class DataSetting(models.Model):
    student = models.OneToOneField("lms_identity.StudentProfile", on_delete=models.CASCADE, primary_key=True)
    
    low_data_mode = models.BooleanField(default=False)
    auto_download = models.BooleanField(default=False)
    download_wifi_only = models.BooleanField(default=True)
    video_quality = models.CharField(max_length=20, choices=[('auto', 'Auto'), ('480p', '480p'), ('720p', '720p'), ('1080p', 'Full HD')], default='auto')

    class Meta:
        db_table = "lms_data_settings"
        app_label = "lms_identity"
