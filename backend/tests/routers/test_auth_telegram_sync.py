"""Tests for Telegram OAuth first-login Remnawave sync."""
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.redis_client import get_redis


NOW = datetime.now(tz=timezone.utc)


@pytest.mark.asyncio
async def test_telegram_oauth_first_login_remnawave_not_configured():
    """First Telegram login succeeds even if Remnawave is not configured (fail-silent)."""
    import time
    import hmac as _hmac
    import hashlib

    bot_token = "fake_bot_token"
    auth_date = int(time.time())
    tg_data = {
        "id": 515172616,
        "first_name": "Вася",
        "auth_date": auth_date,
    }
    check_string = f"auth_date={auth_date}\nfirst_name=Вася\nid=515172616"
    secret = hashlib.sha256(bot_token.encode()).digest()
    tg_data["hash"] = _hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    # DB: first call returns bot_token setting; everything else returns None
    db = AsyncMock(spec=AsyncSession)

    call_count = [0]
    def _execute_side_effect(stmt, *args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        # First call is for get_setting("telegram_bot_token") — return setting
        if call_count[0] == 1:
            setting = MagicMock()
            setting.is_sensitive = False
            setting.value = {"value": bot_token}
            result.scalar_one_or_none = MagicMock(return_value=setting)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
            result.scalars = MagicMock(return_value=MagicMock(
                all=MagicMock(return_value=[]), first=MagicMock(return_value=None)
            ))
        return result

    db.execute = AsyncMock(side_effect=_execute_side_effect)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.display_name = "Вася"
    mock_user.remnawave_uuid = None

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.setex = AsyncMock()

    async def _get_db_override():
        yield db

    async def _get_redis_override():
        return mock_redis

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_redis] = _get_redis_override

    with patch("app.routers.auth.create_user_with_provider", new=AsyncMock(return_value=mock_user)), \
         patch("app.routers.auth.get_user_by_provider", new=AsyncMock(return_value=None)), \
         patch("app.routers.auth._sync_remnawave_on_first_telegram_login", new=AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/auth/oauth/telegram", json=tg_data)

    app.dependency_overrides.clear()

    # Should succeed — 200 even without Remnawave
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Вася"
