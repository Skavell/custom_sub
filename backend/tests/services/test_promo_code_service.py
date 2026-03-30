# backend/tests/services/test_promo_code_service.py
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promo_code import PromoCode, PromoCodeType, PromoCodeUsage
from app.models.user import User


NOW = datetime.now(tz=timezone.utc)


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    return u


def _make_promo(
    code="BONUS30",
    type_=PromoCodeType.bonus_days,
    value=30,
    is_active=True,
    valid_until=None,
    max_uses=None,
    used_count=0,
):
    p = MagicMock(spec=PromoCode)
    p.id = uuid.uuid4()
    p.code = code
    p.type = type_
    p.value = value
    p.is_active = is_active
    p.valid_until = valid_until
    p.max_uses = max_uses
    p.used_count = used_count
    return p


def _db_returning(first_result, second_result=None):
    """DB mock: first execute() call returns first_result, second returns second_result."""
    db = AsyncMock(spec=AsyncSession)
    call_count = [0]

    def _side(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=first_result)
        else:
            result.scalar_one_or_none = MagicMock(return_value=second_result)
        return result

    db.execute = AsyncMock(side_effect=_side)
    return db


# --- validate_promo_code ---

@pytest.mark.asyncio
async def test_validate_not_found_raises_404():
    from app.services.promo_code_service import validate_promo_code
    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc_info:
        await validate_promo_code(db, "NOPE", _make_user())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_validate_inactive_raises_404():
    from app.services.promo_code_service import validate_promo_code
    promo = _make_promo(is_active=False)
    db = _db_returning(promo)
    with pytest.raises(HTTPException) as exc_info:
        await validate_promo_code(db, "BONUS30", _make_user())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_validate_expired_raises_404():
    from app.services.promo_code_service import validate_promo_code
    promo = _make_promo(valid_until=NOW - timedelta(days=1))
    db = _db_returning(promo)
    with pytest.raises(HTTPException) as exc_info:
        await validate_promo_code(db, "BONUS30", _make_user())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_validate_maxed_raises_404():
    from app.services.promo_code_service import validate_promo_code
    promo = _make_promo(max_uses=10, used_count=10)
    db = _db_returning(promo)
    with pytest.raises(HTTPException) as exc_info:
        await validate_promo_code(db, "BONUS30", _make_user())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_validate_valid_not_used():
    from app.services.promo_code_service import validate_promo_code
    promo = _make_promo()
    db = _db_returning(promo, None)  # promo found, no usage record
    result_promo, already_used = await validate_promo_code(db, "BONUS30", _make_user())
    assert result_promo is promo
    assert already_used is False


@pytest.mark.asyncio
async def test_validate_valid_already_used():
    from app.services.promo_code_service import validate_promo_code
    promo = _make_promo()
    usage = MagicMock(spec=PromoCodeUsage)
    db = _db_returning(promo, usage)  # promo found, usage record exists
    result_promo, already_used = await validate_promo_code(db, "BONUS30", _make_user())
    assert result_promo is promo
    assert already_used is True


@pytest.mark.asyncio
async def test_validate_discount_promo_returned_correctly():
    from app.services.promo_code_service import validate_promo_code
    promo = _make_promo(type_=PromoCodeType.discount_percent, value=20)
    db = _db_returning(promo, None)
    result_promo, already_used = await validate_promo_code(db, "SAVE20", _make_user())
    assert result_promo.type == PromoCodeType.discount_percent
    assert result_promo.value == 20
    assert already_used is False
