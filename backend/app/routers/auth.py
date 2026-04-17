import logging
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as _select

from app.database import get_db
from app.redis_client import get_redis
from app.schemas.auth import EmailRegisterRequest, EmailLoginRequest, TokenResponse, TelegramOAuthRequest, GoogleOAuthRequest, VKOAuthRequest, OAuthConfigResponse
from app.services.auth.jwt_service import create_access_token, create_refresh_token, verify_token, TokenType
from app.services.auth.password_service import verify_password
from app.services.user_service import create_user_with_provider, get_user_by_email, get_user_by_provider
from app.models.auth_provider import ProviderType
from app.models.user import User
from app.config import settings
from app.deps import get_current_user
from app.services.auth.oauth.telegram import verify_telegram_data, parse_telegram_user
from app.services.auth.oauth.google import exchange_google_code
from app.services.auth.oauth.vk import exchange_vk_code
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.email_service import send_verification_email
from app.services.rate_limiter import check_rate_limit
from app.models.auth_provider import AuthProvider

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
    raw = await redis.get(f"user_pwd_version:{user_id}")
    pwd_v = int(raw) if raw else 0
    access = create_access_token(user_id, pwd_v=pwd_v)
    refresh, jti = create_refresh_token(user_id, pwd_v=pwd_v)
    await redis.setex(
        f"refresh_jti:{jti}",
        settings.refresh_token_expire_days * 86400,
        user_id,
    )
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)


@router.get("/oauth-config", response_model=OAuthConfigResponse)
async def get_oauth_config(
    db: AsyncSession = Depends(get_db),
) -> OAuthConfigResponse:
    """Public endpoint — returns which OAuth providers are configured."""
    # Google: DB setting takes priority over env var
    google_client_id = await get_setting(db, "google_client_id") or settings.google_client_id or None
    google_enabled_flag = await get_setting(db, "google_enabled")
    google_active = (google_enabled_flag != "false") and bool(google_client_id)

    # VK: DB setting takes priority over env var
    vk_client_id = await get_setting(db, "vk_client_id") or settings.vk_client_id or None
    vk_enabled_flag = await get_setting(db, "vk_enabled")
    vk_active = (vk_enabled_flag != "false") and bool(vk_client_id)

    # Telegram
    telegram_token = await get_setting(db, "telegram_bot_token")
    telegram_enabled = bool(telegram_token)
    bot_username: str | None = None
    if telegram_enabled:
        bot_username = await get_setting(db, "telegram_bot_username") or None

    # Email
    email_enabled_flag = await get_setting(db, "email_enabled")
    email_enabled = email_enabled_flag != "false"

    # Support link
    support_telegram_url = await get_setting(db, "support_telegram_link") or None

    email_verification_required = await get_setting(db, "email_verification_enabled") == "true"

    return OAuthConfigResponse(
        google=google_active,
        google_client_id=google_client_id if google_active else None,
        vk=vk_active,
        vk_client_id=vk_client_id if vk_active else None,
        telegram=telegram_enabled,
        telegram_bot_username=bot_username,
        email_enabled=email_enabled,
        support_telegram_url=support_telegram_url,
        email_verification_required=email_verification_required,
    )


@router.post("/register", response_model=TokenResponse)
async def register_email(
    data: EmailRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # Guard 1: registration enabled
    registration_enabled = await get_setting(db, "registration_enabled")
    if registration_enabled == "false":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Регистрация временно закрыта")

    # Guard 2: domain whitelist
    allowed_domains_str = await get_setting(db, "allowed_email_domains") or ""
    allowed_domains = [d.strip().lower() for d in allowed_domains_str.split(",") if d.strip()]
    if allowed_domains:
        email_domain = data.email.lower().split("@")[-1]
        if email_domain not in allowed_domains:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Регистрация с этим email-адресом недоступна")

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

    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")

    # Reject if password was changed after this refresh token was issued
    token_pwd_v = int(payload.get("pwd_v", 0))
    stored_raw = await redis.get(f"user_pwd_version:{str(user.id)}")
    stored_pwd_v = int(stored_raw) if stored_raw else 0
    if token_pwd_v != stored_pwd_v:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalidated")

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
    client_id = await get_setting(db, "google_client_id") or settings.google_client_id
    client_secret = await get_setting_decrypted(db, "google_client_secret") or settings.google_client_secret
    try:
        g_user = await exchange_google_code(data.code, data.redirect_uri, client_id, client_secret)
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
            provider_username=g_user.email,
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
    vk_client_id = await get_setting(db, "vk_client_id") or settings.vk_client_id
    vk_client_secret = await get_setting_decrypted(db, "vk_client_secret") or settings.vk_client_secret
    try:
        vk_user = await exchange_vk_code(data.code, data.redirect_uri, data.device_id, data.state, vk_client_id, vk_client_secret)
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


@router.post("/verify-email/send")
async def send_verify_email(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    result = await db.execute(
        _select(AuthProvider).where(
            AuthProvider.user_id == current_user.id,
            AuthProvider.provider == ProviderType.email,
        )
    )
    email_provider = result.scalar_one_or_none()

    # Already verified or no email provider
    if email_provider is None or email_provider.email_verified:
        return {"ok": True}

    # Check resend API key
    api_key = await get_setting_decrypted(db, "resend_api_key")
    if not api_key:
        raise HTTPException(status_code=503, detail="Email-сервис не настроен")

    # Rate limit: 3 sends per hour per user
    rate_key = f"verify_email_rate:{current_user.id}"
    if not await check_rate_limit(redis, rate_key, 3, 3600):
        raise HTTPException(status_code=429, detail="Слишком много попыток. Попробуйте через час.")

    # Generate token and store in Redis
    token = str(_uuid.uuid4())
    await redis.setex(f"verify_email:{token}", 86400, str(current_user.id))

    # Send email
    from_address = await get_setting(db, "email_from_address") or "noreply@example.com"
    from_name = await get_setting(db, "email_from_name") or "VPN Service"
    frontend_url = settings.frontend_url.rstrip("/")
    verify_url = f"{frontend_url}/verify-email?token={token}"

    try:
        await send_verification_email(
            api_key=api_key,
            from_address=from_address,
            from_name=from_name,
            to_email=email_provider.provider_user_id,
            verify_url=verify_url,
        )
    except Exception as exc:
        logger.exception("Failed to send verification email: %s", exc)
        raise HTTPException(status_code=503, detail="Ошибка отправки письма")

    return {"ok": True}


@router.get("/verify-email/confirm")
async def confirm_verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    frontend_url = settings.frontend_url.rstrip("/")
    user_id_str = await redis.get(f"verify_email:{token}")
    if not user_id_str:
        return RedirectResponse(url=f"{frontend_url}/verify-email?error=expired", status_code=302)

    try:
        user_uuid = _uuid.UUID(user_id_str if isinstance(user_id_str, str) else user_id_str.decode())
    except ValueError:
        return RedirectResponse(url=f"{frontend_url}/verify-email?error=expired", status_code=302)

    result = await db.execute(
        _select(AuthProvider).where(
            AuthProvider.user_id == user_uuid,
            AuthProvider.provider == ProviderType.email,
        )
    )
    email_provider = result.scalar_one_or_none()
    if email_provider:
        email_provider.email_verified = True
        await db.commit()

    await redis.delete(f"verify_email:{token}")
    return RedirectResponse(url=f"{frontend_url}/verify-email?verified=1", status_code=302)
