from pydantic import BaseModel, EmailStr, field_validator


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user_id: str
    display_name: str


class TelegramOAuthRequest(BaseModel):
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
