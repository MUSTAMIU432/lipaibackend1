import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from multitenant.models import Tenant


def get_phone_expiry():
    return timezone.now() + timedelta(minutes=10)


class PhoneVerification(models.Model):

    STATUS_PENDING  = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_EXPIRED  = "expired"
    STATUS_FAILED   = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING,  "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_EXPIRED,  "Expired"),
        (STATUS_FAILED,   "Failed"),
    ]

    DELIVERY_WHATSAPP = "whatsapp"
    DELIVERY_EMAIL    = "email"          # fallback if WhatsApp fails

    DELIVERY_CHOICES = [
        (DELIVERY_WHATSAPP, "WhatsApp"),
        (DELIVERY_EMAIL,    "Email"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="phone_verifications",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        "lipaidox_auth.User",
        on_delete=models.CASCADE,
        related_name="phone_verifications",
    )

    # ── PHONE ──────────────────────────────────────────────────────

    phone_number    = models.CharField(max_length=20)
    country_code    = models.CharField(max_length=10)

    # ── OTP ────────────────────────────────────────────────────────

    otp_code        = models.CharField(max_length=10)
    status          = models.CharField(
                        max_length=20,
                        choices=STATUS_CHOICES,
                        default=STATUS_PENDING,
                    )
    attempts        = models.PositiveSmallIntegerField(default=0)
    max_attempts    = models.PositiveSmallIntegerField(default=5)

    # ── WHATSAPP DELIVERY ──────────────────────────────────────────

    delivery_channel        = models.CharField(
                                max_length=20,
                                choices=DELIVERY_CHOICES,
                                default=DELIVERY_WHATSAPP,
                            )
    whatsapp_message_id     = models.CharField(
                                max_length=255,
                                null=True,
                                blank=True,
                                help_text="Message ID returned by WhatsApp API after sending",
                            )
    whatsapp_status         = models.CharField(
                                max_length=50,
                                null=True,
                                blank=True,
                                help_text="Delivery status from WhatsApp webhook: sent, delivered, read, failed",
                            )
    whatsapp_error_code     = models.CharField(
                                max_length=50,
                                null=True,
                                blank=True,
                                help_text="Error code from WhatsApp API if sending failed",
                            )
    whatsapp_error_message  = models.TextField(
                                null=True,
                                blank=True,
                                help_text="Error detail from WhatsApp API if sending failed",
                            )
    sent_at                 = models.DateTimeField(
                                null=True,
                                blank=True,
                                help_text="Timestamp when WhatsApp message was dispatched",
                            )
    delivered_at            = models.DateTimeField(
                                null=True,
                                blank=True,
                                help_text="Timestamp from WhatsApp webhook confirming delivery",
                            )

    # ── FALLBACK ───────────────────────────────────────────────────

    fallback_to_email       = models.BooleanField(
                                default=False,
                                help_text="True if WhatsApp failed and OTP was sent via Email",
                            )
    fallback_triggered_at   = models.DateTimeField(null=True, blank=True)

    # ── SECURITY ───────────────────────────────────────────────────

    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    # ── TIMESTAMPS ─────────────────────────────────────────────────

    expires_at      = models.DateTimeField(default=get_phone_expiry)
    verified_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = "phone_verifications"
        app_label = "lipaidox_auth"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["phone_number", "status"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["whatsapp_message_id"]),
        ]

    def __str__(self):
        return f"PhoneVerification({self.phone_number} | {self.status})"

    # ── PROPERTIES ─────────────────────────────────────────────────────────

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_verified(self):
        return self.status == self.STATUS_VERIFIED

    @property
    def has_exceeded_attempts(self):
        return self.attempts >= self.max_attempts

    @property
    def e164_phone_number(self):
        """
        Returns phone in E.164 format required by WhatsApp API
        e.g. country_code='+255' phone_number='712345678' → '+255712345678'
        """
        return f"{self.country_code}{self.phone_number.lstrip('0')}"

    # ── METHODS ────────────────────────────────────────────────────────────

    def mark_verified(self):
        self.status      = self.STATUS_VERIFIED
        self.verified_at = timezone.now()
        self.save(update_fields=["status", "verified_at"])

    def mark_expired(self):
        self.status = self.STATUS_EXPIRED
        self.save(update_fields=["status"])

    def increment_attempts(self):
        self.attempts += 1
        if self.has_exceeded_attempts:
            self.status = self.STATUS_FAILED
        self.save(update_fields=["attempts", "status"])

    def record_whatsapp_sent(self, message_id: str):
        """Call this after WhatsApp API returns a message_id."""
        self.whatsapp_message_id = message_id
        self.whatsapp_status     = "sent"
        self.sent_at             = timezone.now()
        self.save(update_fields=[
            "whatsapp_message_id",
            "whatsapp_status",
            "sent_at",
        ])

    def record_whatsapp_delivered(self):
        """Call this from WhatsApp webhook when status = delivered."""
        self.whatsapp_status = "delivered"
        self.delivered_at    = timezone.now()
        self.save(update_fields=["whatsapp_status", "delivered_at"])

    def record_whatsapp_failed(self, error_code: str, error_message: str):
        """Call this from WhatsApp webhook when status = failed."""
        self.whatsapp_status        = "failed"
        self.whatsapp_error_code    = error_code
        self.whatsapp_error_message = error_message
        self.save(update_fields=[
            "whatsapp_status",
            "whatsapp_error_code",
            "whatsapp_error_message",
        ])

    def trigger_email_fallback(self):
        """Call this when WhatsApp delivery fails and Email is used instead."""
        self.fallback_to_email     = True
        self.fallback_triggered_at = timezone.now()
        self.delivery_channel      = self.DELIVERY_EMAIL
        self.save(update_fields=[
            "fallback_to_email",
            "fallback_triggered_at",
            "delivery_channel",
        ])
