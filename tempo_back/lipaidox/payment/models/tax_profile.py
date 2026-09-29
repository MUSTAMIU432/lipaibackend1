import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class TaxProfileStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'


class TaxProfile(TenantAwareModel):
    """
    A creator's taxpayer registration — what the mobile "Tax Information"
    screen submits (country, authority, TIN, registration certificate).

    One per creator: resubmitting replaces the details and puts the profile
    back to ``pending``. The ``tax_payment_info`` eligibility requirement is
    met once an admin marks it ``verified`` (see ``eligibility_schema.py``).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.OneToOneField(
        "lipaidox_creator_profile.CreatorProfile",
        on_delete=models.CASCADE,
        related_name="tax_profile",
    )
    country_code = models.CharField(max_length=2)
    country_name = models.CharField(max_length=100)
    tax_authority = models.CharField(max_length=255)
    taxpayer_name = models.CharField(max_length=255)
    tin_number = models.CharField(max_length=100)
    tin_certificate_url = models.URLField(max_length=1000)
    status = models.CharField(max_length=20, choices=TaxProfileStatus.choices, default=TaxProfileStatus.PENDING)
    rejection_reason = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tax_profiles"
        app_label = "lipaidox_payment"
        indexes = [models.Index(fields=['status'])]

    def __str__(self):
        return f"TaxProfile({self.country_code}, {self.status}) - {self.creator}"
