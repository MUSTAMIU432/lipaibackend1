import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from multitenant.models import TenantAwareModel
from .enums import TwoFAMethod


class SecuritySettings(TenantAwareModel):
    """
    Security Settings - Module 16
    User security preferences and 2FA settings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'lipaidox_auth.User',
        on_delete=models.CASCADE,
        related_name='security_settings'
    )

    # Two Factor Auth
    two_fa_enabled = models.BooleanField(default=False)
    two_fa_method = models.CharField(
        max_length=20,
        choices=TwoFAMethod.choices,
        null=True,
        blank=True
    )
    two_fa_phone_number = models.CharField(max_length=20, null=True, blank=True)
    two_fa_email = models.EmailField(max_length=255, null=True, blank=True)
    two_fa_secret = models.TextField(null=True, blank=True)
    two_fa_enabled_at = models.DateTimeField(null=True, blank=True)
    two_fa_last_used_at = models.DateTimeField(null=True, blank=True)

    # Backup Codes
    backup_codes_hash = ArrayField(models.TextField(), default=list)
    backup_codes_generated_at = models.DateTimeField(null=True, blank=True)
    backup_codes_remaining = models.IntegerField(default=0)

    # Risk Scoring
    account_risk_score = models.DecimalField(max_digits=5, decimal_places=4, default=0.00)
    risk_score_updated_at = models.DateTimeField(null=True, blank=True)
    risk_flags = ArrayField(models.TextField(), default=list)

    # Login Preferences
    login_notification_email = models.BooleanField(default=True)
    login_notification_sms = models.BooleanField(default=False)
    trusted_ips = ArrayField(models.CharField(max_length=45), default=list)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'security_settings'
        app_label = 'lipaidox_security'
        indexes = [
            models.Index(fields=['user'], name='idx_security_settings_user'),
            models.Index(fields=['two_fa_enabled'], name='idx_security_settings_2fa'),
            models.Index(fields=['-account_risk_score'], name='idx_security_settings_risk'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['user'], name='security_settings_user_unique'),
            models.CheckConstraint(
                check=models.Q(account_risk_score__range=(0, 1)),
                name='risk_score_check'
            ),
            models.CheckConstraint(
                check=models.Q(backup_codes_remaining__gte=0),
                name='backup_codes_check'
            ),
        ]

    def __str__(self):
        return f"Security Settings: {self.user.username}"

    def enable_2fa(self, method, secret=None):
        """Enable two-factor authentication"""
        from django.utils import timezone
        
        self.two_fa_enabled = True
        self.two_fa_method = method
        self.two_fa_secret = secret
        self.two_fa_enabled_at = timezone.now()
        self.save()

    def disable_2fa(self):
        """Disable two-factor authentication"""
        self.two_fa_enabled = False
        self.two_fa_method = None
        self.two_fa_secret = None
        self.two_fa_enabled_at = None
        self.two_fa_last_used_at = None
        self.backup_codes_hash = []
        self.backup_codes_remaining = 0
        self.save()

    def update_risk_score(self, score, flags=None):
        """Update account risk score"""
        from django.utils import timezone
        
        self.account_risk_score = score
        self.risk_score_updated_at = timezone.now()
        if flags:
            self.risk_flags = flags
        self.save()

    def add_trusted_ip(self, ip_address):
        """Add IP to trusted list"""
        if ip_address not in self.trusted_ips:
            self.trusted_ips.append(ip_address)
            self.save()

    def remove_trusted_ip(self, ip_address):
        """Remove IP from trusted list"""
        if ip_address in self.trusted_ips:
            self.trusted_ips.remove(ip_address)
            self.save()

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create security settings for user"""
        settings, created = cls.objects.get_or_create(
            user=user,
            tenant=user.tenant
        )
        return settings
