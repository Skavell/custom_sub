import uuid
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_short_password_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "short",
            "display_name": "Test"
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePass123!",
            "display_name": "Test"
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_blocked_when_registration_disabled():
    """Returns 503 when registration_enabled=false."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.routers.auth.get_setting", new=AsyncMock(return_value="false")):
            resp = await client.post("/api/auth/register", json={
                "email": "user@gmail.com",
                "password": "SecurePass123!",
                "display_name": "User"
            })
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_register_blocked_by_domain_whitelist():
    """Returns 400 when email domain not in allowed_email_domains."""
    async def mock_get_setting(db, key):
        if key == "registration_enabled":
            return "true"
        if key == "allowed_email_domains":
            return "gmail.com,mail.ru"
        return None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.routers.auth.get_setting", new=AsyncMock(side_effect=mock_get_setting)):
            resp = await client.post("/api/auth/register", json={
                "email": "user@tempmail.org",
                "password": "SecurePass123!",
                "display_name": "User"
            })
    assert resp.status_code == 400
    assert "недоступна" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_allowed_when_domain_list_empty():
    """Any domain allowed when allowed_email_domains is empty."""
    async def mock_get_setting(db, key):
        if key == "registration_enabled":
            return "true"
        if key == "allowed_email_domains":
            return ""
        return None

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.display_name = "User"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.routers.auth.get_setting", new=AsyncMock(side_effect=mock_get_setting)):
            with patch("app.routers.auth.get_user_by_email", new=AsyncMock(return_value=(None, None))):
                with patch("app.routers.auth.create_user_with_provider", new=AsyncMock(return_value=mock_user)):
                    with patch("app.routers.auth._set_auth_cookies", new=AsyncMock()):
                        resp = await client.post("/api/auth/register", json={
                            "email": "user@anydomain.xyz",
                            "password": "SecurePass123!",
                            "display_name": "User"
                        })
    assert resp.status_code == 200
