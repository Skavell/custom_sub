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
