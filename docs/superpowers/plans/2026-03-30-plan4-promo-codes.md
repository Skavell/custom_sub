# Plan 4: Promo Codes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two promo code endpoints — `GET /api/promo-codes/validate/{code}` (shows discount/bonus info) and `POST /api/promo-codes/apply` (applies bonus_days without payment, converts trial → paid).

**Architecture:** Validation logic extracted to `promo_code_service.py`; router handles guards and Remnawave errors. `apply_bonus_days` uses `SELECT FOR UPDATE` for concurrency safety and a single `db.commit()` for atomicity — same pattern as `complete_payment`. No new Alembic migration needed: all tables (`promo_codes`, `promo_code_usages`) and enum values (`promo_bonus`) already exist in the initial schema.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, PostgreSQL, pytest-asyncio, httpx AsyncClient for router tests, `unittest.mock` (AsyncMock/MagicMock/patch), `uv run pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `backend/app/schemas/promo_code.py` | Request/response Pydantic models |
| **Create** | `backend/app/services/promo_code_service.py` | `validate_promo_code`, `apply_bonus_days` |
| **Create** | `backend/app/routers/promo_codes.py` | `GET /validate/{code}`, `POST /apply` |
| **Modify** | `backend/app/main.py` | Register `promo_codes.router` |
| **Create** | `backend/tests/services/test_promo_code_service.py` | Service-level unit tests |
| **Create** | `backend/tests/routers/test_promo_codes.py` | Router-level integration tests |

---

## Task 1: Schemas

**Files:**
- Create: `backend/app/schemas/promo_code.py`

- [ ] **Step 1: Create the schema file**

```python
# backend/app/schemas/promo_code.py
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class ValidatePromoResponse(BaseModel):
    code: str
    type: str           # "discount_percent" | "bonus_days"
    value: int          # percent value or days count
    already_used: bool


class ApplyPromoRequest(BaseModel):
    code: str


class ApplyPromoResponse(BaseModel):
    days_added: int
    new_expires_at: datetime
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && uv run python -c "from app.schemas.promo_code import ValidatePromoResponse, ApplyPromoRequest, ApplyPromoResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/promo_code.py
git commit -m "feat: add promo code schemas"
```

---

## Task 2: Service — `validate_promo_code`

**Files:**
- Create: `backend/app/services/promo_code_service.py`
- Create: `backend/tests/services/test_promo_code_service.py` (validate tests only)

### Step-by-step

- [ ] **Step 1: Write failing tests for validate_promo_code**

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError or AttributeError (module doesn't exist yet)**

Run: `cd backend && uv run pytest tests/services/test_promo_code_service.py -v 2>&1 | head -30`
Expected: ERRORS (ImportError: cannot import name 'validate_promo_code')

- [ ] **Step 3: Implement `validate_promo_code` in promo_code_service.py**

```python
# backend/app/services/promo_code_service.py
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promo_code import PromoCode, PromoCodeUsage, PromoCodeType
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.remnawave_client import RemnawaveClient


async def validate_promo_code(
    db: AsyncSession,
    code: str,
    user: User,
) -> tuple[PromoCode, bool]:
    """Returns (promo, already_used_by_user).
    Raises HTTP 404 if code is invalid/inactive/expired/maxed.
    Works for both promo types (discount_percent and bonus_days).
    """
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(PromoCode).where(PromoCode.code == code.upper())
    )
    promo = result.scalar_one_or_none()

    if not promo or not promo.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
    if promo.valid_until is not None and promo.valid_until < now:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")

    usage_result = await db.execute(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo.id,
            PromoCodeUsage.user_id == user.id,
        )
    )
    already_used = usage_result.scalar_one_or_none() is not None

    return promo, already_used
```

- [ ] **Step 4: Run validate tests — expect all pass**

Run: `cd backend && uv run pytest tests/services/test_promo_code_service.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/promo_code_service.py backend/tests/services/test_promo_code_service.py
git commit -m "feat: add validate_promo_code service + tests"
```

---

## Task 3: Service — `apply_bonus_days`

**Files:**
- Modify: `backend/app/services/promo_code_service.py` (append function)
- Modify: `backend/tests/services/test_promo_code_service.py` (append tests)

- [ ] **Step 1: Append apply_bonus_days tests to test file**

Append to `backend/tests/services/test_promo_code_service.py`:

```python
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
    async def _update(uuid_str, traffic_limit_bytes, expire_at_str):
        updated = MagicMock()
        from datetime import datetime
        updated.expire_at = datetime.fromisoformat(expire_at_str.replace("Z", "+00:00"))
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
```

- [ ] **Step 2: Run new apply tests — expect ImportError or AttributeError**

Run: `cd backend && uv run pytest tests/services/test_promo_code_service.py::test_apply_bonus_days_success_no_existing_sub -v 2>&1 | head -20`
Expected: ImportError or AttributeError (apply_bonus_days not yet defined)

- [ ] **Step 3: Append `apply_bonus_days` to promo_code_service.py**

Append to `backend/app/services/promo_code_service.py`:

```python

async def apply_bonus_days(
    db: AsyncSession,
    promo: PromoCode,
    user: User,
    rw_client: RemnawaveClient,
) -> tuple[int, datetime]:
    """Applies a bonus_days promo code atomically.
    Returns (days_added, new_expires_at).
    Uses SELECT FOR UPDATE to serialize concurrent applications.
    Single db.commit() at the end for atomicity.
    Raises HTTP 400 if promo is invalid at lock-time or already used.
    """
    now = datetime.now(tz=timezone.utc)

    # Re-fetch with lock to serialize concurrent applications
    promo_result = await db.execute(
        select(PromoCode)
        .where(PromoCode.id == promo.id)
        .with_for_update()
    )
    promo_locked = promo_result.scalar_one_or_none()
    if promo_locked is None or not promo_locked.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
    if promo_locked.valid_until is not None and promo_locked.valid_until < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
    if promo_locked.max_uses is not None and promo_locked.used_count >= promo_locked.max_uses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")

    # One-per-user check
    usage_result = await db.execute(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo_locked.id,
            PromoCodeUsage.user_id == user.id,
        )
    )
    if usage_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод уже использован")

    # Extend Remnawave subscription
    rw_user = await rw_client.get_user(str(user.remnawave_uuid))
    base_date = max(rw_user.expire_at, now)
    new_expire_at = base_date + timedelta(days=promo_locked.value)
    rw_user = await rw_client.update_user(
        str(user.remnawave_uuid),
        traffic_limit_bytes=0,  # unlimited — always paid after bonus
        expire_at=new_expire_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Upsert local subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, started_at=now)
        db.add(sub)
    sub.type = SubscriptionType.paid
    sub.status = SubscriptionStatus.active
    sub.expires_at = rw_user.expire_at
    sub.traffic_limit_gb = None  # 0 bytes → unlimited
    sub.synced_at = now

    # Create promo_bonus transaction
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.promo_bonus,
        promo_code_id=promo_locked.id,
        days_added=promo_locked.value,
        status=TransactionStatus.completed,
        description=f"Промокод {promo_locked.code}",
        completed_at=now,
    )
    db.add(tx)

    # Record usage + increment counter
    db.add(PromoCodeUsage(promo_code_id=promo_locked.id, user_id=user.id))
    promo_locked.used_count += 1

    await db.commit()
    await db.refresh(sub)

    return promo_locked.value, sub.expires_at
```

- [ ] **Step 4: Run all service tests — expect all pass**

Run: `cd backend && uv run pytest tests/services/test_promo_code_service.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 12 PASSED

- [ ] **Step 5: Run full test suite to ensure no regressions**

Run: `cd backend && uv run pytest --tb=short -q 2>&1 | tail -5`
Expected: 96 passed (84 existing + 12 new)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/promo_code_service.py backend/tests/services/test_promo_code_service.py
git commit -m "feat: add apply_bonus_days service + tests"
```

---

## Task 4: Router + main.py Registration

**Files:**
- Create: `backend/app/routers/promo_codes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/routers/test_promo_codes.py`

- [ ] **Step 1: Write failing router tests**

```python
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
    u.remnawave_uuid = remnawave_uuid or uuid.uuid4()
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
    user = _make_user(remnawave_uuid=None)
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
    db = AsyncMock(spec=AsyncSession)
    # get_setting / get_setting_decrypted return None (not configured)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)

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
```

- [ ] **Step 2: Run router tests — expect ImportError or 404 (router not registered yet)**

Run: `cd backend && uv run pytest tests/routers/test_promo_codes.py -v 2>&1 | head -20`
Expected: Errors or all 404s (router doesn't exist yet)

- [ ] **Step 3: Create the router**

```python
# backend/app/routers/promo_codes.py
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.promo_code import PromoCodeType
from app.models.user import User
from app.schemas.promo_code import ApplyPromoRequest, ApplyPromoResponse, ValidatePromoResponse
from app.services.promo_code_service import apply_bonus_days, validate_promo_code
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.telegram_alert import send_admin_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/promo-codes", tags=["promo-codes"])


@router.get("/validate/{code}", response_model=ValidatePromoResponse)
async def validate_promo(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidatePromoResponse:
    promo, already_used = await validate_promo_code(db, code, current_user)
    return ValidatePromoResponse(
        code=promo.code,
        type=promo.type.value,
        value=promo.value,
        already_used=already_used,
    )


@router.post("/apply", response_model=ApplyPromoResponse)
async def apply_promo(
    data: ApplyPromoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplyPromoResponse:
    # Guard: trial must be activated
    if current_user.remnawave_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала активируйте пробный период",
        )

    # Validate promo (raises 404 if invalid)
    promo, already_used = await validate_promo_code(db, data.code, current_user)

    if promo.type != PromoCodeType.bonus_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот промокод предназначен для скидки при оплате",
        )

    if already_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод уже использован",
        )

    # Load Remnawave client
    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        await send_admin_alert(
            await get_setting(db, "telegram_bot_token"),
            await get_setting(db, "telegram_admin_chat_id"),
            f"Promo apply error: Remnawave not configured\nUser: {current_user.id}\nCode: {promo.code}",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )
    rw_client = RemnawaveClient(url, token)

    try:
        days_added, new_expires_at = await apply_bonus_days(db, promo, current_user, rw_client)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("apply_bonus_days failed for user %s code %s: %s", current_user.id, promo.code, exc)
        try:
            await send_admin_alert(
                await get_setting(db, "telegram_bot_token"),
                await get_setting(db, "telegram_admin_chat_id"),
                f"Promo apply error: Remnawave unavailable\nUser: {current_user.id}\nCode: {promo.code}\nError: {exc}",
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )

    return ApplyPromoResponse(days_added=days_added, new_expires_at=new_expires_at)
```

- [ ] **Step 4: Register router in main.py**

In `backend/app/main.py`, add after `from app.routers import payments`:
```python
from app.routers import promo_codes
```

And after `app.include_router(payments.router)`:
```python
app.include_router(promo_codes.router)
```

- [ ] **Step 5: Run router tests — expect all pass**

Run: `cd backend && uv run pytest tests/routers/test_promo_codes.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 8 PASSED

- [ ] **Step 6: Run full test suite — no regressions**

Run: `cd backend && uv run pytest --tb=short -q 2>&1 | tail -5`
Expected: 104 passed (84 + 12 + 8)

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/promo_codes.py backend/app/main.py backend/tests/routers/test_promo_codes.py
git commit -m "feat: add promo codes router (validate + apply) and register in main"
```

---

## Final Verification

- [ ] **Run full suite one last time**

Run: `cd backend && uv run pytest -v 2>&1 | tail -10`
Expected: All tests pass, 0 failures

- [ ] **Tag completion**

```bash
git tag plan-4-complete
```
