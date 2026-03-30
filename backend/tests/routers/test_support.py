# backend/tests/routers/test_support.py
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


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Тест Пользователь"
    return u


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
async def test_support_rate_limited_returns_429():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=6)  # over limit of 5
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/support/message", json={"message": "помогите"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_support_empty_message_returns_422():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/support/message", json={"message": "   "})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_support_success_returns_200():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.support.get_setting", return_value="chat_id_value"), \
         patch("app.routers.support.get_setting_decrypted", return_value="secret_token"), \
         patch("app.routers.support.send_admin_alert", new_callable=AsyncMock) as mock_alert:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/support/message", json={"message": "Нужна помощь"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_alert.assert_called_once()


@pytest.mark.asyncio
async def test_support_no_telegram_config_still_returns_200():
    """Even if Telegram is not configured, endpoint returns 200 (graceful degradation)."""
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.support.get_setting", return_value=None), \
         patch("app.routers.support.get_setting_decrypted", return_value=None), \
         patch("app.routers.support.send_admin_alert", new_callable=AsyncMock):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/support/message", json={"message": "Нужна помощь"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
