# backend/tests/routers/test_subscriptions.py
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.redis_client import get_redis
from app.deps import get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus


NOW = datetime.now(tz=timezone.utc)


def _make_user(remnawave_uuid=None) -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.remnawave_uuid = uuid.UUID(str(remnawave_uuid)) if remnawave_uuid else None
    user.has_made_payment = False
    user.first_connected_at = None
    return user


def _make_sub() -> Subscription:
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW
    sub.traffic_limit_gb = 30
    return sub


def _override_get_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_get_current_user(user):
    async def _dep():
        return user
    return _dep


def _override_get_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_trial_activate_already_activated():
    """Returns 409 if user already has remnawave_uuid."""
    user = _make_user(remnawave_uuid=uuid.uuid4())
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/subscriptions/trial")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_trial_activate_rate_limited():
    """Returns 429 when IP rate limit exceeded."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock()
    redis.incr.return_value = 4  # over limit of 3

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/subscriptions/trial")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_trial_activate_remnawave_not_configured():
    """Returns 503 when Remnawave settings are missing."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    redis = AsyncMock()
    redis.incr.return_value = 1  # within limit

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/subscriptions/trial")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_me_no_subscription():
    """Returns 200 with null when user has no subscription."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_trial_blocked_when_email_not_verified():
    """Returns 403 when email_verification_enabled=true and email not verified."""
    from app.models.auth_provider import AuthProvider, ProviderType

    user = _make_user()
    user.is_banned = False

    email_provider = MagicMock(spec=AuthProvider)
    email_provider.provider = ProviderType.email
    email_provider.email_verified = False

    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock()

    async def mock_get_setting(d, key):
        if key == "email_verification_enabled":
            return "true"
        if key == "remnawave_url":
            return "http://remnawave"
        if key == "remnawave_token":
            return "token"
        return None

    async def mock_get_setting_decrypted(d, key):
        return "token"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = email_provider
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)

    try:
        with patch("app.routers.subscriptions.get_setting", new=AsyncMock(side_effect=mock_get_setting)):
            with patch("app.routers.subscriptions.get_setting_decrypted", new=AsyncMock(side_effect=mock_get_setting_decrypted)):
                with patch("app.routers.subscriptions.check_rate_limit", new=AsyncMock(return_value=True)):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.post("/api/subscriptions/trial")
        assert resp.status_code == 403
        assert "Подтвердите email" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_with_subscription():
    """Returns subscription details when subscription exists."""
    from datetime import timedelta
    user = _make_user()
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "trial"
    assert data["status"] == "active"
    assert data["traffic_limit_gb"] == 30
    assert data["days_remaining"] >= 1


@pytest.mark.asyncio
async def test_get_me_returns_has_connected_false_when_not_connected():
    """Returns has_connected=False when first_connected_at is None."""
    from datetime import timedelta
    user = _make_user()
    user.first_connected_at = None
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = None  # cache miss

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_connected"] is False
    assert data["traffic_used_bytes"] is None


@pytest.mark.asyncio
async def test_get_me_returns_has_connected_true_from_db():
    """Returns has_connected=True when first_connected_at is set in DB."""
    from datetime import timedelta
    user = _make_user()
    user.first_connected_at = NOW

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["has_connected"] is True


@pytest.mark.asyncio
async def test_get_me_fetches_remnawave_traffic_from_cache():
    """Returns traffic_used_bytes from Redis cache for trial user."""
    import json as _json
    from datetime import timedelta
    rw_uuid = uuid.uuid4()
    user = _make_user(remnawave_uuid=rw_uuid)
    user.first_connected_at = NOW

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    cached = _json.dumps({
        "used_traffic_bytes": 5 * 1024 ** 3,
        "first_connected_at": NOW.isoformat(),
    })

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = cached

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["traffic_used_bytes"] == 5 * 1024 ** 3


@pytest.mark.asyncio
async def test_get_me_writes_first_connected_from_remnawave_fallback():
    """Writes first_connected_at from Remnawave API when DB is null (fallback)."""
    import json as _json
    from datetime import timedelta
    from app.services.remnawave_client import RemnawaveUser

    rw_uuid = uuid.uuid4()
    user = _make_user(remnawave_uuid=rw_uuid)
    user.remnawave_user_id = 12345
    user.first_connected_at = None

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    rw_user = RemnawaveUser(
        id=12345,
        short_uuid="abc123",
        username="ws_test",
        expire_at=NOW,
        traffic_limit_bytes=30 * 1024 ** 3,
        status="ACTIVE",
        subscription_url="https://example.com/sub",
        telegram_id=None,
        used_traffic_bytes=2 * 1024 ** 3,
        first_connected_at=NOW,
    )

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = None  # cache miss

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        with patch("app.routers.subscriptions.get_setting", new=AsyncMock(return_value="http://rw")):
            with patch("app.routers.subscriptions.get_setting_decrypted", new=AsyncMock(return_value="tok")):
                with patch("app.routers.subscriptions.RemnawaveClient") as MockRW:
                    MockRW.return_value.get_user = AsyncMock(return_value=rw_user)
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_connected"] is True
    assert data["traffic_used_bytes"] == 2 * 1024 ** 3
    assert user.first_connected_at == NOW
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_get_me_remnawave_unreachable_still_returns_200():
    """Returns 200 with has_connected from DB when Remnawave is unreachable."""
    from datetime import timedelta
    rw_uuid = uuid.uuid4()
    user = _make_user(remnawave_uuid=rw_uuid)
    user.remnawave_user_id = 12345
    user.first_connected_at = None

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = None  # cache miss

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        with patch("app.routers.subscriptions.get_setting", new=AsyncMock(return_value="http://rw")):
            with patch("app.routers.subscriptions.get_setting_decrypted", new=AsyncMock(return_value="tok")):
                with patch("app.routers.subscriptions.RemnawaveClient") as MockRW:
                    MockRW.return_value.get_user = AsyncMock(side_effect=Exception("timeout"))
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_connected"] is False
    assert data["traffic_used_bytes"] is None
