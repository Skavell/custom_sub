import uuid
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.redis_client import get_redis
from app.models.user import User
from app.services.auth.jwt_service import TokenType, verify_token

_401 = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers=_401)

    try:
        payload = verify_token(token, TokenType.ACCESS)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token", headers=_401)

    # Check blacklist
    if await redis.exists(f"blacklist:{token}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked", headers=_401)

    # Session version check — reject if password was changed after token was issued
    token_pwd_v = int(payload.get("pwd_v", 0))
    stored_raw = await redis.get(f"user_pwd_version:{payload['sub']}")
    stored_pwd_v = int(stored_raw) if stored_raw else 0
    if token_pwd_v != stored_pwd_v:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalidated", headers=_401)

    # payload["sub"] is guaranteed by verify_token, but UUID parse can still fail on malformed input
    try:
        user_uuid = uuid.UUID(payload["sub"])
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject", headers=_401)

    result = await db.execute(
        select(User).where(User.id == user_uuid).options(selectinload(User.auth_providers))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found", headers=_401)

    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return current_user
