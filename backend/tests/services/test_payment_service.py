import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.promo_code import PromoCode, PromoCodeType
from app.models.user import User
from app.services.payment_service import calculate_final_price


NOW = datetime.now(tz=timezone.utc)


def _make_plan(name="1_month", price=200, new_user_price=100, duration=30):
    p = MagicMock(spec=Plan)
    p.name = name
    p.price_rub = price
    p.new_user_price_rub = new_user_price
    p.duration_days = duration
    return p


def _make_user(has_made_payment=False):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.has_made_payment = has_made_payment
    return u


def _make_db_no_promo():
    """DB that returns no promo code, no prior usage."""
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_price_no_discount_returns_plan_price():
    plan = _make_plan(price=200, new_user_price=None)
    user = _make_user(has_made_payment=True)  # returning user, no new_user discount
    final, promo = await calculate_final_price(_make_db_no_promo(), plan, user, None)
    assert final == 200
    assert promo is None


@pytest.mark.asyncio
async def test_price_new_user_returns_lower_price():
    plan = _make_plan(price=200, new_user_price=100)
    user = _make_user(has_made_payment=False)
    final, promo = await calculate_final_price(_make_db_no_promo(), plan, user, None)
    assert final == 100


@pytest.mark.asyncio
async def test_price_new_user_discount_only_on_1_month():
    plan = _make_plan(name="3_months", price=590, new_user_price=None)
    plan.new_user_price_rub = 400  # set but plan.name != "1_month"
    user = _make_user(has_made_payment=False)
    final, promo = await calculate_final_price(_make_db_no_promo(), plan, user, None)
    assert final == 590  # discount not applied


@pytest.mark.asyncio
async def test_price_promo_discount_applied():
    plan = _make_plan(name="3_months", price=590, new_user_price=None)
    user = _make_user(has_made_payment=True)

    promo_obj = MagicMock(spec=PromoCode)
    promo_obj.is_active = True
    promo_obj.valid_until = None
    promo_obj.max_uses = None
    promo_obj.used_count = 0
    promo_obj.type = PromoCodeType.discount_percent
    promo_obj.value = 10  # 10% off
    promo_obj.id = uuid.uuid4()

    db = AsyncMock(spec=AsyncSession)
    call_count = [0]
    def _side(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=promo_obj)  # promo found
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)  # no prior usage
        return result
    db.execute = AsyncMock(side_effect=_side)

    final, promo = await calculate_final_price(db, plan, user, "CODE10")
    assert final == round(590 * 0.9)  # 531
    assert promo is promo_obj


@pytest.mark.asyncio
async def test_price_min_wins_when_both_discounts():
    """When new_user and promo both apply, the lower price wins."""
    plan = _make_plan(name="1_month", price=200, new_user_price=100)
    user = _make_user(has_made_payment=False)

    promo_obj = MagicMock(spec=PromoCode)
    promo_obj.is_active = True
    promo_obj.valid_until = None
    promo_obj.max_uses = None
    promo_obj.used_count = 0
    promo_obj.type = PromoCodeType.discount_percent
    promo_obj.value = 40  # 40% off 200 = 120
    promo_obj.id = uuid.uuid4()

    db = AsyncMock(spec=AsyncSession)
    call_count = [0]
    def _side(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=promo_obj)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result
    db.execute = AsyncMock(side_effect=_side)

    final, _ = await calculate_final_price(db, plan, user, "PROMO40")
    # candidates: [200, 100 (new_user), 120 (promo)] → min = 100
    assert final == 100


@pytest.mark.asyncio
async def test_invalid_promo_raises_400():
    plan = _make_plan()
    user = _make_user()
    db = _make_db_no_promo()  # returns None for promo lookup
    with pytest.raises(HTTPException) as exc_info:
        await calculate_final_price(db, plan, user, "INVALID")
    assert exc_info.value.status_code == 400
