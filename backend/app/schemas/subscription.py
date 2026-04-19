from datetime import datetime
from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    type: str
    status: str
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None
    days_remaining: int
    has_connected: bool
    traffic_used_bytes: int | None


class TrialActivateResponse(BaseModel):
    subscription: SubscriptionResponse
    message: str
