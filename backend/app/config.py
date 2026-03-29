from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str
    settings_encryption_key: str

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("settings_encryption_key")
    @classmethod
    def _validate_encryption_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SETTINGS_ENCRYPTION_KEY must be at least 32 characters")
        return v
    google_client_id: str = ""
    google_client_secret: str = ""
    vk_client_id: str = ""
    vk_client_secret: str = ""
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"

    # JWT
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
