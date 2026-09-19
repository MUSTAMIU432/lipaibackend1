"""
Financial audit trail (PRD §75): who did what to which money-related record.

Append-only by convention — nothing in the codebase updates or deletes a row, and
the API exposes read access only. (The older `admin_panel.AuditLog` model was never
migrated and nothing writes to it, so this is the working audit log.)
"""
import uuid

from django.db import models


class FinancialAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        'lipaidox_auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_audit_entries'
    )
    # e.g. ADMIN_CREDIT_ADJUSTMENT, LIVE_FORCE_ENDED, CREDIT_PACKAGE_UPDATED
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=50)
    entity_id = models.UUIDField(null=True, blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'financial_audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action'], name='idx_fin_audit_action'),
            models.Index(fields=['entity_type', 'entity_id'], name='idx_fin_audit_entity'),
            models.Index(fields=['-created_at'], name='idx_fin_audit_created'),
        ]
