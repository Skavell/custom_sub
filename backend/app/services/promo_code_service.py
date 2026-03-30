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


async def apply_bonus_days(
    db: AsyncSession,
    promo: PromoCode,
    user: User,
    rw_client: RemnawaveClient,
) -> tuple[int, datetime]:
    """Applies a bonus_days promo code atomically.
    Returns (days_added, new_expires_at).
    Uses SELECT FOR UPDATE to serialize concurrent applications.
    Single db.commit() at the end for atomicity.
    Raises HTTP 400 if promo is invalid at lock-time or already used.
    """
    now = datetime.now(tz=timezone.utc)

    # Re-fetch with lock to serialize concurrent applications
    promo_result = await db.execute(
        select(PromoCode)
        .where(PromoCode.id == promo.id)
        .with_for_update()
    )
    promo_locked = promo_result.scalar_one_or_none()
    if promo_locked is None or not promo_locked.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
    if promo_locked.valid_until is not None and promo_locked.valid_until < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
    if promo_locked.max_uses is not None and promo_locked.used_count >= promo_locked.max_uses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")

    # One-per-user check
    usage_result = await db.execute(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo_locked.id,
            PromoCodeUsage.user_id == user.id,
        )
    )
    if usage_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод уже использован")

    # Extend Remnawave subscription
    rw_user = await rw_client.get_user(str(user.remnawave_uuid))
    base_date = max(rw_user.expire_at, now)
    new_expire_at = base_date + timedelta(days=promo_locked.value)
    rw_user = await rw_client.update_user(
        str(user.remnawave_uuid),
        traffic_limit_bytes=0,  # unlimited — always paid after bonus
        expire_at=new_expire_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Upsert local subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, started_at=now)
        db.add(sub)
    sub.type = SubscriptionType.paid
    sub.status = SubscriptionStatus.active
    sub.expires_at = rw_user.expire_at
    sub.traffic_limit_gb = None  # 0 bytes → unlimited
    sub.synced_at = now

    # Create promo_bonus transaction
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.promo_bonus,
        promo_code_id=promo_locked.id,
        days_added=promo_locked.value,
        status=TransactionStatus.completed,
        description=f"Промокод {promo_locked.code}",
        completed_at=now,
    )
    db.add(tx)

    # Record usage + increment counter
    db.add(PromoCodeUsage(promo_code_id=promo_locked.id, user_id=user.id))
    promo_locked.used_count += 1

    await db.commit()
    await db.refresh(sub)

    return promo_locked.value, sub.expires_at
