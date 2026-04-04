import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.deps import require_admin
from app.models.user import User

NOW = datetime.now(tz=timezone.utc)


def _make_admin():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Admin"
    u.is_admin = True
    return u


@pytest.mark.asyncio
async def test_create_plan_success():
    """POST /api/admin/plans creates a plan and returns 201."""
    admin = _make_admin()
    created_plan_id = uuid.uuid4()

    async def override_require_admin():
        return admin

    async def override_get_db():
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        async def refresh_impl(obj):
            obj.id = created_plan_id
            obj.is_active = True
            obj.sort_order = 0
            obj.new_user_price_rub = None

        db.refresh = AsyncMock(side_effect=refresh_impl)
        yield db

    from app.database import get_db
    app.dependency_overrides[require_admin] = override_require_admin
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/admin/plans", json={
                "name": "custom_plan",
                "label": "Кастомный тариф",
                "duration_days": 60,
                "price_rub": 450,
            })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "custom_plan"
    assert data["label"] == "Кастомный тариф"
    assert data["duration_days"] == 60
    assert data["price_rub"] == 450


@pytest.mark.asyncio
async def test_create_plan_duplicate_name_returns_409():
    """POST /api/admin/plans returns 409 when name already exists."""
    admin = _make_admin()

    async def override_require_admin():
        return admin

    async def override_get_db():
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("unique constraint")))
        db.rollback = AsyncMock()
        yield db

    from app.database import get_db
    app.dependency_overrides[require_admin] = override_require_admin
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/admin/plans", json={
                "name": "1_month",
                "label": "1 месяц",
                "duration_days": 30,
                "price_rub": 200,
            })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_plan_requires_admin():
    """POST /api/admin/plans returns 401/403 without admin."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/admin/plans", json={
            "name": "x", "label": "X", "duration_days": 30, "price_rub": 100
        })
    assert resp.status_code in (401, 403)
