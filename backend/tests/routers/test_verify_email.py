import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.deps import get_current_user
from app.redis_client import get_redis
from app.database import get_db
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType


def _make_user_with_email(email_verified=False):
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.is_banned = False
    provider = MagicMock(spec=AuthProvider)
    provider.provider = ProviderType.email
    provider.provider_user_id = "user@gmail.com"
    provider.email_verified = email_verified
    user.auth_providers = [provider]
    return user, provider


def _override_db(mock_db):
    async def _dep():
        return mock_db
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_send_verify_already_verified_returns_200():
    """Returns 200 no-op if email already verified."""
    user, provider = _make_user_with_email(email_verified=True)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider  # returns already-verified provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/auth/verify-email/send")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_verify_rate_limited_returns_429():
    """Returns 429 when rate limit exceeded."""
    user, provider = _make_user_with_email(email_verified=False)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)

    try:
        with patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=False)):
            with patch("app.routers.auth.get_setting_decrypted", new=AsyncMock(return_value="re_key")):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/api/auth/verify-email/send")
        assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_confirm_invalid_token_redirects_to_error():
    """Redirects to ?error=expired when token not in Redis."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)

    app.dependency_overrides[get_redis] = _override_redis(redis)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.get("/api/auth/verify-email/confirm?token=badtoken")
        assert resp.status_code == 302
        assert "error=expired" in resp.headers["location"]
    finally:
        app.dependency_overrides.clear()
