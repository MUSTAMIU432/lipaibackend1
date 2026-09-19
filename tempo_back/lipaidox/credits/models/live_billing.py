"""
Live-session billing records.

A `LiveCreditReservation` holds credits for one live stream while it runs. The
server — never the client — decides how much time has elapsed, so a modified app
can't under-report. `LiveBillingEvent` is the heartbeat log: one row per accepted
heartbeat, unique per (reservation, sequence) so a retried or replayed heartbeat
can't be billed twice.
"""
import uuid

from django.db import models

CREDIT_PLACES = 6


class ReservationStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    SETTLED = 'settled', 'Settled'


class LiveEndReason(models.TextChoices):
    CREATOR_ENDED = 'creator_ended', 'Creator ended'
    CREDIT_EXHAUSTED = 'credit_exhausted', 'Credits exhausted'
    FORCED_ENDED = 'forced_ended', 'Ended by an administrator'
    CONNECTION_LOST = 'connection_lost', 'Connection lost'


class LiveCreditReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        'lipaidox_credits.CreatorCreditWallet', on_delete=models.PROTECT, related_name='reservations'
    )
    creator = models.ForeignKey(
        'lipaidox_creator_profile.CreatorProfile', on_delete=models.CASCADE, related_name='live_credit_reservations'
    )
    # One reservation per stream.
    live_stream = models.OneToOneField(
        'lipaidox_live_streaming.LiveStream', on_delete=models.CASCADE, related_name='credit_reservation'
    )

    credits_reserved = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    credits_consumed = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    credits_released = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)

    status = models.CharField(max_length=20, choices=ReservationStatus.choices, default=ReservationStatus.ACTIVE)
    end_reason = models.CharField(max_length=30, choices=LiveEndReason.choices, blank=True, default='')

    # Server clock, authoritative for billing.
    started_at = models.DateTimeField()
    last_heartbeat_at = models.DateTimeField()
    last_sequence = models.IntegerField(default=0)
    billed_seconds = models.IntegerField(default=0)

    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'live_credit_reservations'
        indexes = [
            models.Index(fields=['status'], name='idx_live_resv_status'),
            models.Index(fields=['creator', 'status'], name='idx_live_resv_creator_status'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(credits_reserved__gte=0), name='live_resv_reserved_check'),
            models.CheckConstraint(check=models.Q(credits_consumed__gte=0), name='live_resv_consumed_check'),
            models.CheckConstraint(
                check=models.Q(credits_consumed__lte=models.F('credits_reserved')),
                name='live_resv_consumed_within_reserved_check',
            ),
            # A creator can only have one live session holding credits at a time.
            models.UniqueConstraint(
                fields=['creator'], condition=models.Q(status='active'), name='live_resv_one_active_per_creator'
            ),
        ]

    def __str__(self):
        return f"Reservation {self.credits_consumed}/{self.credits_reserved} ({self.status})"


class LiveBillingEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        LiveCreditReservation, on_delete=models.CASCADE, related_name='billing_events'
    )
    creator = models.ForeignKey('lipaidox_creator_profile.CreatorProfile', on_delete=models.CASCADE)
    event_sequence = models.IntegerField()
    # Cumulative — the elapsed time and credits billed as of this heartbeat.
    elapsed_seconds = models.IntegerField()
    credits_consumed = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES)
    credits_delta = models.DecimalField(max_digits=20, decimal_places=CREDIT_PLACES, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'live_billing_events'
        ordering = ['event_sequence']
        constraints = [
            models.UniqueConstraint(fields=['reservation', 'event_sequence'], name='live_billing_event_unique_seq'),
        ]
