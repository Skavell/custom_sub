from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment_providers.base import PaymentProvider
from app.services.payment_providers.cryptobot import CryptoBotProvider
from app.services.setting_service import get_setting, get_setting_decrypted


async def get_active_provider(db: AsyncSession) -> PaymentProvider:
    """Read settings and return the configured payment provider.
    Raises HTTP 503 if no provider is configured.
    """
    token = await get_setting_decrypted(db, "cryptobot_token")
    if token:
        rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
        try:
            rate = float(rate_str)
            if rate <= 0:
                rate = 83.0
        except ValueError:
            rate = 83.0
        return CryptoBotProvider(token=token, usdt_rate=rate)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Платёжная система не настроена. Обратитесь в поддержку.",
    )
