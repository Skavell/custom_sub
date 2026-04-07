from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment_providers.base import PaymentProvider
from app.services.payment_providers.cryptobot import CryptoBotProvider
from app.services.setting_service import get_setting, get_setting_decrypted

# ─── Provider registry ────────────────────────────────────────────────────────

_KNOWN_PROVIDERS: list[str] = ["cryptobot"]

_PROVIDER_LABELS: dict[str, str] = {
    "cryptobot": "CryptoBot",
}


async def _is_provider_active(db: AsyncSession, name: str) -> bool:
    """Returns True iff the provider is enabled (== "true") AND has a token set.
    Both disabled and missing-token states return False — both mean "can't pay".
    Uses strict equality (== "true"), NOT the frontend OAuthToggle convention (!= "false").
    """
    if name == "cryptobot":
        enabled = await get_setting(db, "cryptobot_enabled")
        if enabled != "true":
            return False
        token = await get_setting_decrypted(db, "cryptobot_token")
        return bool(token)
    return False


async def get_active_provider(db: AsyncSession, provider_name: str) -> PaymentProvider:
    """Return the configured payment provider by name.

    Raises:
        HTTP 400 — provider name is unknown or provider is disabled
        HTTP 503 — provider is enabled but token is missing/misconfigured
    """
    if provider_name not in _KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неизвестная платёжная система",
        )

    if provider_name == "cryptobot":
        enabled = await get_setting(db, "cryptobot_enabled")
        if enabled != "true":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Платёжная система отключена",
            )
        token = await get_setting_decrypted(db, "cryptobot_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Платёжная система не настроена. Обратитесь в поддержку.",
            )
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
