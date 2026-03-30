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


# --- apply_bonus_days ---

def _make_rw_client(expire_at=None):
    """Mock RemnawaveClient. get_user returns rw_user, update_user returns updated rw_user."""
    if expire_at is None:
        expire_at = NOW + timedelta(days=5)
    rw_user = MagicMock()
    rw_user.expire_at = expire_at
    client = AsyncMock()
    client.get_user = AsyncMock(return_value=rw_user)
    # update_user returns a new rw_user with updated expire_at
    async def _update(uuid_str, traffic_limit_bytes=None, expire_at=None):
        updated = MagicMock()
        from datetime import datetime
        updated.expire_at = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
        return updated
    client.update_user = AsyncMock(side_effect=_update)
    return client


def _db_for_apply(promo, usage=None, sub=None):
    """DB mock for apply_bonus_days: handles SELECT FOR UPDATE promo, usage check, subscription."""
    db = AsyncMock(spec=AsyncSession)
    call_count = [0]

    def _side(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=promo)   # FOR UPDATE promo
        elif call_count[0] == 2:
            result.scalar_one_or_none = MagicMock(return_value=usage)   # usage check
        else:
            result.scalar_one_or_none = MagicMock(return_value=sub)     # subscription upsert
        return result

    db.execute = AsyncMock(side_effect=_side)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_apply_bonus_days_success_no_existing_sub():
    from app.services.promo_code_service import apply_bonus_days
    promo = _make_promo(value=30)
    user = _make_user()
    user.remnawave_uuid = uuid.uuid4()
    rw_client = _make_rw_client(expire_at=NOW + timedelta(days=5))
    db = _db_for_apply(promo, usage=None, sub=None)

    days_added, new_expires_at = await apply_bonus_days(db, promo, user, rw_client)

    assert days_added == 30
    # new_expires_at should be ~35 days from now (5 existing + 30 bonus)
    assert new_expires_at > NOW + timedelta(days=34)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_apply_bonus_days_extends_existing_sub():
    from app.services.promo_code_service import apply_bonus_days
    from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus

    promo = _make_promo(value=15)
    user = _make_user()
    user.remnawave_uuid = uuid.uuid4()
    rw_client = _make_rw_client(expire_at=NOW + timedelta(days=20))

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    db = _db_for_apply(promo, usage=None, sub=sub)

    days_added, new_expires_at = await apply_bonus_days(db, promo, user, rw_client)

    assert days_added == 15
    # Sub type should have been set to paid
    assert sub.type == SubscriptionType.paid
    assert sub.traffic_limit_gb is None


@pytest.mark.asyncio
async def test_apply_bonus_days_already_used_raises_400():
    from app.services.promo_code_service import apply_bonus_days
    promo = _make_promo(value=30)
    user = _make_user()
    user.remnawave_uuid = uuid.uuid4()
    usage = MagicMock(spec=PromoCodeUsage)
    rw_client = _make_rw_client()
    db = _db_for_apply(promo, usage=usage)

    with pytest.raises(HTTPException) as exc_info:
        await apply_bonus_days(db, promo, user, rw_client)
    assert exc_info.value.status_code == 400
    assert "использован" in exc_info.value.detail


@pytest.mark.asyncio
async def test_apply_bonus_days_maxed_at_lock_time_raises_400():
    from app.services.promo_code_service import apply_bonus_days
    promo = _make_promo(value=30, max_uses=5, used_count=5)
    user = _make_user()
    user.remnawave_uuid = uuid.uuid4()
    rw_client = _make_rw_client()
    db = _db_for_apply(promo, usage=None)

    with pytest.raises(HTTPException) as exc_info:
        await apply_bonus_days(db, promo, user, rw_client)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_apply_bonus_days_increments_used_count():
    from app.services.promo_code_service import apply_bonus_days
    promo = _make_promo(value=30)
    promo.used_count = 3
    user = _make_user()
    user.remnawave_uuid = uuid.uuid4()
    rw_client = _make_rw_client()
    db = _db_for_apply(promo, usage=None, sub=None)

    await apply_bonus_days(db, promo, user, rw_client)

    assert promo.used_count == 4
