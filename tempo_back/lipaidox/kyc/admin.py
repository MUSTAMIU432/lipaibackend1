"""
Django admin for identity verification — https://<backend>/admin/

Reviewers open an application, check the document and selfie links, then use
the "Approve" or "Ask to resubmit" action. Approving grants the verification
badge (see `kyc/services.py`).
"""
from django.contrib import admin, messages
from django.utils.html import format_html

from lipaidox.kyc.models.kyc_status import KYCOverallStatus, KYCRejectionReason, KYCStatus
from lipaidox.kyc.services import approve_kyc, request_kyc_resubmission


def _link(url, label):
    return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, label) if url else "—"


@admin.register(KYCStatus)
class KYCStatusAdmin(admin.ModelAdmin):
    list_display = ("creator_username", "kyc_type", "overall_status", "document", "first_submitted_at", "reviewed_at")
    list_filter = ("overall_status", "kyc_type")
    search_fields = ("creator__user__username", "creator__user__email", "current_document__document_number")
    ordering = ("-updated_at",)
    readonly_fields = (
        "creator",
        "current_document",
        "document_file",
        "selfie",
        "document_details",
        "reviewed_by",
        "reviewed_at",
        "approved_at",
        "first_submitted_at",
        "created_at",
        "updated_at",
    )
    fields = (
        "creator",
        "kyc_type",
        "overall_status",
        "document_details",
        "document_file",
        "selfie",
        "rejection_reason",
        "rejection_note",
        "reviewed_by",
        "reviewed_at",
        "approved_at",
        "first_submitted_at",
        "created_at",
        "updated_at",
    )
    actions = ("approve", "ask_to_resubmit")

    @admin.display(description="Creator", ordering="creator__user__username")
    def creator_username(self, obj):
        return obj.creator.user.username

    @admin.display(description="Document")
    def document(self, obj):
        d = obj.current_document
        return f"{d.get_document_type_display() if d.document_type else d.document_name or '—'} · {d.document_number or '—'}" if d else "—"

    @admin.display(description="Document details")
    def document_details(self, obj):
        d = obj.current_document
        if not d:
            return "—"
        return format_html(
            "{}<br>Number: {}<br>Expires: {}<br>TIN: {}",
            d.get_document_type_display() if d.document_type else (d.document_name or "—"),
            d.document_number or "—",
            d.document_expiry_date or "—",
            d.tin_number or "—",
        )

    @admin.display(description="ID document")
    def document_file(self, obj):
        return _link(obj.current_document and obj.current_document.document_file_url, "Open ID photo")

    @admin.display(description="Selfie")
    def selfie(self, obj):
        return _link(obj.current_document and obj.current_document.selfie_url, "Open selfie")

    @admin.action(description="Approve — grant the verification badge")
    def approve(self, request, queryset):
        for kyc in queryset.select_related("creator", "current_document"):
            approve_kyc(kyc, reviewer=request.user)
        self.message_user(request, f"Approved {queryset.count()} verification(s).", messages.SUCCESS)

    @admin.action(description="Ask to resubmit (document unclear or invalid)")
    def ask_to_resubmit(self, request, queryset):
        for kyc in queryset.select_related("current_document"):
            request_kyc_resubmission(kyc, reviewer=request.user, reason=KYCRejectionReason.INCOMPLETE_SUBMISSION)
        self.message_user(request, f"Asked {queryset.count()} creator(s) to resubmit.", messages.WARNING)

    def save_model(self, request, obj, form, change):
        # Setting the status to Approved by hand must grant the badge too.
        if change and "overall_status" in form.changed_data and obj.overall_status == KYCOverallStatus.APPROVED:
            approve_kyc(obj, reviewer=request.user)
            return
        super().save_model(request, obj, form, change)
