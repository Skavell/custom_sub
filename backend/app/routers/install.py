# backend/app/routers/install.py
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.subscription import SubscriptionStatus
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.install import SubscriptionLinkResponse
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import get_user_subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/install", tags=["install"])

_SUB_URL_TTL = 3600  # 1 hour


@router.get("/subscription-link", response_model=SubscriptionLinkResponse)
async def get_subscription_link(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SubscriptionLinkResponse:
    # Guard: must have an active subscription
    sub = await get_user_subscription(db, current_user.id)
    if sub is None or sub.status != SubscriptionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подписка неактивна. Для доступа к ссылке установки продлите подписку.",
        )

    # Try Redis cache first
    cache_key = f"sub_url:{current_user.id}"
    cached = await redis.get(cache_key)
    if cached:
        return SubscriptionLinkResponse(subscription_url=cached)

    # Cache miss — fetch from Remnawave
    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )

    rw_client = RemnawaveClient(url, token)
    try:
        rw_user = await rw_client.get_user(str(current_user.remnawave_uuid))
    except Exception as exc:
        logger.exception("Failed to fetch subscription URL from Remnawave: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )

    subscription_url = rw_user.subscription_url
    await redis.set(cache_key, subscription_url, ex=_SUB_URL_TTL)

    return SubscriptionLinkResponse(subscription_url=subscription_url)
