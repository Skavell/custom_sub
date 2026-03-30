# backend/tests/routers/test_admin.py
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.deps import require_admin
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.auth_provider import AuthProvider, ProviderType
from app.models.transaction import Transaction, TransactionStatus, TransactionType

NOW = datetime.now(tz=timezone.utc)


def _make_admin():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Admin"
    u.is_admin = True
    u.remnawave_uuid = None
    u.has_made_payment = False
    u.subscription_conflict = False
    u.avatar_url = None
    u.created_at = NOW
    u.last_seen_at = NOW
    u.subscription = None
    u.auth_providers = []
    u.transactions = []
    return u


def _make_regular_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Иван"
    u.avatar_url = None
    u.is_admin = False
    u.remnawave_uuid = uuid.uuid4()
    u.has_made_payment = True
    u.subscription_conflict = False
    u.created_at = NOW
    u.last_seen_at = NOW
    # subscription
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.paid
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW
    sub.traffic_limit_gb = None
    sub.synced_at = NOW
    u.subscription = sub
    # providers
    prov = MagicMock(spec=AuthProvider)
    prov.provider = ProviderType.telegram
    prov.provider_user_id = "123456"
    prov.provider_username = "ivan"
    prov.created_at = NOW
    u.auth_providers = [prov]
    # transactions
    u.transactions = []
    return u


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_admin(user):
    async def _dep():
        return user
    return _dep


# --- GET /api/admin/users ---

@pytest.mark.asyncio
async def test_admin_users_list_not_admin_returns_403():
    from fastapi import HTTPException

    def _not_admin():
        raise HTTPException(status_code=403, detail="Admin required")

    app.dependency_overrides[require_admin] = _not_admin
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/users")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_users_list_returns_200():
    admin = _make_admin()
    user = _make_regular_user()
    db = AsyncMock(spec=AsyncSession)

    result_mock = MagicMock()
    result_mock.scalars.return_value.unique.return_value.all.return_value = [user]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/users")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Иван"
    assert data[0]["subscription_status"] == "active"
    assert "telegram" in data[0]["providers"]


@pytest.mark.asyncio
async def test_admin_users_list_search_passes_q():
    """Verify endpoint accepts q param without error."""
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalars.return_value.unique.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/users?q=Иван&skip=0&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == []


# --- GET /api/admin/users/{user_id} ---

@pytest.mark.asyncio
async def test_admin_user_detail_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    ))

    # First execute call returns None for user
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/admin/users/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_user_detail_returns_full_info():
    admin = _make_admin()
    user = _make_regular_user()
    db = AsyncMock(spec=AsyncSession)
    # db.get returns the user (with selectinload already applied via separate query)
    # Use execute for the select with options
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    tx_result = MagicMock()
    tx_result.scalars.return_value.all.return_value = []

    call_count = [0]
    def _side(*a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            return result_mock  # user query
        return tx_result  # transactions query

    db.execute = AsyncMock(side_effect=_side)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/admin/users/{user.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Иван"
    assert data["subscription"]["status"] == "active"
    assert len(data["providers"]) == 1
    assert data["providers"][0]["provider"] == "telegram"


# --- POST /api/admin/users/{user_id}/sync ---

@pytest.mark.asyncio
async def test_admin_user_sync_no_rw_uuid_returns_409():
    admin = _make_admin()
    user = _make_regular_user()
    user.remnawave_uuid = None
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/admin/users/{user.id}/sync")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_user_sync_rw_not_configured_returns_503():
    admin = _make_admin()
    user = _make_regular_user()
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.get_setting", return_value=None), \
         patch("app.routers.admin.get_setting_decrypted", return_value=None):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(f"/api/admin/users/{user.id}/sync")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_admin_user_sync_success_returns_200():
    admin = _make_admin()
    user = _make_regular_user()
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.get_setting", return_value="http://rw"), \
         patch("app.routers.admin.get_setting_decrypted", return_value="token"), \
         patch("app.routers.admin.RemnawaveClient") as mock_rw_cls, \
         patch("app.routers.admin.sync_subscription_from_remnawave", new_callable=AsyncMock):
        mock_rw_cls.return_value.get_user = AsyncMock(return_value=MagicMock())
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(f"/api/admin/users/{user.id}/sync")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# --- POST /api/admin/users/{user_id}/resolve-conflict ---

@pytest.mark.asyncio
async def test_admin_resolve_conflict_user_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"/api/admin/users/{uuid.uuid4()}/resolve-conflict",
                json={"remnawave_uuid": str(uuid.uuid4())},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_resolve_conflict_success_clears_flag():
    admin = _make_admin()
    user = _make_regular_user()
    user.subscription_conflict = True
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    new_rw_uuid = str(uuid.uuid4())
    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.get_setting", return_value="http://rw"), \
         patch("app.routers.admin.get_setting_decrypted", return_value="token"), \
         patch("app.routers.admin.RemnawaveClient") as mock_rw_cls, \
         patch("app.routers.admin.sync_subscription_from_remnawave", new_callable=AsyncMock):
        mock_rw_cls.return_value.get_user = AsyncMock(return_value=MagicMock())
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    f"/api/admin/users/{user.id}/resolve-conflict",
                    json={"remnawave_uuid": new_rw_uuid},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert user.subscription_conflict is False
    db.commit.assert_called()


from redis.asyncio import Redis
from app.redis_client import get_redis
import json


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


# --- POST /api/admin/sync/all ---

@pytest.mark.asyncio
async def test_admin_sync_all_returns_task_id():
    admin = _make_admin()
    redis = AsyncMock(spec=Redis)
    redis.set = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.admin.run_sync_all", new_callable=AsyncMock):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/admin/sync/all")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert "task_id" in data
    # Verify initial status stored in Redis
    redis.set.assert_called()


# --- GET /api/admin/sync/status/{task_id} ---

@pytest.mark.asyncio
async def test_admin_sync_status_returns_data():
    admin = _make_admin()
    task_id = str(uuid.uuid4())
    status_data = {"status": "running", "total": 10, "done": 3, "errors": 0}
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=json.dumps(status_data))

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/admin/sync/status/{task_id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["total"] == 10
    assert data["done"] == 3


@pytest.mark.asyncio
async def test_admin_sync_status_not_found_returns_404():
    admin = _make_admin()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/admin/sync/status/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
