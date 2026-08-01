from django.db import models
import uuid


class CreditType(models.TextChoices):
    CREATOR_CREDIT = 'creator_credit', 'Creator Credit'
    FAN_CREDIT = 'fan_credit', 'Fan Credit'


class CreditTransactionType(models.TextChoices):
    PURCHASE = 'purchase', 'Purchase'
    ADMIN_GIFT = 'admin_gift', 'Admin Gift'
    MONTHLY_ALLOCATION = 'monthly_allocation', 'Monthly Allocation'
    SPENT = 'spent', 'Spent'
    EXPIRED = 'expired', 'Expired'
    REFUNDED = 'refunded', 'Refunded'
    CONVERTED = 'converted', 'Converted'
    ADJUSTMENT = 'adjustment', 'Adjustment'


class CreditTransactionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REVERSED = 'reversed', 'Reversed'


class CreditGiftStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    DELIVERED = 'delivered', 'Delivered'
    FAILED = 'failed', 'Failed'
    REVERSED = 'reversed', 'Reversed'


class CreditPackageTarget(models.TextChoices):
    CREATOR = 'creator', 'Creator'
    FAN = 'fan', 'Fan'
    BOTH = 'both', 'Both'


class GiftAnimationType(models.TextChoices):
    HEART = 'heart', 'Heart'
    STAR = 'star', 'Star'
    FIRE = 'fire', 'Fire'
    CROWN = 'crown', 'Crown'
    DIAMOND = 'diamond', 'Diamond'
    ROCKET = 'rocket', 'Rocket'
    CONFETTI = 'confetti', 'Confetti'
