import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.mark.asyncio
async def test_install_app_config_returns_defaults():
    """When no DB settings, returns hardcoded defaults."""
    with patch("app.routers.install.get_setting", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/install/app-config")

    assert resp.status_code == 200
    data = resp.json()
    assert "android" in data
    assert "ios" in data
    assert "windows" in data
    assert "macos" in data
    assert "linux" in data
    assert data["android"]["app_name"] == "FlClash"
    assert data["ios"]["app_name"] == "Clash Mi"


@pytest.mark.asyncio
async def test_install_app_config_overrides_from_db():
    """When DB settings exist, they override defaults."""
    async def mock_get(db, key):
        overrides = {
            "install_ios_app_name": "Streisand",
            "install_ios_store_url": "https://apps.apple.com/app/streisand/id6450534064",
        }
        return overrides.get(key)

    with patch("app.routers.install.get_setting", side_effect=mock_get):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/install/app-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ios"]["app_name"] == "Streisand"
    assert data["ios"]["store_url"] == "https://apps.apple.com/app/streisand/id6450534064"
    assert data["android"]["app_name"] == "FlClash"
