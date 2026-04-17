from pydantic import BaseModel, field_validator
from datetime import datetime
from app.schemas.auth import validate_password_strength


class ProviderInfo(BaseModel):
    type: str
    username: str | None
    identifier: str | None = None


class UserProfileResponse(BaseModel):
    id: str
    display_name: str
    is_admin: bool
    has_made_payment: bool
    created_at: datetime
    providers: list[ProviderInfo]
    email_verified: bool | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UpdateDisplayNameRequest(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Имя не может быть пустым")
        if len(v) > 64:
            raise ValueError("Имя не может быть длиннее 64 символов")
        return v
