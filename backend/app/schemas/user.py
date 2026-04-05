from datetime import datetime
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    type: str
    username: str | None
    identifier: str | None = None  # display: email for email, @handle for telegram, email for google


class UserProfileResponse(BaseModel):
    id: str
    display_name: str
    is_admin: bool
    created_at: datetime
    providers: list[ProviderInfo]
    email_verified: bool | None = None
