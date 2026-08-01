import uuid
from django.db import models
from multitenant.models import TenantAwareModel


class ClearingJobStatus(models.TextChoices):
    """Status of wallet clearing jobs"""
    SCHEDULED = 'scheduled', 'Scheduled'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class WalletClearingJob(TenantAwareModel):
    """
    Tracks background jobs that move money from pending_balance to available_balance
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        'lipaidox_wallet.CreatorWallet',
        on_delete=models.CASCADE,
        related_name='clearing_jobs'
    )
    wallet_transaction = models.ForeignKey(
        'lipaidox_wallet.WalletTransaction',
        on_delete=models.CASCADE,
        related_name='clearing_jobs'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='wallet_clearing_jobs'
    )
    amount = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(
        max_length=20,
        choices=ClearingJobStatus.choices,
        default=ClearingJobStatus.SCHEDULED
    )
    scheduled_clear_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wallet_clearing_jobs'
        app_label = 'lipaidox_wallet'
        ordering = ['scheduled_clear_at']
        indexes = [
            models.Index(fields=['wallet'], name='idx_clearing_wallet'),
            models.Index(fields=['creator'], name='idx_clearing_creator'),
            models.Index(fields=['status'], name='idx_clearing_status'),
            models.Index(fields=['scheduled_clear_at'], name='idx_clearing_scheduled'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='clearing_amount_check'),
        ]

    def __str__(self):
        return f"Clearing Job: {self.creator.username} - {self.amount} {self.currency}"

    def start_processing(self):
        """Mark job as processing"""
        from django.utils import timezone
        self.status = ClearingJobStatus.PROCESSING
        self.save()

    def complete_job(self):
        """Complete the clearing job"""
        from django.utils import timezone
        
        try:
            # Clear the pending balance
            self.wallet.clear_pending_balance(self.amount)
            
            # Mark wallet transaction as cleared
            self.wallet_transaction.mark_cleared()
            
            # Mark job as completed
            self.status = ClearingJobStatus.COMPLETED
            self.processed_at = timezone.now()
            self.save()
            
            return True
        except Exception as e:
            self.fail_job(str(e))
            return False

    def fail_job(self, failure_reason):
        """Mark job as failed"""
        from django.utils import timezone
        self.status = ClearingJobStatus.FAILED
        self.failure_reason = failure_reason
        self.processed_at = timezone.now()
        self.save()

    def cancel_job(self):
        """Cancel the clearing job"""
        from django.utils import timezone
        self.status = ClearingJobStatus.CANCELLED
        self.processed_at = timezone.now()
        self.save()

    @classmethod
    def schedule_clearing_job(cls, wallet_transaction):
        """Schedule a clearing job for a pending wallet transaction"""
        if wallet_transaction.balance_type != 'pending':
            raise ValueError("Can only schedule clearing jobs for pending transactions")
        
        if not wallet_transaction.clears_at:
            raise ValueError("Transaction must have a clear date")
        
        return cls.objects.create(
            wallet=wallet_transaction.wallet,
            wallet_transaction=wallet_transaction,
            creator=wallet_transaction.creator,
            tenant=wallet_transaction.tenant,
            amount=wallet_transaction.amount,
            currency=wallet_transaction.currency,
            scheduled_clear_at=wallet_transaction.clears_at
        )

    @classmethod
    def get_pending_jobs(cls):
        """Get jobs that are ready to be processed"""
        from django.utils import timezone
        return cls.objects.filter(
            status=ClearingJobStatus.SCHEDULED,
            scheduled_clear_at__lte=timezone.now()
        ).order_by('scheduled_clear_at')

    @classmethod
    def process_pending_jobs(cls):
        """Process all pending clearing jobs"""
        processed_count = 0
        failed_count = 0
        
        for job in cls.get_pending_jobs():
            job.start_processing()
            if job.complete_job():
                processed_count += 1
            else:
                failed_count += 1
        
        return {
            'processed': processed_count,
            'failed': failed_count,
            'total': processed_count + failed_count
        }
