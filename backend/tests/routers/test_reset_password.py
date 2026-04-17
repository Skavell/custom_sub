import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from app.redis_client import get_redis
from app.models.auth_provider import AuthProvider, ProviderType


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_reset_request_email_not_found_returns_404():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # email not in DB
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # not rate limited

    with patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=True)):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/request", json={"email": "notfound@example.com"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert "не найден" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_request_rate_limited_returns_429():
    db = AsyncMock()
    redis = AsyncMock()

    with patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=False)):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/request", json={"email": "user@example.com"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_reset_request_found_sends_email_and_returns_200():
    provider = MagicMock(spec=AuthProvider)
    provider.provider = ProviderType.email
    provider.provider_user_id = "user@example.com"
    provider.user_id = uuid.uuid4()

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.setex = AsyncMock()

    with (
        patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=True)),
        patch("app.routers.auth.get_setting", new=AsyncMock(return_value="noreply@test.com")),
        patch("app.routers.auth.get_setting_decrypted", new=AsyncMock(return_value="fake-resend-key")),
        patch("app.routers.auth.send_reset_email", new=AsyncMock()),
    ):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/request", json={"email": "user@example.com"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_reset_confirm_invalid_token_returns_400():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # token not in Redis

    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/auth/reset-password/confirm", json={
                "token": "nonexistent-token",
                "new_password": "NewPass1"
            })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "недействительна" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_confirm_weak_password_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/reset-password/confirm", json={
            "token": "sometoken",
            "new_password": "weakpassword"  # no uppercase, no digit
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_confirm_valid_token_updates_password():
    user_id = str(uuid.uuid4())

    provider = MagicMock(spec=AuthProvider)
    provider.password_hash = "old_hash"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=user_id.encode())
    redis.delete = AsyncMock()
    redis.incr = AsyncMock()

    with patch("app.routers.auth.hash_password", return_value="new_hash"):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/confirm", json={
                    "token": "validtoken123",
                    "new_password": "NewPass1"
                })
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert provider.password_hash == "new_hash"
    redis.incr.assert_called_once()
    redis.delete.assert_called_once()
