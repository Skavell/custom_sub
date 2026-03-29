from datetime import datetime
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    type: str
    username: str | None


class UserProfileResponse(BaseModel):
    id: str
    display_name: str
    is_admin: bool
    created_at: datetime
    providers: list[ProviderInfo]
