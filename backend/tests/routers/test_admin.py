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

from app.models.plan import Plan as PlanModel


# --- GET /api/admin/plans ---

@pytest.mark.asyncio
async def test_admin_plans_list_returns_all_including_inactive():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    plan = MagicMock(spec=PlanModel)
    plan.id = uuid.uuid4()
    plan.name = "basic"
    plan.label = "Базовый"
    plan.duration_days = 30
    plan.price_rub = 300
    plan.new_user_price_rub = None
    plan.is_active = False  # inactive — must still appear
    plan.sort_order = 0

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [plan]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/plans")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_active"] is False
    assert data[0]["label"] == "Базовый"


@pytest.mark.asyncio
async def test_admin_plan_patch_updates_fields():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    plan = MagicMock(spec=PlanModel)
    plan.id = uuid.uuid4()
    plan.name = "basic"
    plan.label = "Базовый"
    plan.duration_days = 30
    plan.price_rub = 300
    plan.new_user_price_rub = None
    plan.is_active = True
    plan.sort_order = 0

    db.get = AsyncMock(return_value=plan)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(
                f"/api/admin/plans/{plan.id}",
                json={"price_rub": 500, "is_active": False},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert plan.price_rub == 500
    assert plan.is_active is False
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_admin_plan_patch_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(f"/api/admin/plans/{uuid.uuid4()}", json={"price_rub": 100})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


from app.models.promo_code import PromoCode as PromoCodeModel, PromoCodeType
from sqlalchemy.exc import IntegrityError


# --- GET /api/admin/promo-codes ---

@pytest.mark.asyncio
async def test_admin_promo_list_returns_all():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    promo = MagicMock(spec=PromoCodeModel)
    promo.id = uuid.uuid4()
    promo.code = "SALE10"
    promo.type = PromoCodeType.discount_percent
    promo.value = 10
    promo.max_uses = None
    promo.used_count = 0
    promo.valid_until = None
    promo.is_active = True
    promo.created_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [promo]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/promo-codes")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "SALE10"


@pytest.mark.asyncio
async def test_admin_promo_create_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # After refresh, simulate DB populating server-default fields
    async def _refresh_promo(obj):
        obj.id = uuid.uuid4()
        obj.used_count = 0
        obj.created_at = NOW
    db.refresh = AsyncMock(side_effect=_refresh_promo)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/promo-codes",
                json={"code": "test10", "type": "discount_percent", "value": 10},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "TEST10"  # uppercased


@pytest.mark.asyncio
async def test_admin_promo_create_duplicate_returns_409():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, Exception()))
    db.rollback = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/promo-codes",
                json={"code": "EXISTING", "type": "bonus_days", "value": 7},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_promo_toggle_flips_is_active():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    promo = MagicMock(spec=PromoCodeModel)
    promo.id = uuid.uuid4()
    promo.code = "SALE10"
    promo.type = PromoCodeType.discount_percent
    promo.value = 10
    promo.max_uses = None
    promo.used_count = 0
    promo.valid_until = None
    promo.is_active = True
    promo.created_at = NOW

    db.get = AsyncMock(return_value=promo)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(f"/api/admin/promo-codes/{promo.id}/toggle")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert promo.is_active is False
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_admin_promo_delete_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    promo = MagicMock(spec=PromoCodeModel)
    db.get = AsyncMock(return_value=promo)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api/admin/promo-codes/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    db.delete.assert_called_once_with(promo)
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_admin_promo_delete_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api/admin/promo-codes/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


from app.models.article import Article as ArticleModel


def _make_article(published=True):
    a = MagicMock(spec=ArticleModel)
    a.id = uuid.uuid4()
    a.slug = "test-article"
    a.title = "Тест"
    a.content = "Содержимое"
    a.preview_image_url = None
    a.is_published = published
    a.sort_order = 0
    a.created_at = NOW
    a.updated_at = NOW
    return a


# --- GET /api/admin/articles ---

@pytest.mark.asyncio
async def test_admin_articles_list_includes_unpublished():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article(published=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [article]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/articles")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_published"] is False


@pytest.mark.asyncio
async def test_admin_article_create_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # After refresh, simulate DB populating server-default fields
    async def _refresh_article(obj):
        obj.id = uuid.uuid4()
        obj.created_at = NOW
        obj.updated_at = NOW
    db.refresh = AsyncMock(side_effect=_refresh_article)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/articles",
                json={"slug": "new-article", "title": "Новая", "content": "Текст"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_admin_article_create_duplicate_slug_returns_409():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, Exception()))
    db.rollback = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/articles",
                json={"slug": "existing-slug", "title": "Новая", "content": "Текст"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_article_get_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/admin/articles/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_article_patch_updates_title():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article()
    db.get = AsyncMock(return_value=article)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(
                f"/api/admin/articles/{article.id}",
                json={"title": "Обновлённый заголовок"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert article.title == "Обновлённый заголовок"


@pytest.mark.asyncio
async def test_admin_article_delete_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article()
    db.get = AsyncMock(return_value=article)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api/admin/articles/{article.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    db.delete.assert_called_once_with(article)


@pytest.mark.asyncio
async def test_admin_article_publish_sets_published():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article(published=False)
    db.get = AsyncMock(return_value=article)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/admin/articles/{article.id}/publish")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert article.is_published is True


@pytest.mark.asyncio
async def test_admin_article_unpublish_clears_published():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article(published=True)
    db.get = AsyncMock(return_value=article)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/admin/articles/{article.id}/unpublish")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert article.is_published is False


from app.models.setting import Setting as SettingModel


# --- GET /api/admin/settings ---

@pytest.mark.asyncio
async def test_admin_settings_list_masks_sensitive():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    s = MagicMock(spec=SettingModel)
    s.key = "telegram_bot_token"
    s.value = {"encrypted": "abc123"}
    s.is_sensitive = True
    s.updated_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [s]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/settings")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["value"] == "***"
    assert data[0]["is_sensitive"] is True


@pytest.mark.asyncio
async def test_admin_settings_list_shows_plain_value():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    s = MagicMock(spec=SettingModel)
    s.key = "remnawave_url"
    s.value = {"value": "http://rw.example.com"}
    s.is_sensitive = False
    s.updated_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [s]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/settings")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["value"] == "http://rw.example.com"


@pytest.mark.asyncio
async def test_admin_settings_upsert_plain():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.set_setting", new_callable=AsyncMock) as mock_set:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.put(
                    "/api/admin/settings/remnawave_url",
                    json={"value": "http://rw.example.com", "is_sensitive": False},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_set.assert_called_once_with(db, "remnawave_url", "http://rw.example.com", False)
    data = resp.json()
    assert data["value"] == "http://rw.example.com"


@pytest.mark.asyncio
async def test_admin_settings_upsert_sensitive_masks_value():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.set_setting", new_callable=AsyncMock) as mock_set:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.put(
                    "/api/admin/settings/telegram_bot_token",
                    json={"value": "secret_token", "is_sensitive": True},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_set.assert_called_once_with(db, "telegram_bot_token", "secret_token", True)
    data = resp.json()
    assert data["value"] == "***"
    assert data["is_sensitive"] is True


from app.models.support_message import SupportMessage as SupportMessageModel


# --- GET /api/admin/support-messages ---

@pytest.mark.asyncio
async def test_admin_support_messages_list_returns_items():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    msg = MagicMock(spec=SupportMessageModel)
    msg.id = uuid.uuid4()
    msg.user_id = uuid.uuid4()
    msg.display_name = "Иван"
    msg.message = "Нужна помощь"
    msg.created_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [msg]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/support-messages")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Иван"
    assert data[0]["message"] == "Нужна помощь"


@pytest.mark.asyncio
async def test_admin_support_messages_not_admin_returns_403():
    from fastapi import HTTPException

    def _not_admin():
        raise HTTPException(status_code=403, detail="Admin required")

    app.dependency_overrides[require_admin] = _not_admin
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/support-messages")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403
