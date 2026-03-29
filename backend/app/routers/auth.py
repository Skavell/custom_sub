import logging
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as _select

from app.database import get_db
from app.redis_client import get_redis
from app.schemas.auth import EmailRegisterRequest, EmailLoginRequest, TokenResponse, TelegramOAuthRequest, GoogleOAuthRequest, VKOAuthRequest
from app.services.auth.jwt_service import create_access_token, create_refresh_token, verify_token, TokenType
from app.services.auth.password_service import verify_password
from app.services.user_service import create_user_with_provider, get_user_by_email, get_user_by_provider
from app.models.auth_provider import ProviderType
from app.models.user import User
from app.config import settings
from app.services.auth.oauth.telegram import verify_telegram_data, parse_telegram_user
from app.services.auth.oauth.google import exchange_google_code
from app.services.auth.oauth.vk import exchange_vk_code
from app.services.setting_service import get_setting, get_setting_decrypted

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


async def _sync_remnawave_on_first_telegram_login(
    db: AsyncSession, user: "User", telegram_id: int
) -> None:
    """Best-effort: look up user in Remnawave by Telegram ID and sync subscription.
    Failures are logged and swallowed — the auth flow must not be blocked by this.
    """
    import uuid as _uuid2
    try:
        remnawave_url = await get_setting(db, "remnawave_url")
        remnawave_token = await get_setting_decrypted(db, "remnawave_token")
        if not remnawave_url or not remnawave_token:
            return  # Not configured — skip silently

        from app.services.remnawave_client import RemnawaveClient
        from app.services.subscription_service import sync_subscription_from_remnawave

        rw_client = RemnawaveClient(remnawave_url, remnawave_token)
        rw_user = await rw_client.get_user_by_telegram_id(telegram_id)
        if rw_user is None:
            return  # Not found in Remnawave — new user with no prior subscription

        user.remnawave_uuid = _uuid2.UUID(rw_user.id)
        await db.commit()
        await sync_subscription_from_remnawave(db, user, rw_user)
    except Exception as exc:
        logger.warning("Remnawave sync on first Telegram login failed (non-blocking): %s", exc)

COOKIE_OPTS = {
    "httponly": True,
    "samesite": "strict",
    "secure": settings.is_production,
}


async def _set_auth_cookies(response: Response, user_id: str, redis: Redis) -> None:
    """Issue access + refresh tokens, store refresh jti in Redis for rotation."""
    access = create_access_token(str(user_id))
    refresh, jti = create_refresh_token(str(user_id))
    await redis.setex(
        f"refresh_jti:{jti}",
        settings.refresh_token_expire_days * 86400,
        str(user_id),
    )
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)


@router.post("/register", response_model=TokenResponse)
async def register_email(
    data: EmailRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
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
    await _set_auth_cookies(response, str(user.id), redis)
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/login", response_model=TokenResponse)
async def login_email(
    data: EmailLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user, provider = await get_user_by_email(db, data.email)
    if not user or not provider or not provider.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(data.password, provider.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await _set_auth_cookies(response, str(user.id), redis)
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
    response.delete_cookie("access_token", samesite="strict", httponly=True, secure=settings.is_production)
    response.delete_cookie("refresh_token", samesite="strict", httponly=True, secure=settings.is_production)
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

    jti = payload.get("jti")
    if not jti or not await redis.exists(f"refresh_jti:{jti}"):
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    # Invalidate old jti before issuing new tokens (rotation)
    await redis.delete(f"refresh_jti:{jti}")

    try:
        user_uuid = _uuid.UUID(payload["sub"])
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    result = await db.execute(_select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    await _set_auth_cookies(response, str(user.id), redis)
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/oauth/telegram", response_model=TokenResponse)
async def oauth_telegram(
    data: TelegramOAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    bot_token = await get_setting(db, "telegram_bot_token")
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram OAuth not configured")
    try:
        raw = data.model_dump(exclude_none=True)
        verify_telegram_data(raw, bot_token=bot_token)
        tg_user = parse_telegram_user(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = await get_user_by_provider(db, ProviderType.telegram, str(tg_user.id))
    if not user:
        display_name = tg_user.first_name
        if tg_user.last_name:
            display_name += f" {tg_user.last_name}"
        user = await create_user_with_provider(
            db,
            display_name=display_name,
            provider=ProviderType.telegram,
            provider_user_id=str(tg_user.id),
            avatar_url=tg_user.photo_url,
            provider_username=tg_user.username,
        )
        # Fail-silent Remnawave sync: try to find prior subscription by Telegram ID
        await _sync_remnawave_on_first_telegram_login(db, user, tg_user.id)

    await _set_auth_cookies(response, str(user.id), redis)
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(
    data: GoogleOAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    try:
        g_user = await exchange_google_code(data.code, data.redirect_uri)
    except Exception as exc:
        logger.exception("Google OAuth exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="Google OAuth failed")

    user = await get_user_by_provider(db, ProviderType.google, g_user.id)
    if not user:
        user = await create_user_with_provider(
            db,
            display_name=g_user.name,
            provider=ProviderType.google,
            provider_user_id=g_user.id,
            avatar_url=g_user.picture,
        )

    await _set_auth_cookies(response, str(user.id), redis)
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)


@router.post("/oauth/vk", response_model=TokenResponse)
async def oauth_vk(
    data: VKOAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    try:
        vk_user = await exchange_vk_code(data.code, data.redirect_uri, data.device_id, data.state)
    except Exception as exc:
        logger.exception("VK OAuth exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail="VK OAuth failed")

    user = await get_user_by_provider(db, ProviderType.vk, vk_user.id)
    if not user:
        user = await create_user_with_provider(
            db,
            display_name=f"{vk_user.first_name} {vk_user.last_name}".strip(),
            provider=ProviderType.vk,
            provider_user_id=vk_user.id,
            avatar_url=vk_user.avatar,
        )

    await _set_auth_cookies(response, str(user.id), redis)
    return TokenResponse(user_id=str(user.id), display_name=user.display_name)
