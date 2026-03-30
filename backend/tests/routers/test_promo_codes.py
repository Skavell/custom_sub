# backend/tests/routers/test_promo_codes.py
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.promo_code import PromoCode, PromoCodeType


NOW = datetime.now(tz=timezone.utc)


def _make_user(remnawave_uuid=None):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.remnawave_uuid = remnawave_uuid if remnawave_uuid is not None else uuid.uuid4()
    return u


def _make_promo(type_=PromoCodeType.bonus_days, value=30):
    p = MagicMock(spec=PromoCode)
    p.id = uuid.uuid4()
    p.code = "BONUS30"
    p.type = type_
    p.value = value
    return p


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


# --- GET /api/promo-codes/validate/{code} ---

@pytest.mark.asyncio
async def test_validate_invalid_code_returns_404():
    from fastapi import HTTPException
    user = _make_user()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch(
        "app.routers.promo_codes.validate_promo_code",
        side_effect=HTTPException(status_code=404, detail="Промокод не найден"),
    ):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/promo-codes/validate/NOPE")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_discount_code_returns_200():
    user = _make_user()
    promo = _make_promo(type_=PromoCodeType.discount_percent, value=20)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch("app.routers.promo_codes.validate_promo_code", return_value=(promo, False)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/promo-codes/validate/SAVE20")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "BONUS30"
    assert data["type"] == "discount_percent"
    assert data["value"] == 20
    assert data["already_used"] is False


@pytest.mark.asyncio
async def test_validate_already_used_code_returns_200_with_flag():
    user = _make_user()
    promo = _make_promo(type_=PromoCodeType.bonus_days, value=30)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch("app.routers.promo_codes.validate_promo_code", return_value=(promo, True)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/promo-codes/validate/BONUS30")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["already_used"] is True


# --- POST /api/promo-codes/apply ---

@pytest.mark.asyncio
async def test_apply_no_trial_returns_409():
    user = _make_user()
    user.remnawave_uuid = None
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/promo-codes/apply", json={"code": "BONUS30"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_apply_discount_code_returns_400():
    user = _make_user()
    promo = _make_promo(type_=PromoCodeType.discount_percent, value=20)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch("app.routers.promo_codes.validate_promo_code", return_value=(promo, False)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/promo-codes/apply", json={"code": "SAVE20"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "скидки" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_apply_already_used_returns_400():
    user = _make_user()
    promo = _make_promo(type_=PromoCodeType.bonus_days, value=30)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch("app.routers.promo_codes.validate_promo_code", return_value=(promo, True)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/promo-codes/apply", json={"code": "BONUS30"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "использован" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_apply_rw_not_configured_returns_503():
    user = _make_user()
    promo = _make_promo(type_=PromoCodeType.bonus_days, value=30)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch("app.routers.promo_codes.validate_promo_code", return_value=(promo, False)), \
         patch("app.routers.promo_codes.get_setting", return_value=None), \
         patch("app.routers.promo_codes.get_setting_decrypted", return_value=None), \
         patch("app.routers.promo_codes.send_admin_alert", new_callable=AsyncMock):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/promo-codes/apply", json={"code": "BONUS30"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_apply_success_returns_200():
    user = _make_user()
    promo = _make_promo(type_=PromoCodeType.bonus_days, value=30)
    new_expires = NOW + timedelta(days=35)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))

    with patch("app.routers.promo_codes.validate_promo_code", return_value=(promo, False)), \
         patch("app.routers.promo_codes.get_setting", return_value="http://rw"), \
         patch("app.routers.promo_codes.get_setting_decrypted", return_value="token"), \
         patch("app.routers.promo_codes.RemnawaveClient"), \
         patch("app.routers.promo_codes.apply_bonus_days", return_value=(30, new_expires)):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/promo-codes/apply", json={"code": "BONUS30"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["days_added"] == 30
    assert "new_expires_at" in data
