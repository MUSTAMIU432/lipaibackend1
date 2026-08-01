import strawberry
from typing import List, Optional
from ..models.plan import LmsPlan

@strawberry.type
class LmsPlanNode:
    id: strawberry.ID
    name: str
    description: Optional[str]
    price: float
    currency: str
    interval: str
    features: List[str]
    stripePriceId: Optional[str]

    @classmethod
    def from_model(cls, instance: LmsPlan):
        return cls(
            id=strawberry.ID(str(instance.id)),
            name=instance.name,
            description=instance.description,
            price=float(instance.price),
            currency=instance.currency,
            interval=instance.interval,
            features=instance.features or [],
            stripePriceId=instance.stripe_price_id,
        )
