import enum
from datetime import datetime, timedelta, timezone
from jose import ExpiredSignatureError, JWTError, jwt
from app.config import settings


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {"sub": user_id, "type": TokenType.ACCESS, "exp": expire},
        settings.secret_key,
        algorithm="HS256",
    )


def create_refresh_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    return jwt.encode(
        {"sub": user_id, "type": TokenType.REFRESH, "exp": expire},
        settings.secret_key,
        algorithm="HS256",
    )


def verify_token(token: str, expected_type: TokenType) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except ExpiredSignatureError:
        raise ValueError("Token expired")
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")

    if payload.get("type") != expected_type:
        raise ValueError(f"Invalid token type: expected {expected_type}")

    if not payload.get("sub"):
        raise ValueError("Token missing subject claim")

    return payload
