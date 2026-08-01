from django.db import models

class CreatorPlanTier(models.TextChoices):
    FREE = 'free', 'Free'
    PREMIUM = 'premium', 'Premium'
    PROMAX = 'promax', 'Promax+'

class CreatorPlanStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    CANCELLED = 'cancelled', 'Cancelled'
    EXPIRED = 'expired', 'Expired'
    PAST_DUE = 'past_due', 'Past Due'
    PENDING = 'pending', 'Pending'

class PlanPaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'

class PlanPaymentType(models.TextChoices):
    INITIAL = 'initial', 'Initial'
    RENEWAL = 'renewal', 'Renewal'
    RETRY = 'retry', 'Retry'
    UPGRADE = 'upgrade', 'Upgrade'
    CREDIT_TOP_UP = 'credit_top_up', 'Credit Top Up'
