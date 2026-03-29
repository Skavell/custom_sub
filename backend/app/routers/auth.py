import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as _select

from app.database import get_db
from app.redis_client import get_redis
from app.schemas.auth import EmailRegisterRequest, EmailLoginRequest, TokenResponse
from app.services.auth.jwt_service import create_access_token, create_refresh_token, verify_token, TokenType
from app.services.auth.password_service import verify_password
from app.services.user_service import create_user_with_provider, get_user_by_email
from app.models.auth_provider import ProviderType
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_OPTS = {
    "httponly": True,
    "samesite": "strict",
    "secure": settings.is_production,
}


def _set_auth_cookies(response: Response, user_id: str) -> None:
    access = create_access_token(str(user_id))
    refresh = create_refresh_token(str(user_id))
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)


@router.post("/register", response_model=TokenResponse)
async def register_email(
    data: EmailRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    existing, _ = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await create_user_with_provider(
        db,
        display_name=data.display_name,
        provider=ProviderType.email,
        provider_user_id=data.email.lower(),
        password=data.password,
    )
    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/login", response_model=TokenResponse)
async def login_email(
    data: EmailLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, provider = await get_user_by_email(db, data.email)
    if not user or not provider or not provider.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(data.password, provider.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
):
    access_token = request.cookies.get("access_token")
    if access_token:
        await redis.setex(f"blacklist:{access_token}", settings.access_token_expire_minutes * 60, "1")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"ok": True}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = verify_token(token, TokenType.REFRESH)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Invalidate old refresh token (rotation)
    await redis.delete(f"refresh:{token[:32]}")

    user_id = payload["sub"]
    result = await db.execute(_select(User).where(User.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _set_auth_cookies(response, str(user.id))
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)
