import pytest
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
