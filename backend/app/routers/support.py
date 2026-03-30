# backend/app/routers/support.py
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.support import SupportMessageRequest
from app.services.rate_limiter import check_rate_limit
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.telegram_alert import send_admin_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/support", tags=["support"])

_SUPPORT_RATE_LIMIT = 5
_SUPPORT_RATE_WINDOW = 3600  # 1 hour


@router.post("/message")
async def send_support_message(
    data: SupportMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    # Rate limit per user
    rate_key = f"rate:support:{current_user.id}"
    if not await check_rate_limit(redis, rate_key, _SUPPORT_RATE_LIMIT, _SUPPORT_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много сообщений. Попробуйте позже.",
        )

    user_id_short = str(current_user.id)[:8]
    text = (
        f"📨 Новое сообщение\n"
        f"От: {current_user.display_name} (#{user_id_short})\n\n"
        f"{data.message}"
    )

    bot_token = await get_setting_decrypted(db, "telegram_bot_token")
    chat_id = await get_setting(db, "telegram_support_chat_id")

    # Fire-and-forget — send_admin_alert swallows all exceptions
    await send_admin_alert(bot_token, chat_id, text)

    return {"ok": True}
