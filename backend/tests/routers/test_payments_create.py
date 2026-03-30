# backend/tests/routers/test_payments_create.py
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
from app.models.transaction import Transaction, TransactionStatus
from app.services.payment_providers.base import InvoiceResult

NOW = datetime.now(tz=timezone.utc)
PLAN_ID = uuid.uuid4()


def _make_user(remnawave_uuid=None) -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.remnawave_uuid = remnawave_uuid
    u.has_made_payment = False
    return u


def _make_plan(name="1_month", price=200, duration=30, new_user_price=100):
    p = MagicMock()
    p.id = PLAN_ID
    p.name = name
    p.label = "1 месяц"
    p.price_rub = price
    p.new_user_price_rub = new_user_price
    p.duration_days = duration
    p.is_active = True
    return p


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_create_payment_no_trial_returns_409():
    user = _make_user(remnawave_uuid=None)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(AsyncMock())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_payment_rate_limited_returns_429():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 6  # over limit of 5
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_create_payment_plan_not_found_returns_404():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(uuid.uuid4())})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_payment_not_configured_returns_503():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    db = AsyncMock(spec=AsyncSession)

    call_count = [0]
    def _side_effect(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # Plan query
            result.scalar_one_or_none = MagicMock(return_value=_make_plan())
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result
    db.execute = AsyncMock(side_effect=_side_effect)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_create_payment_duplicate_pending_returns_200():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    pending_tx = MagicMock(spec=Transaction)
    pending_tx.status = TransactionStatus.pending
    pending_tx.payment_url = "https://t.me/CryptoBot?start=IVexisting"
    pending_tx.id = uuid.uuid4()
    pending_tx.amount_rub = 200
    pending_tx.created_at = NOW  # recent

    db = AsyncMock(spec=AsyncSession)
    call_count = [0]
    def _side_effect(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=_make_plan())
        elif call_count[0] == 2:
            # get_active_provider: cryptobot_token → None (but we mock provider separately)
            result.scalar_one_or_none = MagicMock(return_value=None)
        else:
            result.scalar_one_or_none = MagicMock(return_value=pending_tx)
        return result
    db.execute = AsyncMock(side_effect=_side_effect)

    mock_provider = AsyncMock()
    mock_provider.create_invoice = AsyncMock(
        return_value=InvoiceResult(payment_url="https://t.me/CryptoBot?start=IVexisting", external_id="999")
    )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.payments.get_active_provider", return_value=mock_provider), \
         patch("app.routers.payments.get_pending_transaction", return_value=pending_tx):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["is_existing"] is True


@pytest.mark.asyncio
async def test_create_payment_success_returns_201():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    plan = _make_plan()
    new_tx = MagicMock(spec=Transaction)
    new_tx.id = uuid.uuid4()
    new_tx.amount_rub = 100  # new user price
    new_tx.payment_url = "https://t.me/CryptoBot?start=IVnew"

    mock_provider = AsyncMock()
    mock_provider.name = "cryptobot"
    mock_provider.create_invoice = AsyncMock(
        return_value=InvoiceResult(payment_url="https://t.me/CryptoBot?start=IVnew", external_id="123")
    )

    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=plan)))

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.payments.get_active_provider", return_value=mock_provider), \
         patch("app.routers.payments.get_pending_transaction", return_value=None), \
         patch("app.routers.payments.calculate_final_price", return_value=(100, None)), \
         patch("app.routers.payments._create_transaction", return_value=new_tx):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["payment_url"] == "https://t.me/CryptoBot?start=IVnew"
    assert data["is_existing"] is False
