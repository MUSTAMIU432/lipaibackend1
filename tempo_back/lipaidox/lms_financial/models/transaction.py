import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class LmsPayment(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lms_payments")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    
    status = models.CharField(max_length=20, default="succeeded")
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    
    stripe_payment_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_charge_id = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_payments"
        app_label = "lms_financial"

class LmsInvoice(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lms_invoices")
    payment = models.OneToOneField(LmsPayment, on_delete=models.CASCADE, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default="paid")
    invoice_url = models.URLField(max_length=500, null=True, blank=True)
    
    billing_period_start = models.DateTimeField(null=True, blank=True)
    billing_period_end = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lms_invoices"
        app_label = "lms_financial"
