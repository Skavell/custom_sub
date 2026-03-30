# backend/tests/routers/test_install.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.redis_client import get_redis
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType


def _make_user(remnawave_uuid=None):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.remnawave_uuid = remnawave_uuid or uuid.uuid4()
    return u


def _make_sub(status=SubscriptionStatus.active, type_=SubscriptionType.paid):
    s = MagicMock(spec=Subscription)
    s.status = status
    s.type = type_
    return s


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_install_no_subscription_returns_403():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=None):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_install_expired_subscription_returns_403():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    sub = _make_sub(status=SubscriptionStatus.expired)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=sub):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_install_returns_cached_url():
    user = _make_user()
    sub = _make_sub()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value="https://rw.example.com/sub/abc123")
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=sub):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["subscription_url"] == "https://rw.example.com/sub/abc123"


@pytest.mark.asyncio
async def test_install_rw_not_configured_returns_503():
    user = _make_user()
    sub = _make_sub()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=sub), \
         patch("app.routers.install.get_setting", return_value=None), \
         patch("app.routers.install.get_setting_decrypted", return_value=None):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_install_fetches_from_remnawave_and_caches():
    user = _make_user()
    sub = _make_sub()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    rw_user = MagicMock()
    rw_user.subscription_url = "https://rw.example.com/sub/fresh"

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    mock_rw_client = AsyncMock()
    mock_rw_client.get_user = AsyncMock(return_value=rw_user)

    with patch("app.routers.install.get_user_subscription", return_value=sub), \
         patch("app.routers.install.get_setting", return_value="http://rw"), \
         patch("app.routers.install.get_setting_decrypted", return_value="token"), \
         patch("app.routers.install.RemnawaveClient", return_value=mock_rw_client):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["subscription_url"] == "https://rw.example.com/sub/fresh"
    redis.set.assert_called_once()
