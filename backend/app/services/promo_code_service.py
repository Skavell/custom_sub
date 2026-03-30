# backend/app/services/promo_code_service.py
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promo_code import PromoCode, PromoCodeUsage, PromoCodeType
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.remnawave_client import RemnawaveClient


async def validate_promo_code(
    db: AsyncSession,
    code: str,
    user: User,
) -> tuple[PromoCode, bool]:
    """Returns (promo, already_used_by_user).
    Raises HTTP 404 if code is invalid/inactive/expired/maxed.
    Works for both promo types (discount_percent and bonus_days).
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(PromoCode).where(PromoCode.code == code.upper())
    )
    promo = result.scalar_one_or_none()

    if not promo or not promo.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
    if promo.valid_until is not None and promo.valid_until < now:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")

    usage_result = await db.execute(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo.id,
            PromoCodeUsage.user_id == user.id,
        )
    )
    already_used = usage_result.scalar_one_or_none() is not None

    return promo, already_used
