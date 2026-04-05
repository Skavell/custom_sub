import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch

from app.main import app
from app.deps import get_current_user
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType

NOW = datetime.now(tz=timezone.utc)


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Ivan"
    u.is_admin = False
    u.created_at = NOW
    return u


@pytest.mark.asyncio
async def test_link_google_success():
    """POST /api/users/me/providers/google links Google to existing user."""
    user = _make_user()

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # provider not yet linked
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        yield db

    from app.database import get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    g_user = MagicMock()
    g_user.id = "google-123"
    g_user.name = "Ivan"
    g_user.picture = None

    try:
        with patch("app.routers.users.exchange_google_code", new_callable=AsyncMock, return_value=g_user):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/users/me/providers/google", json={
                    "code": "auth-code",
                    "redirect_uri": "http://localhost/auth/google/callback",
                })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_link_google_already_linked():
    """Returns 409 if Google is already linked to any user."""
    user = _make_user()

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        existing = MagicMock(spec=AuthProvider)
        existing.user_id = user.id
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result_mock)
        yield db

    from app.database import get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    g_user = MagicMock()
    g_user.id = "google-123"

    try:
        with patch("app.routers.users.exchange_google_code", new_callable=AsyncMock, return_value=g_user), \
             patch("app.routers.users.get_setting", new_callable=AsyncMock, return_value=None), \
             patch("app.routers.users.get_setting_decrypted", new_callable=AsyncMock, return_value=None):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/users/me/providers/google", json={
                    "code": "auth-code",
                    "redirect_uri": "http://localhost/auth/google/callback",
                })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_link_google_taken_by_other_user():
    """Returns 409 if Google account belongs to a different user."""
    user = _make_user()
    other_user_id = uuid.uuid4()

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        existing = MagicMock(spec=AuthProvider)
        existing.user_id = other_user_id  # different user
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result_mock)
        yield db

    from app.database import get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    g_user = MagicMock()
    g_user.id = "google-123"

    try:
        with patch("app.routers.users.exchange_google_code", new_callable=AsyncMock, return_value=g_user), \
             patch("app.routers.users.get_setting", new_callable=AsyncMock, return_value=None), \
             patch("app.routers.users.get_setting_decrypted", new_callable=AsyncMock, return_value=None):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/users/me/providers/google", json={
                    "code": "auth-code",
                    "redirect_uri": "http://localhost/auth/google/callback",
                })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_link_email_requires_auth():
    """Without cookie, returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/users/me/providers/email", json={
            "email": "new@example.com",
            "password": "Password123!"
        })
    assert resp.status_code == 401
