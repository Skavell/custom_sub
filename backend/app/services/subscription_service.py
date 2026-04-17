from __future__ import annotations
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveUser

logger = logging.getLogger(__name__)


@dataclass
class TelegramLinkResult:
    """Result of sync_remnawave_by_telegram_id — informs the caller what happened."""
    action: str  # "first_link" | "set_telegram_id" | "replaced_trial" | "merged_paid" | "kept_paid" | "same_user" | "no_tg_user" | "no_config" | "error"
    notification: str | None = None  # User-facing message to show in the UI (Russian)


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
    # Refresh so attributes are not in "expired" state after commit (same rationale
    # as create_trial_subscription — avoids MissingGreenlet on async attribute access).
    await db.refresh(sub)
    return sub


async def sync_remnawave_by_telegram_id(
    db: AsyncSession,
    user: User,
    telegram_id: int,
    telegram_username: str | None = None,
) -> TelegramLinkResult:
    """Sync/merge subscriptions when a Telegram account is linked or used for login.

    Scenarios:
    - No existing remnawave_uuid → link TG subscription if found, done.
    - Has remnawave_uuid, no TG user in Remnawave → set telegramId on site user.
    - Both exist and they are the same Remnawave user → nothing to do.
    - Site = trial, TG = any → replace site subscription with TG, delete site Remnawave user.
    - Site = paid, TG = trial → keep site subscription, just set telegramId.
    - Site = paid, TG = paid → merge (add remaining days), replace with TG, delete site user.

    Trial detection: traffic_limit_bytes > 0 → trial, 0 → paid/unlimited.
    Failures are logged and swallowed — must not block auth or linking flow.
    """
    try:
        from app.services.setting_service import get_setting, get_setting_decrypted
        remnawave_url = await get_setting(db, "remnawave_url")
        remnawave_token = await get_setting_decrypted(db, "remnawave_token")
        if not remnawave_url or not remnawave_token:
            return TelegramLinkResult(action="no_config")

        from app.services.remnawave_client import RemnawaveClient
        rw_client = RemnawaveClient(remnawave_url, remnawave_token)
        tg_rw_user = await rw_client.get_user_by_telegram_id(telegram_id)

        # ── Case 1: user has no site subscription yet ──────────────────────────
        if user.remnawave_uuid is None:
            if tg_rw_user is None:
                return TelegramLinkResult(action="no_tg_user")
            user.remnawave_uuid = uuid.UUID(tg_rw_user.id)
            await db.commit()
            await sync_subscription_from_remnawave(db, user, tg_rw_user)
            return TelegramLinkResult(action="first_link")

        # ── Case 2: user already has a site subscription ───────────────────────
        site_rw_user = await rw_client.get_user(str(user.remnawave_uuid))

        # Same Remnawave user — nothing to do
        if tg_rw_user is not None and tg_rw_user.id == site_rw_user.id:
            return TelegramLinkResult(action="same_user")

        if tg_rw_user is None:
            # No TG user in Remnawave → stamp telegramId (and username as description) on the site user
            await rw_client.update_user(
                str(user.remnawave_uuid),
                telegram_id=telegram_id,
                description=f"@{telegram_username}" if telegram_username else None,
            )
            return TelegramLinkResult(action="set_telegram_id")

        # Determine subscription types (trial = has traffic limit)
        site_is_trial = site_rw_user.traffic_limit_bytes > 0
        tg_is_trial = tg_rw_user.traffic_limit_bytes > 0

        if site_is_trial:
            # ── Site = trial → always replace with TG subscription ────────────
            old_site_uuid = str(user.remnawave_uuid)
            user.remnawave_uuid = uuid.UUID(tg_rw_user.id)
            await db.commit()
            await sync_subscription_from_remnawave(db, user, tg_rw_user)
            try:
                await rw_client.delete_user(old_site_uuid)
            except Exception as exc:
                logger.warning("Could not delete site trial user %s from Remnawave: %s", old_site_uuid, exc)
            return TelegramLinkResult(
                action="replaced_trial",
                notification=(
                    "К аккаунту привязана подписка, созданная через Telegram-бота. "
                    "Пробная подписка с сайта удалена. "
                    "Если вы уже добавляли подписку с сайта в приложение — "
                    "нужно повторить добавление через вкладку «Установка»."
                ),
            )

        elif not tg_is_trial:
            # ── Site = paid, TG = paid → merge subscriptions ──────────────────
            now = datetime.now(tz=timezone.utc)
            site_remaining_secs = max(0.0, (site_rw_user.expire_at - now).total_seconds())
            site_remaining_days = math.ceil(site_remaining_secs / 86400)
            new_expire_at = tg_rw_user.expire_at + timedelta(days=site_remaining_days)
            updated_tg_user = await rw_client.update_user(
                tg_rw_user.id,
                expire_at=new_expire_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            )
            old_site_uuid = str(user.remnawave_uuid)
            user.remnawave_uuid = uuid.UUID(tg_rw_user.id)
            await db.commit()
            await sync_subscription_from_remnawave(db, user, updated_tg_user)
            try:
                await rw_client.delete_user(old_site_uuid)
            except Exception as exc:
                logger.warning("Could not delete site paid user %s from Remnawave: %s", old_site_uuid, exc)
            return TelegramLinkResult(
                action="merged_paid",
                notification=(
                    f"Подписки объединены: к подписке из Telegram-бота добавлено {site_remaining_days} дн. с сайта. "
                    "Подписка, созданная через сайт, удалена. "
                    "Актуальная подписка отображается в профиле — "
                    "возможно, нужно добавить её в приложение заново через вкладку «Установка»."
                ),
            )

        else:
            # ── Site = paid, TG = trial → keep site, stamp telegramId, delete TG trial ──
            await rw_client.update_user(
                str(user.remnawave_uuid),
                telegram_id=telegram_id,
                description=f"@{telegram_username}" if telegram_username else None,
            )
            try:
                await rw_client.delete_user(tg_rw_user.id)
            except Exception as exc:
                logger.warning("Could not delete TG trial user %s from Remnawave: %s", tg_rw_user.id, exc)
            return TelegramLinkResult(action="kept_paid")

    except Exception as exc:
        logger.warning("Remnawave sync by Telegram ID failed (non-blocking): %s", exc)
        return TelegramLinkResult(action="error")
