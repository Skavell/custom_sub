import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _make_admin():
    admin = MagicMock(spec=User)
    admin.id = uuid.uuid4()
    admin.is_admin = True
    admin.is_banned = False
    return admin


def _make_target_user(is_banned=False, is_admin=False):
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.is_banned = is_banned
    user.is_admin = is_admin
    user.display_name = "Test User"
    user.avatar_url = None
    user.remnawave_uuid = None
    user.has_made_payment = False
    user.subscription_conflict = False
    from datetime import datetime, timezone
    user.created_at = datetime.now(tz=timezone.utc)
    user.last_seen_at = datetime.now(tz=timezone.utc)
    user.subscription = None
    user.auth_providers = []
    return user


@pytest.mark.asyncio
async def test_ban_user_toggles_is_banned():
    """PATCH /ban toggles is_banned on target user."""
    from datetime import datetime, timezone
    from app.schemas.admin import UserAdminDetail as UAD

    admin = _make_admin()
    target = _make_target_user(is_banned=False)
    db = AsyncMock(spec=AsyncSession)

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = target
    db.execute = AsyncMock(return_value=user_result)
    db.commit = AsyncMock()

    now = datetime.now(tz=timezone.utc)
    detail_response = UAD(
        id=target.id,
        display_name=target.display_name,
        avatar_url=None,
        is_admin=False,
        is_banned=True,
        remnawave_uuid=None,
        has_made_payment=False,
        subscription_conflict=False,
        created_at=now,
        last_seen_at=now,
        email=None,
        email_verified=None,
        subscription=None,
        providers=[],
        recent_transactions=[],
    )

    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = _override_db(db)

    try:
        with patch("app.routers.admin._build_user_detail", new=AsyncMock(return_value=detail_response)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(f"/api/admin/users/{target.id}/ban")
        assert resp.status_code == 200
        assert target.is_banned is True  # toggled by endpoint
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ban_self_returns_403():
    """Cannot ban yourself."""
    admin = _make_admin()
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(f"/api/admin/users/{admin.id}/ban")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reset_subscription_deletes_sub_and_clears_uuid():
    """POST /reset-subscription deletes the subscription and clears remnawave_uuid."""
    admin = _make_admin()
    target = _make_target_user()
    target.remnawave_uuid = "some-uuid"
    sub = MagicMock(spec=Subscription)
    sub.status = SubscriptionStatus.active

    db = AsyncMock(spec=AsyncSession)
    target_result = MagicMock()
    target_result.scalar_one_or_none.return_value = target
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = sub

    call_count = [0]
    async def mock_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return target_result
        return sub_result

    db.execute = AsyncMock(side_effect=mock_execute)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = _override_db(db)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/admin/users/{target.id}/reset-subscription")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        db.delete.assert_called_once_with(sub)
        assert target.remnawave_uuid is None
    finally:
        app.dependency_overrides.clear()
