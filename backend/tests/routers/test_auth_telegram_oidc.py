"""Tests for Telegram OIDC login endpoint and oauth-config fields."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.auth.oauth.telegram import TelegramUser


# ---------------------------------------------------------------------------
# Test 1 — 503 when Telegram OIDC is not configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telegram_oidc_not_configured():
    """POST /api/auth/oauth/telegram-oidc returns 503 when no settings in DB."""
    with (
        patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
        patch("app.routers.auth.get_setting_decrypted", new_callable=AsyncMock) as mock_get_dec,
    ):
        mock_get.return_value = None
        mock_get_dec.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/oauth/telegram-oidc",
                json={"code": "some-code", "redirect_uri": "https://example.com/callback"},
            )

    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Test 2 — 200 + cookie + display_name when OIDC exchange succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telegram_oidc_creates_new_user():
    """POST /api/auth/oauth/telegram-oidc creates a new user and returns access_token cookie."""
    fake_tg_user = TelegramUser(
        id=99999,
        first_name="Ivan",
        last_name="Test",
        username="ivantest",
        photo_url=None,
    )

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.display_name = "Ivan Test"

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.setex = AsyncMock()

    from app.redis_client import get_redis

    async def _get_redis_override():
        return mock_redis

    app.dependency_overrides[get_redis] = _get_redis_override

    try:
        with (
            patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
            patch("app.routers.auth.get_setting_decrypted", new_callable=AsyncMock) as mock_get_dec,
            patch(
                "app.routers.auth.exchange_telegram_oidc_code",
                new_callable=AsyncMock,
                return_value=fake_tg_user,
            ),
            patch("app.routers.auth.get_user_by_provider", new_callable=AsyncMock, return_value=None),
            patch(
                "app.routers.auth.create_user_with_provider",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "app.routers.auth._sync_remnawave_on_first_telegram_login",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            # Return non-None values so the "not configured" guard is passed
            mock_get.return_value = "12345678"
            mock_get_dec.return_value = "fake-secret"

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/auth/oauth/telegram-oidc",
                    json={"code": "auth-code-xyz", "redirect_uri": "https://example.com/callback"},
                )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Ivan Test"
    # access_token cookie must be set
    assert "access_token" in resp.cookies


# ---------------------------------------------------------------------------
# Test 3 — oauth-config includes telegram_oidc fields when enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oauth_config_includes_telegram_oidc_fields():
    """GET /api/auth/oauth-config returns telegram_oidc=True and telegram_oidc_client_id when enabled."""
    def mock_get(db, key):
        mapping = {
            "telegram_oidc_enabled": "true",
            "telegram_oidc_client_id": "12345678",
        }
        return mapping.get(key)

    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", side_effect=mock_get),
        patch("app.routers.auth.get_setting_decrypted", new_callable=AsyncMock) as mock_get_dec,
    ):
        mock_settings.google_client_id = ""
        mock_settings.vk_client_id = ""
        mock_get_dec.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_oidc"] is True
    assert data["telegram_oidc_client_id"] == "12345678"
