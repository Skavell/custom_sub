import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch
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
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', created_plan_id) or setattr(obj, 'is_active', True) or setattr(obj, 'sort_order', 0) or setattr(obj, 'new_user_price_rub', None))
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


@pytest.mark.asyncio
async def test_create_plan_requires_admin():
    """POST /api/admin/plans returns 403 without admin."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/admin/plans", json={
            "name": "x", "label": "X", "duration_days": 30, "price_rub": 100
        })
    assert resp.status_code in (401, 403)
