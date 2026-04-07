import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from unittest.mock import MagicMock


def _make_user():
    u = MagicMock(spec=User)
    u.id = None
    return u


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


@pytest.mark.asyncio
async def test_get_providers_returns_cryptobot_active():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_current_user] = _override_user(_make_user())

    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="tok"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/payments/providers")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "cryptobot"
    assert data[0]["label"] == "CryptoBot"
    assert data[0]["is_active"] is True


@pytest.mark.asyncio
async def test_get_providers_returns_cryptobot_inactive_when_disabled():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_current_user] = _override_user(_make_user())

    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="false"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="tok"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/payments/providers")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["is_active"] is False


@pytest.mark.asyncio
async def test_get_providers_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/payments/providers")
    assert resp.status_code == 401
