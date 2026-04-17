from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, Field


def validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Пароль должен содержать не менее 8 символов")
    if not any(c.isupper() for c in v):
        raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
    if not any(c.islower() for c in v):
        raise ValueError("Пароль должен содержать хотя бы одну строчную букву")
    if not any(c.isdigit() for c in v):
        raise ValueError("Пароль должен содержать хотя бы одну цифру")
    return v


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Display name cannot be empty")
        if len(v) > 64:
            raise ValueError("Display name must be 64 characters or less")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user_id: str
    display_name: str


class TelegramOAuthRequest(BaseModel):
    model_config = ConfigDict(extra='allow')

    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class GoogleOAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class VKOAuthRequest(BaseModel):
    code: str
    redirect_uri: str
    device_id: str
    state: str


class OAuthConfigResponse(BaseModel):
    google: bool
    google_client_id: str | None
    vk: bool
    vk_client_id: str | None
    telegram: bool
    telegram_bot_username: str | None
    email_enabled: bool
    support_telegram_url: str | None
    email_verification_required: bool = False


class LinkEmailRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ResetPasswordRequestSchema(BaseModel):
    email: EmailStr


class ResetPasswordConfirmSchema(BaseModel):
    token: str = Field(min_length=1)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)
