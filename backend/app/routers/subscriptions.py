import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.subscription import SubscriptionResponse, TrialActivateResponse
from app.services.rate_limiter import check_rate_limit
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import (
    create_trial_subscription,
    get_user_subscription,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

_TRIAL_RATE_LIMIT = 3
_TRIAL_RATE_WINDOW = 86400  # 24 hours


def _to_response(sub) -> SubscriptionResponse:
    now = datetime.now(tz=timezone.utc)
    expires = sub.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    days_remaining = max(0, (expires - now).days)
    return SubscriptionResponse(
        type=sub.type.value,
        status=sub.status.value,
        started_at=sub.started_at,
        expires_at=expires,
        traffic_limit_gb=sub.traffic_limit_gb,
        days_remaining=days_remaining,
    )


@router.get("/me", response_model=SubscriptionResponse | None)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse | None:
    sub = await get_user_subscription(db, current_user.id)
    if sub is None:
        return None
    return _to_response(sub)


@router.post("/trial", response_model=TrialActivateResponse, status_code=201)
async def activate_trial(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TrialActivateResponse:
    # Guard 1: already activated
    if current_user.remnawave_uuid is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пробный период уже был активирован",
        )

    # Guard 2: IP rate limit
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate:trial:{client_ip}"
    allowed = await check_rate_limit(redis, rate_key, _TRIAL_RATE_LIMIT, _TRIAL_RATE_WINDOW)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен лимит активаций. Попробуйте завтра.",
        )

    # Guard 3: Remnawave not configured
    remnawave_url = await get_setting(db, "remnawave_url")
    remnawave_token = await get_setting_decrypted(db, "remnawave_token")
    if not remnawave_url or not remnawave_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен. Обратитесь в поддержку.",
        )

    # Guard 4: email verification
    email_verification_enabled = await get_setting(db, "email_verification_enabled")
    if email_verification_enabled == "true":
        from sqlalchemy import select as _sel
        from app.models.auth_provider import AuthProvider, ProviderType
        ev_result = await db.execute(
            _sel(AuthProvider).where(
                AuthProvider.user_id == current_user.id,
                AuthProvider.provider == ProviderType.email,
            )
        )
        email_provider = ev_result.scalar_one_or_none()
        if email_provider is not None and not email_provider.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Подтвердите email для активации пробного периода",
            )

    # Fetch trial settings
    trial_days_str = await get_setting(db, "remnawave_trial_days") or "3"
    trial_days = int(trial_days_str)
    trial_traffic_str = await get_setting(db, "remnawave_trial_traffic_limit_bytes") or str(30 * 1024 ** 3)
    trial_traffic_bytes = int(trial_traffic_str)
    squad_uuids_str = (
        await get_setting(db, "remnawave_trial_squad_uuids")
        or await get_setting(db, "remnawave_squad_uuids")
        or ""
    )
    squad_ids = [s.strip() for s in squad_uuids_str.split(",") if s.strip()]

    # Build Remnawave username
    user_id_hex = str(current_user.id).replace("-", "")
    username = f"ws_{user_id_hex[:8]}"

    # Get Telegram info if linked
    from sqlalchemy import select as _select
    from app.models.auth_provider import AuthProvider, ProviderType
    result = await db.execute(
        _select(AuthProvider).where(
            AuthProvider.user_id == current_user.id,
            AuthProvider.provider == ProviderType.telegram,
        )
    )
    tg_provider = result.scalar_one_or_none()
    telegram_id: int | None = None
    description: str | None = None
    if tg_provider:
        try:
            telegram_id = int(tg_provider.provider_user_id)
            description = f"@{tg_provider.provider_username}" if tg_provider.provider_username else None
        except (ValueError, TypeError):
            pass

    # Create Remnawave user (retry with longer suffix on username collision)
    from datetime import timedelta
    expire_at = (datetime.now(tz=timezone.utc) + timedelta(days=trial_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        rw_user = await RemnawaveClient(remnawave_url, remnawave_token).create_user(
            username=username,
            traffic_limit_bytes=trial_traffic_bytes,
            expire_at=expire_at,
            squad_ids=squad_ids,
            telegram_id=telegram_id,
            description=description,
        )
    except Exception as exc:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 409:
            username_long = f"ws_{user_id_hex[:12]}"
            rw_user = await RemnawaveClient(remnawave_url, remnawave_token).create_user(
                username=username_long,
                traffic_limit_bytes=trial_traffic_bytes,
                expire_at=expire_at,
                squad_ids=squad_ids,
                telegram_id=telegram_id,
                description=description,
            )
        else:
            logger.exception("Remnawave user creation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ошибка подключения к серверу туннелей. Попробуйте позже.",
            )

    # Persist remnawave_uuid on user
    import uuid as _uuid
    current_user.remnawave_uuid = _uuid.UUID(rw_user.id)
    await db.commit()

    # Create local subscription
    sub = await create_trial_subscription(
        db=db,
        user=current_user,
        trial_days=trial_days,
        trial_traffic_bytes=trial_traffic_bytes,
    )

    return TrialActivateResponse(
        subscription=_to_response(sub),
        message=f"Пробный период активирован на {trial_days} дня",
    )
