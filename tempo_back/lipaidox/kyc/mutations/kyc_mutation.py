import strawberry
from django.db import transaction
from django.utils import timezone
from ..models import KYCStatus, VerificationDocument, DocumentStatus, KYCOverallStatus, KYCType, BusinessVerification, BusinessVerificationStatus, DocumentType
from lipaidox.creator_profile.models import CreatorProfile
from ..schema.kyc_schema import KYCStatusType, IndividualKYCInput, FullBusinessKYCInput
from multitenant.utils.tenant_context import get_current_tenant
from lipaidox.auth.permissions import require_creator


def _normalize_document_type(raw: str) -> str:
    """Map any frontend display string to the backend DocumentType enum value."""
    if not raw:
        return DocumentType.PASSPORT
    # Already a valid enum value — pass through
    if raw in DocumentType.values:
        return raw
    mapping = {
        "passport": DocumentType.PASSPORT,
        "national id": DocumentType.NATIONAL_ID,
        "national_id": DocumentType.NATIONAL_ID,
        "nationalid": DocumentType.NATIONAL_ID,
        "id card": DocumentType.NATIONAL_ID,
        "id_card": DocumentType.NATIONAL_ID,
        "driver license": DocumentType.DRIVER_LICENSE,
        "driver_license": DocumentType.DRIVER_LICENSE,
        "drivers license": DocumentType.DRIVER_LICENSE,
        "drivers_license": DocumentType.DRIVER_LICENSE,
        "driving license": DocumentType.DRIVER_LICENSE,
        "other": "other",
    }
    return mapping.get(raw.lower().strip(), DocumentType.PASSPORT)


def _normalize_business_type(raw: str) -> str:
    """Map any frontend business type string to the backend BusinessVerification enum value."""
    if not raw:
        return "limited_liability_company"
    mapping = {
        "company": "limited_liability_company",
        "limited_liability_company": "limited_liability_company",
        "llc": "limited_liability_company",
        "partnership": "partnership",
        "sole_trader": "sole_proprietorship",
        "sole_proprietorship": "sole_proprietorship",
        "sole trader": "sole_proprietorship",
        "ngo": "non_profit",
        "non_profit": "non_profit",
        "nonprofit": "non_profit",
        "non profit": "non_profit",
        "corporation": "corporation",
        "agency": "agency",
        "enterprise": "enterprise",
        "other": "other",
    }
    return mapping.get(raw.lower().strip(), "limited_liability_company")

@strawberry.type
class KYCMutation:
    @strawberry.mutation
    @require_creator
    def submit_individual_kyc(self, info: strawberry.types.Info, input: IndividualKYCInput) -> KYCStatusType:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()
        
        with transaction.atomic():
            kyc_status, created = KYCStatus.objects.get_or_create(
                creator=profile,
                tenant=tenant
            )
            
            if kyc_status.overall_status == KYCOverallStatus.PERMANENTLY_REJECTED:
                raise Exception("You have been permanently rejected.")

            # Validate Other requires a document name
            normalized_doc_type = _normalize_document_type(input.documentType)
            if normalized_doc_type == "other" and not (getattr(input, "documentName", None) or "").strip():
                raise Exception("Document name is required when document type is 'Other'.")

            doc = VerificationDocument.objects.create(
                creator=profile,
                tenant=tenant,
                kyc_type=KYCType.INDIVIDUAL,
                document_type=normalized_doc_type if normalized_doc_type != "other" else None,
                document_name=getattr(input, "documentName", None) or None,
                document_number=input.documentNumber,
                document_expiry_date=input.documentExpiryDate,
                document_file_url=input.documentFileUrl,
                selfie_url=input.selfieUrl,
                tin_number=input.tinNumber,
                tin_certificate_url=input.tinCertificateUrl,
                status=DocumentStatus.PENDING
            )
            
            kyc_status.kyc_type = KYCType.INDIVIDUAL
            kyc_status.overall_status = KYCOverallStatus.PENDING
            kyc_status.current_document = doc
            kyc_status.save()
            
        return KYCStatusType.from_model(kyc_status)

    @strawberry.mutation
    @require_creator
    def submit_business_kyc_full(self, info: strawberry.types.Info, input: FullBusinessKYCInput) -> KYCStatusType:
        user = info.context.request.user
        # Role validation handled by @require_creator decorator

        profile = CreatorProfile.objects.get(user=user)
        tenant = get_current_tenant()
        
        with transaction.atomic():
            # 1. Update/Create KYC Status
            kyc_status, created = KYCStatus.objects.get_or_create(
                creator=profile,
                tenant=tenant
            )
            
            # 2. Create foundational VerificationDocument record (Module 5)
            doc = VerificationDocument.objects.create(
                creator=profile,
                tenant=tenant,
                kyc_type=KYCType.BUSINESS,
                business_name=input.businessName,
                business_registration_number=input.businessRegistrationNumber,
                business_registration_doc_url=input.businessRegistrationDocUrl,
                status=DocumentStatus.PENDING
            )
            
            # 3. Create/Update rich BusinessVerification record (Module 6)
            business_verification, bv_created = BusinessVerification.objects.update_or_create(
                creator=profile,
                tenant=tenant,
                defaults={
                    "business_name": input.businessName,
                    "business_type": _normalize_business_type(input.businessType),
                    "business_registration_number": input.businessRegistrationNumber,
                    "business_registration_doc_url": input.businessRegistrationDocUrl,
                    "business_email": input.businessEmail,
                    "country_of_incorporation": input.countryOfIncorporation,
                    "representative_first_name": input.representativeFirstName,
                    "representative_last_name": input.representativeLastName,
                    "representative_role": input.representativeRole,
                    "representative_id_document_url": input.representativeIdDocumentUrl,
                    "representative_selfie_url": input.representativeSelfieUrl,
                    "verification_status": BusinessVerificationStatus.PENDING,
                    "first_submitted_at": timezone.now() if not kyc_status.first_submitted_at else kyc_status.first_submitted_at
                }
            )
            
            # 4. Finalize KYC Status
            kyc_status.kyc_type = KYCType.BUSINESS
            kyc_status.overall_status = KYCOverallStatus.PENDING
            kyc_status.current_document = doc
            if not created:
                kyc_status.resubmission_count += 1
            kyc_status.save()
            
        return KYCStatusType.from_model(kyc_status)
