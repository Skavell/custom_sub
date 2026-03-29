import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveUser
from app.services.subscription_service import (
    get_user_subscription,
    create_trial_subscription,
    sync_subscription_from_remnawave,
)

NOW = datetime.now(tz=timezone.utc)
USER_ID = uuid.uuid4()
REMNAWAVE_UUID = "aaaaaaaa-0000-0000-0000-000000000001"


def _make_user(remnawave_uuid=None):
    user = MagicMock(spec=User)
    user.id = USER_ID
    user.remnawave_uuid = uuid.UUID(remnawave_uuid) if remnawave_uuid else None
    user.has_made_payment = False
    return user


def _make_db(subscription=None):
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=subscription)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_get_user_subscription_found():
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    db = _make_db(sub)
    result = await get_user_subscription(db, USER_ID)
    assert result is sub


@pytest.mark.asyncio
async def test_get_user_subscription_not_found():
    db = _make_db(None)
    result = await get_user_subscription(db, USER_ID)
    assert result is None


@pytest.mark.asyncio
async def test_create_trial_subscription_creates_row():
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    sub = await create_trial_subscription(
        db=db,
        user=user,
        trial_days=3,
        trial_traffic_bytes=32212254720,  # 30 GB
    )

    # Should add Subscription and Transaction, then commit, then refresh
    assert db.add.call_count == 2
    assert db.commit.await_count == 1
    assert db.refresh.await_count == 1

    sub_call = db.add.call_args_list[0][0][0]
    assert sub_call.type == SubscriptionType.trial
    assert sub_call.status == SubscriptionStatus.active
    assert sub_call.traffic_limit_gb == 30  # ceil(30GB bytes / 1024^3)


@pytest.mark.asyncio
async def test_sync_subscription_from_remnawave_active():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    user = _make_user(REMNAWAVE_UUID)
    remnawave_user = RemnawaveUser(
        id=REMNAWAVE_UUID,
        username="ws_4a1b2c3d",
        expire_at=NOW + timedelta(days=7),
        traffic_limit_bytes=0,
        status="ACTIVE",
        subscription_url="https://sub.example.com/abc",
        telegram_id=None,
    )

    await sync_subscription_from_remnawave(db, user, remnawave_user)

    db.add.assert_called_once()
    sub = db.add.call_args[0][0]
    assert sub.status == SubscriptionStatus.active
    assert sub.traffic_limit_gb is None  # 0 bytes = unlimited
