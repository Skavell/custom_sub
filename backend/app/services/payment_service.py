from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.promo_code import PromoCode, PromoCodeUsage, PromoCodeType
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveClient


async def calculate_final_price(
    db: AsyncSession,
    plan: Plan,
    user: User,
    promo_code_str: str | None,
) -> tuple[int, PromoCode | None]:
    """Returns (final_price_rub, validated_promo_or_None).
    Raises HTTP 400 if promo code string is provided but invalid.
    """
    candidates: list[int] = [plan.price_rub]

    # New user discount: only on 1_month plan
    if (
        not user.has_made_payment
        and plan.name == "1_month"
        and plan.new_user_price_rub is not None
    ):
        candidates.append(plan.new_user_price_rub)

    promo: PromoCode | None = None
    if promo_code_str:
        now = datetime.now(tz=timezone.utc)
        result = await db.execute(
            select(PromoCode).where(PromoCode.code == promo_code_str.upper())
        )
        promo = result.scalar_one_or_none()

        if not promo or not promo.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
        if promo.valid_until is not None and promo.valid_until < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
        if promo.max_uses is not None and promo.used_count >= promo.max_uses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
        if promo.type != PromoCodeType.discount_percent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")

        # Check one-per-user constraint
        usage_result = await db.execute(
            select(PromoCodeUsage).where(
                PromoCodeUsage.promo_code_id == promo.id,
                PromoCodeUsage.user_id == user.id,
            )
        )
        if usage_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")

        discounted = round(plan.price_rub * (1 - promo.value / 100))
        candidates.append(discounted)

    return min(candidates), promo


async def get_pending_transaction(
    db: AsyncSession, user_id: uuid.UUID
) -> Transaction | None:
    """SELECT FOR UPDATE (blocking) — serialises concurrent payment creation for the same user."""
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.pending,
        )
        .with_for_update()
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def complete_payment(
    db: AsyncSession,
    transaction: Transaction,
    user: User,
    plan: Plan,
    rw_client: RemnawaveClient,
    paid_internal_squad_uuids: list[str] | None = None,
    paid_external_squad_uuid: str | None = None,
) -> None:
    """Atomically completes payment: extends Remnawave subscription + updates all local state.
    Single db.commit() at the end — does NOT call sync_subscription_from_remnawave
    (that function has its own internal commit which would break atomicity).
    Raises httpx.HTTPStatusError / httpx.RequestError on Remnawave failure.
    Caller must send alert + return 500.
    """
    now = datetime.now(tz=timezone.utc)

    # Extend Remnawave subscription
    rw_user = await rw_client.get_user(str(user.remnawave_uuid))
    base_date = max(rw_user.expire_at, now)
    new_expire_at = base_date + timedelta(days=plan.duration_days)
    rw_user = await rw_client.update_user(
        str(user.remnawave_uuid),
        traffic_limit_bytes=0,  # unlimited — all paid plans
        expire_at=new_expire_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        internal_squad_uuids=paid_internal_squad_uuids,
        external_squad_uuid=paid_external_squad_uuid,
    )

    # Upsert local subscription directly (no sync_subscription_from_remnawave)
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

    # Update user + transaction
    user.has_made_payment = True
    transaction.status = TransactionStatus.completed
    transaction.completed_at = now
    transaction.days_added = plan.duration_days

    # Record promo code usage if applicable
    if transaction.promo_code_id is not None:
        promo_result = await db.execute(
            select(PromoCode)
            .where(PromoCode.id == transaction.promo_code_id)
            .with_for_update()
        )
        promo = promo_result.scalar_one_or_none()
        if promo is not None:
            db.add(PromoCodeUsage(promo_code_id=promo.id, user_id=user.id))
            promo.used_count += 1

    await db.commit()
