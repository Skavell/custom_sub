from __future__ import annotations
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveUser


async def get_user_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    """Returns the subscription row for this user, or None if no subscription exists."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_trial_subscription(
    db: AsyncSession,
    user: User,
    trial_days: int,
    trial_traffic_bytes: int,
) -> Subscription:
    """Create a trial Subscription row and a trial_activation Transaction.
    Caller is responsible for setting user.remnawave_uuid before calling this.
    """
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(days=trial_days)

    traffic_gb = math.ceil(trial_traffic_bytes / (1024 ** 3)) if trial_traffic_bytes > 0 else None

    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.trial,
        status=SubscriptionStatus.active,
        started_at=now,
        expires_at=expires_at,
        traffic_limit_gb=traffic_gb,
        synced_at=now,
    )
    db.add(sub)

    tx = Transaction(
        user_id=user.id,
        type=TransactionType.trial_activation,
        days_added=trial_days,
        status=TransactionStatus.completed,
        description="Активация пробного периода",
        completed_at=now,
    )
    db.add(tx)
    await db.commit()
    # Refresh sub so attributes are not in "expired" state after commit
    # (SQLAlchemy expires all ORM attributes on commit by default).
    # Without this, accessing sub.type/expires_at in the router raises MissingGreenlet.
    await db.refresh(sub)
    return sub


async def sync_subscription_from_remnawave(
    db: AsyncSession, user: User, remnawave_user: RemnawaveUser
) -> Subscription:
    """Create or update the local subscription row from Remnawave data.
    Type inference: if user.has_made_payment=True → always paid.
    Otherwise: traffic_limit_bytes=0 → paid (unlimited), >0 → trial.
    """
    now = datetime.now(tz=timezone.utc)

    if remnawave_user.traffic_limit_bytes > 0:
        traffic_gb: int | None = math.ceil(remnawave_user.traffic_limit_bytes / (1024 ** 3))
    else:
        traffic_gb = None

    if user.has_made_payment:
        sub_type = SubscriptionType.paid
    else:
        sub_type = SubscriptionType.paid if traffic_gb is None else SubscriptionType.trial

    if remnawave_user.status == "ACTIVE" and remnawave_user.expire_at > now:
        sub_status = SubscriptionStatus.active
    elif remnawave_user.status == "DISABLED":
        sub_status = SubscriptionStatus.disabled
    else:
        sub_status = SubscriptionStatus.expired

    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, started_at=now)
        db.add(sub)

    sub.type = sub_type
    sub.status = sub_status
    sub.expires_at = remnawave_user.expire_at
    sub.traffic_limit_gb = traffic_gb
    sub.synced_at = now

    await db.commit()
    return sub
