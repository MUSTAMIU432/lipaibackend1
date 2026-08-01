import strawberry
from typing import Optional, List
from datetime import datetime
from ..models import VerificationDocument, KYCStatus, BusinessVerification

@strawberry.type
class VerificationDocumentType:
    id: strawberry.ID
    kycType: str
    documentType: Optional[str]
    documentName: Optional[str]
    documentNumber: Optional[str]
    documentExpiryDate: Optional[datetime]
    documentFileUrl: Optional[str]
    selfieUrl: Optional[str]
    tinNumber: Optional[str]
    status: str
    submittedAt: datetime

    @classmethod
    def from_model(cls, instance: VerificationDocument):
        return cls(
            id=strawberry.ID(str(instance.id)),
            kycType=instance.kyc_type,
            documentType=instance.document_type,
            documentName=instance.document_name,
            documentNumber=instance.document_number,
            documentExpiryDate=instance.document_expiry_date,
            documentFileUrl=instance.document_file_url,
            selfieUrl=instance.selfie_url,
            tinNumber=instance.tin_number,
            status=instance.status,
            submittedAt=instance.submitted_at,
        )

@strawberry.type
class BusinessVerificationType:
    id: strawberry.ID
    businessName: str
    businessType: str
    businessRegistrationNumber: str
    verificationStatus: str
    resubmissionCount: int
    createdAt: datetime
    representativeFirstName: str
    representativeLastName: str

    @classmethod
    def from_model(cls, instance: BusinessVerification):
        return cls(
            id=strawberry.ID(str(instance.id)),
            businessName=instance.business_name,
            businessType=instance.business_type,
            businessRegistrationNumber=instance.business_registration_number,
            verificationStatus=instance.verification_status,
            resubmissionCount=instance.resubmission_count,
            createdAt=instance.created_at,
            representativeFirstName=instance.representative_first_name,
            representativeLastName=instance.representative_last_name,
        )

@strawberry.type
class KYCStatusType:
    id: strawberry.ID
    creatorId: strawberry.ID
    kycType: str
    overallStatus: str
    resubmissionCount: int
    updatedAt: datetime
    currentDocument: Optional[VerificationDocumentType]
    businessDetail: Optional[BusinessVerificationType]

    @classmethod
    def from_model(cls, instance: KYCStatus):
        # We can fetch business detail via relation
        business = getattr(instance.creator, 'business_verification', None)
        return cls(
            id=strawberry.ID(str(instance.id)),
            creatorId=strawberry.ID(str(instance.creator_id)),
            kycType=instance.kyc_type,
            overallStatus=instance.overall_status,
            resubmissionCount=instance.resubmission_count,
            updatedAt=instance.updated_at,
            currentDocument=VerificationDocumentType.from_model(instance.current_document) if instance.current_document else None,
            businessDetail=BusinessVerificationType.from_model(business) if business else None
        )

@strawberry.input
class IndividualKYCInput:
    documentType: str
    documentNumber: str
    documentExpiryDate: datetime
    documentName: Optional[str] = None
    documentFileUrl: Optional[str] = None
    selfieUrl: Optional[str] = None
    tinNumber: Optional[str] = None
    tinCertificateUrl: Optional[str] = None

@strawberry.input
class FullBusinessKYCInput:
    businessName: str
    businessRegistrationNumber: str
    businessType: str
    representativeFirstName: str
    representativeLastName: str
    representativeRole: str
    businessRegistrationDocUrl: Optional[str] = None
    businessEmail: Optional[str] = None
    countryOfIncorporation: Optional[str] = None
    representativeIdDocumentUrl: Optional[str] = None
    representativeSelfieUrl: Optional[str] = None
