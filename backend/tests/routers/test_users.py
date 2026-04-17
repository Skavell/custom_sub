import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.deps import get_current_user
from app.database import get_db
from app.redis_client import get_redis
from app.models.auth_provider import AuthProvider, ProviderType
from app.models.user import User


def _make_user(
    user_id: uuid.UUID | None = None,
    display_name: str = "Test User",
    is_admin: bool = False,
) -> User:
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.display_name = display_name
    user.is_admin = is_admin
    user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return user


def _make_provider(
    user_id: uuid.UUID,
    provider: ProviderType,
    username: str | None = None,
    provider_user_id: str | None = None,
    email_verified: bool | None = None,
) -> AuthProvider:
    ap = MagicMock(spec=AuthProvider)
    ap.user_id = user_id
    ap.provider = provider
    ap.provider_username = username
    ap.provider_user_id = provider_user_id
    ap.email_verified = email_verified
    return ap


def _make_db_with_providers(providers: list[AuthProvider]) -> AsyncSession:
    """Return a mock AsyncSession whose execute().scalars().all() returns `providers`."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = providers

    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_mock
    return db


def _override_get_db(db: AsyncSession):
    """Return an async generator factory that yields the given db mock."""
    async def _get_db_override():
        yield db
    return _get_db_override


def _override_get_current_user(user: User):
    """Return a dependency override that returns the given user."""
    async def _get_current_user_override():
        return user
    return _get_current_user_override


def _override_db(db):
    """Return an async generator factory that yields the given db mock."""
    async def _get_db_override():
        yield db
    return _get_db_override


def _override_redis(redis):
    """Return an async generator factory that yields the given redis mock."""
    async def _get_redis_override():
        yield redis
    return _get_redis_override


# ---------------------------------------------------------------------------
# GET /api/users/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_profile():
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id, display_name="Alice", is_admin=False)

    providers = [
        _make_provider(user_id, ProviderType.email, "alice@example.com"),
        _make_provider(user_id, ProviderType.google, "alice_google"),
    ]
    db = _make_db_with_providers(providers)

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/users/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(user_id)
    assert data["display_name"] == "Alice"
    assert data["is_admin"] is False
    assert "created_at" in data
    assert len(data["providers"]) == 2
    types = {p["type"] for p in data["providers"]}
    assert types == {"email", "google"}


@pytest.mark.asyncio
async def test_get_me_unauthenticated():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/users/me")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/users/me/providers/{provider}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_provider_success():
    """Delete VK provider when user also has email — should succeed with 204."""
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)

    vk_provider = _make_provider(user_id, ProviderType.vk, "vk_user")
    email_provider = _make_provider(user_id, ProviderType.email, "user@example.com")
    providers = [vk_provider, email_provider]

    db = _make_db_with_providers(providers)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete("/api/users/me/providers/vk")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    db.delete.assert_awaited_once_with(vk_provider)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_last_provider_forbidden():
    """Cannot remove the only provider."""
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)

    vk_provider = _make_provider(user_id, ProviderType.vk, "vk_user")
    providers = [vk_provider]

    db = _make_db_with_providers(providers)

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete("/api/users/me/providers/vk")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_email_provider_forbidden():
    """Cannot remove email provider even when other providers exist."""
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)

    email_provider = _make_provider(user_id, ProviderType.email, "user@example.com")
    google_provider = _make_provider(user_id, ProviderType.google, "user_google")
    providers = [email_provider, google_provider]

    db = _make_db_with_providers(providers)

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete("/api/users/me/providers/email")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_nonexistent_provider():
    """Returns 404 when provider is not linked."""
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)

    email_provider = _make_provider(user_id, ProviderType.email, "user@example.com")
    providers = [email_provider]

    db = _make_db_with_providers(providers)

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete("/api/users/me/providers/vk")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_provider_unauthenticated():
    """Returns 401 when no auth cookie is present."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete("/api/users/me/providers/vk")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_invalid_provider_name():
    """Returns 422 for unknown provider type."""
    user_id = uuid.uuid4()
    user = _make_user(user_id=user_id)
    db = _make_db_with_providers([])

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete("/api/users/me/providers/twitter")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


# --- change password tests ---

@pytest.mark.asyncio
async def test_change_password_no_email_provider_returns_400():
    user = _make_user()
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # no email provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")  # pwd_v check in get_current_user

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/users/me/password", json={
                "old_password": "OldPass1",
                "new_password": "NewPass1"
            })
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_wrong_old_password_returns_400():
    user = _make_user()
    provider = _make_provider(user.id, ProviderType.email, provider_user_id="u@test.com")
    provider.password_hash = "some_hash"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")

    with patch("app.routers.users.verify_password", return_value=False):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch("/api/users/me/password", json={
                    "old_password": "WrongPass1",
                    "new_password": "NewPass1"
                })
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 400
    assert "Неверный" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_change_password_success():
    user = _make_user()
    provider = _make_provider(user.id, ProviderType.email, provider_user_id="u@test.com")
    provider.password_hash = "old_hash"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")
    redis.incr = AsyncMock()

    with (
        patch("app.routers.users.verify_password", return_value=True),
        patch("app.routers.users.hash_password", return_value="new_hash"),
    ):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch("/api/users/me/password", json={
                    "old_password": "OldPass1",
                    "new_password": "NewPass1"
                })
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert provider.password_hash == "new_hash"
    redis.incr.assert_called_once()


# --- update display name tests ---

@pytest.mark.asyncio
async def test_update_display_name_success():
    user = _make_user(display_name="OldName")
    db = AsyncMock()
    db.commit = AsyncMock()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/users/me", json={"display_name": "  NewName  "})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.display_name == "NewName"  # stripped


@pytest.mark.asyncio
async def test_update_display_name_empty_returns_422():
    user = _make_user()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/users/me", json={"display_name": "   "})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
