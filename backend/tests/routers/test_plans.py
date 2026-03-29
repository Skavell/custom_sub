import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.plan import Plan


def _make_plan(name, label, price, duration, sort_order=0, new_user_price=None):
    p = MagicMock(spec=Plan)
    p.id = "00000000-0000-0000-0000-000000000001"
    p.name = name
    p.label = label
    p.price_rub = price
    p.new_user_price_rub = new_user_price
    p.duration_days = duration
    p.is_active = True
    p.sort_order = sort_order
    return p


def _override_get_db(plans: list):
    async def _get_db_override():
        scalars = MagicMock()
        scalars.all.return_value = plans
        result = MagicMock()
        result.scalars.return_value = scalars
        db = AsyncMock(spec=AsyncSession)
        db.execute.return_value = result
        yield db
    return _get_db_override


@pytest.mark.asyncio
async def test_list_plans_returns_active_plans():
    plans = [
        _make_plan("1_month", "1 месяц", 200, 30, sort_order=1, new_user_price=100),
        _make_plan("3_months", "3 месяца", 590, 90, sort_order=2),
    ]
    app.dependency_overrides[get_db] = _override_get_db(plans)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/plans")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "1_month"
    assert data[0]["price_rub"] == 200
    assert data[0]["new_user_price_rub"] == 100
    assert data[1]["name"] == "3_months"
    assert data[1]["new_user_price_rub"] is None


@pytest.mark.asyncio
async def test_list_plans_empty():
    app.dependency_overrides[get_db] = _override_get_db([])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/plans")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == []
