import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.mark.asyncio
async def test_oauth_config_all_disabled():
    """When no env vars and no DB settings, all providers disabled."""
    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
        patch("app.routers.auth.get_setting_decrypted", new_callable=AsyncMock) as mock_get_dec,
    ):
        mock_settings.google_client_id = ""
        mock_settings.vk_client_id = ""
        mock_get.return_value = None
        mock_get_dec.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["google"] is False
    assert data["vk"] is False
    assert data["telegram"] is False
    assert data["telegram_bot_username"] is None


@pytest.mark.asyncio
async def test_oauth_config_google_enabled():
    """When GOOGLE_CLIENT_ID is set, google=true."""
    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
        patch("app.routers.auth.get_setting_decrypted", new_callable=AsyncMock) as mock_get_dec,
    ):
        mock_settings.google_client_id = "some-client-id"
        mock_settings.vk_client_id = ""
        mock_get.return_value = None
        mock_get_dec.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    assert resp.json()["google"] is True


@pytest.mark.asyncio
async def test_oauth_config_has_email_verification_required():
    """Response includes email_verification_required field."""
    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
        patch("app.routers.auth.get_setting_decrypted", new_callable=AsyncMock) as mock_get_dec,
    ):
        mock_settings.google_client_id = ""
        mock_settings.vk_client_id = ""
        mock_get.return_value = None
        mock_get_dec.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    data = resp.json()
    assert "email_verification_required" in data
    assert isinstance(data["email_verification_required"], bool)


@pytest.mark.asyncio
async def test_oauth_config_telegram_enabled_with_username():
    """When telegram_bot_token is in DB and bot_username set, telegram=true with username."""
    async def mock_get(db, key):
        if key == "telegram_bot_username":
            return "mybot"
        return None

    async def mock_get_dec(db, key):
        if key == "telegram_bot_token":
            return "some-token"
        return None

    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", side_effect=mock_get),
        patch("app.routers.auth.get_setting_decrypted", side_effect=mock_get_dec),
    ):
        mock_settings.google_client_id = ""
        mock_settings.vk_client_id = ""

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram"] is True
    assert data["telegram_bot_username"] == "mybot"
