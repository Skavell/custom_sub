from pydantic import BaseModel


class SubscriptionLinkResponse(BaseModel):
    subscription_url: str
