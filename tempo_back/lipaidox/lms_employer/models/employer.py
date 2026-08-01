import uuid
from django.db import models
from django.conf import settings
from multitenant.models import TenantAwareModel

class CompanySize(models.TextChoices):
    STARTUP = 'startup', 'Startup (1-10)'
    SMALL = 'small', 'Small (11-50)'
    MEDIUM = 'medium', 'Medium (51-200)'
    LARGE = 'large', 'Large (201-1000)'
    ENTERPRISE = 'enterprise', 'Enterprise (1000+)'

class Industry(models.TextChoices):
    TECHNOLOGY = 'technology', 'Technology'
    HEALTHCARE = 'healthcare', 'Healthcare'
    FINANCE = 'finance', 'Finance'
    EDUCATION = 'education', 'Education'
    RETAIL = 'retail', 'Retail'
    MANUFACTURING = 'manufacturing', 'Manufacturing'
    CONSULTING = 'consulting', 'Consulting'
    MEDIA = 'media', 'Media'
    NONPROFIT = 'nonprofit', 'Non-Profit'
    GOVERNMENT = 'government', 'Government'
    OTHER = 'other', 'Other'

class EmployerProfile(TenantAwareModel):
    """
    Employer company profiles
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employer_profile"
    )
    
    # Company Information
    company_name = models.CharField(max_length=255)
    industry = models.CharField(
        max_length=20,
        choices=Industry.choices,
        default=Industry.OTHER
    )
    company_size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        default=CompanySize.SMALL
    )
    
    # Description
    description = models.TextField()
    mission = models.TextField(null=True, blank=True)
    values = models.JSONField(default=list, blank=True)  # List of company values
    
    # Branding
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    website = models.URLField(max_length=500, null=True, blank=True)
    
    # Location
    headquarters = models.CharField(max_length=255, null=True, blank=True)
    locations = models.JSONField(default=list, blank=True)  # List of office locations
    
    # Social Media
    linkedin_url = models.URLField(max_length=500, null=True, blank=True)
    twitter_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Recruitment Info
    hr_contact_email = models.EmailField(null=True, blank=True)
    recruitment_team_size = models.IntegerField(default=1)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Stats (Denormalized)
    total_job_postings = models.IntegerField(default=0)
    active_job_postings = models.IntegerField(default=0)
    total_applications = models.IntegerField(default=0)
    
    # Subscription/Plan
    plan_type = models.CharField(max_length=50, default='free')  # free, premium, enterprise
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_employer_profiles"
        app_label = "lms_employer"
        indexes = [
            models.Index(fields=['company_name'], name='idx_emp_company_name'),
            models.Index(fields=['industry'], name='idx_emp_industry'),
            models.Index(fields=['company_size'], name='idx_emp_size'),
            models.Index(fields=['is_verified'], name='idx_emp_verified'),
            models.Index(fields=['-created_at'], name='idx_emp_created'),
        ]
    
    def __str__(self):
        return self.company_name
    
    def can_post_jobs(self):
        """Check if employer can post jobs based on plan"""
        if self.plan_type == 'free':
            return self.active_job_postings < 3  # Free tier: 3 active jobs
        elif self.plan_type == 'premium':
            return self.active_job_postings < 20  # Premium tier: 20 active jobs
        else:  # enterprise
            return True  # Unlimited
    
    def update_stats(self):
        """Update denormalized stats"""
        from lipaidox.lms_careers.models import JobListing, JobApplication
        
        self.total_job_postings = JobListing.objects.filter(employer=self).count()
        self.active_job_postings = JobListing.objects.filter(
            employer=self, 
            status='active'
        ).count()
        self.total_applications = JobApplication.objects.filter(
            job_listing__employer=self
        ).count()
        self.save()

class TalentPoolSearch(TenantAwareModel):
    """
    Employer talent pool search history
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="talent_searches"
    )
    
    # Search criteria
    filters_json = models.JSONField(default=dict)  # Search filters as JSON
    search_query = models.CharField(max_length=255, null=True, blank=True)
    
    # Results
    results_count = models.IntegerField(default=0)
    saved_profiles = models.JSONField(default=list, blank=True)  # Saved student profile IDs
    
    # Timestamps
    searched_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "lms_talent_pool_searches"
        app_label = "lms_employer"
        indexes = [
            models.Index(fields=['employer'], name='idx_search_employer'),
            models.Index(fields=['-searched_at'], name='idx_search_date'),
        ]
    
    def __str__(self):
        return f"Search by {self.employer.company_name} at {self.searched_at}"

class ContactStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    RESPONDED = 'responded', 'Responded'

class EmployerStudentContact(TenantAwareModel):
    """
    Employer to student contact requests/messages
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="student_contacts"
    )
    student = models.ForeignKey(
        "lms_identity.StudentProfile",
        on_delete=models.CASCADE,
        related_name="employer_contacts"
    )
    
    # Communication
    message = models.TextField()
    job_listing = models.ForeignKey(
        "lms_careers.JobListing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_contacts"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=ContactStatus.choices,
        default=ContactStatus.PENDING
    )
    
    # Response
    student_response = models.TextField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    source = models.CharField(max_length=50, default='talent_search')  # talent_search, job_application, direct
    priority = models.CharField(max_length=20, default='normal')  # low, normal, high
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_employer_student_contacts"
        app_label = "lms_employer"
        unique_together = ('employer', 'student')
        indexes = [
            models.Index(fields=['employer'], name='idx_contact_employer'),
            models.Index(fields=['student'], name='idx_contact_student'),
            models.Index(fields=['status'], name='idx_contact_status'),
            models.Index(fields=['-created_at'], name='idx_contact_created'),
        ]
    
    def __str__(self):
        return f"{self.employer.company_name} → {self.student.user.username}"
    
    def respond(self, response_text):
        """Student responds to contact request"""
        from django.utils import timezone
        self.student_response = response_text
        self.status = ContactStatus.RESPONDED
        self.responded_at = timezone.now()
        self.save()
    
    def accept(self):
        """Employer accepts student response"""
        self.status = ContactStatus.ACCEPTED
        self.save()
    
    def reject(self):
        """Employer rejects student response"""
        self.status = ContactStatus.REJECTED
        self.save()

class EmployerDashboardStats(TenantAwareModel):
    """
    Cached dashboard statistics for employers
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    employer = models.OneToOneField(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="dashboard_stats"
    )
    
    # Job Statistics
    total_views = models.IntegerField(default=0)
    total_applications = models.IntegerField(default=0)
    pending_applications = models.IntegerField(default=0)
    hired_count = models.IntegerField(default=0)
    
    # Talent Pool Statistics
    profile_views = models.IntegerField(default=0)
    contacts_sent = models.IntegerField(default=0)
    contacts_accepted = models.IntegerField(default=0)
    
    # Engagement Metrics
    avg_response_time_hours = models.FloatField(default=0)
    conversion_rate = models.FloatField(default=0)  # Applications to hires
    
    # Period
    stats_period_start = models.DateTimeField()
    stats_period_end = models.DateTimeField()
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "lms_employer_dashboard_stats"
        app_label = "lms_employer"
        indexes = [
            models.Index(fields=['employer'], name='idx_stats_employer'),
            models.Index(fields=['stats_period_start'], name='idx_stats_period'),
        ]
    
    def __str__(self):
        return f"Stats for {self.employer.company_name}"
    
    @classmethod
    def update_stats(cls, employer):
        """Update dashboard statistics for employer"""
        from lipaidox.lms_careers.models import JobListing, JobApplication
        from django.utils import timezone
        from datetime import timedelta
        
        # Get or create stats record
        stats, created = cls.objects.get_or_create(
            employer=employer,
            defaults={
                'stats_period_start': timezone.now() - timedelta(days=30),
                'stats_period_end': timezone.now(),
            }
        )
        
        # Calculate statistics
        stats.total_applications = JobApplication.objects.filter(
            job_listing__employer=employer
        ).count()
        
        stats.pending_applications = JobApplication.objects.filter(
            job_listing__employer=employer,
            status='pending'
        ).count()
        
        stats.contacts_sent = EmployerStudentContact.objects.filter(
            employer=employer
        ).count()
        
        stats.contacts_accepted = EmployerStudentContact.objects.filter(
            employer=employer,
            status=ContactStatus.ACCEPTED
        ).count()
        
        stats.save()
        return stats
