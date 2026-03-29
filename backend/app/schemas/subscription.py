from datetime import datetime
from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    type: str            # "trial" | "paid"
    status: str          # "active" | "expired" | "disabled"
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None   # None = unlimited
    days_remaining: int


class TrialActivateResponse(BaseModel):
    subscription: SubscriptionResponse
    message: str
