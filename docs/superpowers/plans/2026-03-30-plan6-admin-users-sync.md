# Plan 6: Admin API — Users & Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add admin-only endpoints for user management (list/search/detail), per-user Remnawave sync, subscription conflict resolution, and a background "sync all" job with Redis-backed progress polling.

**Architecture:** Single `app/routers/admin.py` (all endpoints under `/api/admin`, protected by `require_admin` dep). Background task logic extracted to `app/services/admin_sync_service.py` (creates its own DB session via `AsyncSessionLocal` — NOT the request session). Progress tracked in Redis as JSON under key `sync:{task_id}` (1h TTL).

**Tech Stack:** FastAPI, SQLAlchemy 2.x async (`selectinload` for relationships), `asyncio.timeout` (Python 3.12), Redis JSON, pytest-asyncio, AsyncMock/MagicMock/patch, `uv run pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `backend/app/schemas/admin.py` | All admin request/response models |
| **Create** | `backend/app/services/admin_sync_service.py` | `run_sync_all` background task |
| **Create** | `backend/app/routers/admin.py` | All admin endpoints |
| **Modify** | `backend/app/main.py` | Register admin router |
| **Create** | `backend/tests/services/test_admin_sync_service.py` | Unit tests for sync logic |
| **Create** | `backend/tests/routers/test_admin.py` | Router tests |

---

## Task 1: Admin Schemas

**Files:**
- Create: `backend/app/schemas/admin.py`

- [ ] **Step 1: Create schemas file**

```python
# backend/app/schemas/admin.py
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    provider: str
    provider_user_id: str
    provider_username: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class SubscriptionAdminInfo(BaseModel):
    type: str
    status: str
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None
    synced_at: datetime | None
    model_config = {"from_attributes": True}


class TransactionAdminItem(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount_rub: int | None
    days_added: int | None
    description: str | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class UserAdminListItem(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    is_admin: bool
    remnawave_uuid: uuid.UUID | None
    has_made_payment: bool
    subscription_conflict: bool
    created_at: datetime
    last_seen_at: datetime
    subscription_status: str | None
    subscription_type: str | None
    subscription_expires_at: datetime | None
    providers: list[str]


class UserAdminDetail(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    is_admin: bool
    remnawave_uuid: uuid.UUID | None
    has_made_payment: bool
    subscription_conflict: bool
    created_at: datetime
    last_seen_at: datetime
    subscription: SubscriptionAdminInfo | None
    providers: list[ProviderInfo]
    recent_transactions: list[TransactionAdminItem]


class ConflictResolveRequest(BaseModel):
    remnawave_uuid: str  # UUID string of the Remnawave user to keep


class SyncStatusResponse(BaseModel):
    status: str   # "running" | "completed" | "failed" | "timed_out"
    total: int
    done: int
    errors: int
```

- [ ] **Step 2: Verify import**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run python -c "from app.schemas.admin import UserAdminListItem, UserAdminDetail, SyncStatusResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/schemas/admin.py
git commit -m "feat: add admin schemas"
```

---

## Task 2: Admin Users Router — List & Detail

**Files:**
- Create: `backend/app/routers/admin.py` (partial — list + detail only)
- Create: `backend/tests/routers/test_admin.py` (list + detail tests only)

### Context
- `require_admin` dep in `app/deps.py` — raises 403 if not admin
- Use `selectinload(User.auth_providers)` and `selectinload(User.subscription)` for eager loading
- Query params: `q: str | None` (search display_name ilike), `skip: int = 0`, `limit: int = 50`
- Sort by: `sort_by: Literal["created_at","last_seen_at","display_name"] = "created_at"`, `order: Literal["asc","desc"] = "desc"`
- User detail: load providers + subscription + last 10 transactions (separate query)
- `User.transactions` relationship exists; query with `.order_by(Transaction.created_at.desc()).limit(10)`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect ImportError (router not created)**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -v 2>&1 | head -20`
Expected: Errors (ImportError or 404)

- [ ] **Step 3: Create partial router (list + detail only)**

```python
# backend/app/routers/admin.py
from __future__ import annotations
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_admin
from app.models.auth_provider import AuthProvider
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.admin import (
    ProviderInfo,
    SubscriptionAdminInfo,
    TransactionAdminItem,
    UserAdminDetail,
    UserAdminListItem,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _build_list_item(u: User) -> UserAdminListItem:
    sub = u.subscription
    return UserAdminListItem(
        id=u.id,
        display_name=u.display_name,
        avatar_url=u.avatar_url,
        is_admin=u.is_admin,
        remnawave_uuid=u.remnawave_uuid,
        has_made_payment=u.has_made_payment,
        subscription_conflict=u.subscription_conflict,
        created_at=u.created_at,
        last_seen_at=u.last_seen_at,
        subscription_status=sub.status.value if sub else None,
        subscription_type=sub.type.value if sub else None,
        subscription_expires_at=sub.expires_at if sub else None,
        providers=[p.provider.value for p in u.auth_providers],
    )


@router.get("/users", response_model=list[UserAdminListItem])
async def list_users(
    q: str | None = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: Literal["created_at", "last_seen_at", "display_name"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserAdminListItem]:
    sort_map = {
        "created_at": User.created_at,
        "last_seen_at": User.last_seen_at,
        "display_name": User.display_name,
    }
    sort_col = sort_map[sort_by]
    stmt = (
        select(User)
        .options(selectinload(User.auth_providers), selectinload(User.subscription))
    )
    if q:
        stmt = stmt.where(User.display_name.ilike(f"%{q}%"))
    if order == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())
    stmt = stmt.offset(skip).limit(min(limit, 200))
    result = await db.execute(stmt)
    users = result.scalars().unique().all()
    return [_build_list_item(u) for u in users]


@router.get("/users/{user_id}", response_model=UserAdminDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminDetail:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.auth_providers), selectinload(User.subscription))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(10)
    )
    transactions = tx_result.scalars().all()

    return UserAdminDetail(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        remnawave_uuid=user.remnawave_uuid,
        has_made_payment=user.has_made_payment,
        subscription_conflict=user.subscription_conflict,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        subscription=SubscriptionAdminInfo.model_validate(user.subscription) if user.subscription else None,
        providers=[ProviderInfo.model_validate(p) for p in user.auth_providers],
        recent_transactions=[TransactionAdminItem.model_validate(tx) for tx in transactions],
    )
```

- [ ] **Step 4: Register in main.py**

Read `app/main.py`, then add:
- `from app.routers import admin` after `from app.routers import articles`
- `app.include_router(admin.router)` after `app.include_router(articles.router)`

- [ ] **Step 5: Run list + detail tests — expect 5 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 5 passed

- [ ] **Step 6: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 123 passed (117 + 1 schema verify + 5 admin)

- [ ] **Step 7: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/schemas/admin.py app/routers/admin.py app/main.py tests/routers/test_admin.py
git commit -m "feat: add admin users list and detail endpoints"
```

---

## Task 3: Admin User Actions — Per-User Sync & Conflict Resolution

**Files:**
- Modify: `backend/app/routers/admin.py` (append two endpoints)
- Modify: `backend/tests/routers/test_admin.py` (append tests)

### Context
- `sync_subscription_from_remnawave(db, user, rw_user)` in `app/services/subscription_service.py` — creates/updates local subscription row, calls `db.commit()` internally
- `RemnawaveClient(url, token).get_user(uuid_str)` — may raise httpx exceptions
- Per-user sync: 409 if `remnawave_uuid is None`, 503 if Remnawave not configured, 503 on RW exception, 200 `{"ok": True}` on success
- Conflict resolution: validate UUID, update `user.remnawave_uuid + user.subscription_conflict = False`, commit, then best-effort sync (catch exception)

- [ ] **Step 1: Append tests to test_admin.py**

Append to `backend/tests/routers/test_admin.py`:

```python

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
```

- [ ] **Step 2: Run new tests — expect failures (endpoints don't exist yet)**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py::test_admin_user_sync_no_rw_uuid_returns_409 -v 2>&1 | head -15`
Expected: FAILED (404 or AttributeError)

- [ ] **Step 3: Append two endpoints to admin.py**

Append to `backend/app/routers/admin.py` (after the existing imports add these — they need `get_setting`, `get_setting_decrypted`, `RemnawaveClient`, `sync_subscription_from_remnawave`):

First, add missing imports at top of `admin.py`:
```python
from app.schemas.admin import ConflictResolveRequest  # add to existing import
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import sync_subscription_from_remnawave
```

Then append these two endpoints to the router:

```python

@router.post("/users/{user_id}/sync")
async def sync_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if user.remnawave_uuid is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У пользователя нет Remnawave UUID")

    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Remnawave не настроен")

    rw_client = RemnawaveClient(url, token)
    try:
        rw_user = await rw_client.get_user(str(user.remnawave_uuid))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ошибка связи с Remnawave")

    await sync_subscription_from_remnawave(db, user, rw_user)
    return {"ok": True}


@router.post("/users/{user_id}/resolve-conflict")
async def resolve_conflict(
    user_id: uuid.UUID,
    data: ConflictResolveRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        new_rw_uuid = uuid.UUID(data.remnawave_uuid)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный UUID")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    user.remnawave_uuid = new_rw_uuid
    user.subscription_conflict = False
    await db.commit()

    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if url and token:
        try:
            rw_user = await RemnawaveClient(url, token).get_user(str(new_rw_uuid))
            await sync_subscription_from_remnawave(db, user, rw_user)
        except Exception:
            pass  # Conflict cleared; sync failure is non-critical

    return {"ok": True}
```

- [ ] **Step 4: Run all admin tests — expect 10 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 10 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 128 passed

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/admin.py tests/routers/test_admin.py
git commit -m "feat: add admin per-user sync and conflict resolution endpoints"
```

---

## Task 4: Admin Sync-All Service

**Files:**
- Create: `backend/app/services/admin_sync_service.py`
- Create: `backend/tests/services/test_admin_sync_service.py`

### Context
- Background task must create its own DB session using `AsyncSessionLocal` from `app.database` (the request session is closed by the time the background task runs)
- Stores progress in Redis as JSON: `{"status": "running"|"completed"|"failed"|"timed_out", "total": N, "done": N, "errors": N}`
- Key: `sync:{task_id}`, TTL: 3600s
- Per-user timeout: 10s via `asyncio.timeout` (Python 3.12)
- Full batch timeout: 600s (10 min)
- On Remnawave not configured: set status "failed" immediately

- [ ] **Step 1: Write failing service tests**

```python
# backend/tests/services/test_admin_sync_service.py
import asyncio
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


def _make_redis():
    r = AsyncMock(spec=Redis)
    r.set = AsyncMock()
    return r


def _make_db(users=None):
    """Mock AsyncSessionLocal context manager."""
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = users or []
    db.execute = AsyncMock(return_value=result)
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.mark.asyncio
async def test_sync_all_no_rw_config_sets_failed_status():
    from app.services.admin_sync_service import run_sync_all

    task_id = str(uuid.uuid4())
    redis = _make_redis()
    mock_db = _make_db()

    with patch("app.services.admin_sync_service.AsyncSessionLocal", return_value=mock_db), \
         patch("app.services.admin_sync_service.get_setting", return_value=None), \
         patch("app.services.admin_sync_service.get_setting_decrypted", return_value=None):
        await run_sync_all(task_id, redis)

    # Verify final Redis set called with failed status
    last_call = redis.set.call_args_list[-1]
    stored = json.loads(last_call[0][1])
    assert stored["status"] == "failed"


@pytest.mark.asyncio
async def test_sync_all_success_sets_completed_status():
    from app.services.admin_sync_service import run_sync_all

    task_id = str(uuid.uuid4())
    redis = _make_redis()

    user1 = MagicMock()
    user1.remnawave_uuid = uuid.uuid4()
    user2 = MagicMock()
    user2.remnawave_uuid = uuid.uuid4()
    mock_db = _make_db(users=[user1, user2])

    rw_user = MagicMock()

    with patch("app.services.admin_sync_service.AsyncSessionLocal", return_value=mock_db), \
         patch("app.services.admin_sync_service.get_setting", return_value="http://rw"), \
         patch("app.services.admin_sync_service.get_setting_decrypted", return_value="token"), \
         patch("app.services.admin_sync_service.RemnawaveClient") as mock_rw_cls, \
         patch("app.services.admin_sync_service.sync_subscription_from_remnawave", new_callable=AsyncMock):
        mock_rw_cls.return_value.get_user = AsyncMock(return_value=rw_user)
        await run_sync_all(task_id, redis)

    last_call = redis.set.call_args_list[-1]
    stored = json.loads(last_call[0][1])
    assert stored["status"] == "completed"
    assert stored["done"] == 2
    assert stored["errors"] == 0


@pytest.mark.asyncio
async def test_sync_all_per_user_error_counted_and_continues():
    from app.services.admin_sync_service import run_sync_all

    task_id = str(uuid.uuid4())
    redis = _make_redis()

    user1 = MagicMock()
    user1.remnawave_uuid = uuid.uuid4()
    user2 = MagicMock()
    user2.remnawave_uuid = uuid.uuid4()
    mock_db = _make_db(users=[user1, user2])

    call_count = [0]
    async def _failing_get_user(uid):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("Remnawave error")
        return MagicMock()

    with patch("app.services.admin_sync_service.AsyncSessionLocal", return_value=mock_db), \
         patch("app.services.admin_sync_service.get_setting", return_value="http://rw"), \
         patch("app.services.admin_sync_service.get_setting_decrypted", return_value="token"), \
         patch("app.services.admin_sync_service.RemnawaveClient") as mock_rw_cls, \
         patch("app.services.admin_sync_service.sync_subscription_from_remnawave", new_callable=AsyncMock):
        mock_rw_cls.return_value.get_user = _failing_get_user
        await run_sync_all(task_id, redis)

    last_call = redis.set.call_args_list[-1]
    stored = json.loads(last_call[0][1])
    assert stored["status"] == "completed"
    assert stored["done"] == 1
    assert stored["errors"] == 1
```

- [ ] **Step 2: Run service tests — expect ImportError**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/services/test_admin_sync_service.py -v 2>&1 | head -15`
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Create service file**

```python
# backend/app/services/admin_sync_service.py
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import sync_subscription_from_remnawave

logger = logging.getLogger(__name__)

_BATCH_TIMEOUT = 600   # 10 minutes total
_PER_USER_TIMEOUT = 10  # seconds per user
_REDIS_TTL = 3600       # 1 hour


async def run_sync_all(task_id: str, redis: Redis) -> None:
    """Background task: sync all Remnawave users.
    Creates its own DB session — must NOT receive the request session.
    Stores progress in Redis as JSON under key sync:{task_id}.
    """
    async with AsyncSessionLocal() as db:
        url = await get_setting(db, "remnawave_url")
        token = await get_setting_decrypted(db, "remnawave_token")

        if not url or not token:
            await redis.set(
                f"sync:{task_id}",
                json.dumps({"status": "failed", "total": 0, "done": 0, "errors": 0}),
                ex=_REDIS_TTL,
            )
            return

        result = await db.execute(select(User).where(User.remnawave_uuid.is_not(None)))
        users = result.scalars().all()
        total = len(users)
        done = 0
        errors = 0

        await redis.set(
            f"sync:{task_id}",
            json.dumps({"status": "running", "total": total, "done": 0, "errors": 0}),
            ex=_REDIS_TTL,
        )

        rw_client = RemnawaveClient(url, token)
        start_time = datetime.now(tz=timezone.utc)

        for user in users:
            elapsed = (datetime.now(tz=timezone.utc) - start_time).total_seconds()
            if elapsed > _BATCH_TIMEOUT:
                await redis.set(
                    f"sync:{task_id}",
                    json.dumps({"status": "timed_out", "total": total, "done": done, "errors": errors}),
                    ex=_REDIS_TTL,
                )
                return

            try:
                async with asyncio.timeout(_PER_USER_TIMEOUT):
                    rw_user = await rw_client.get_user(str(user.remnawave_uuid))
                    await sync_subscription_from_remnawave(db, user, rw_user)
                done += 1
            except Exception as exc:
                logger.warning("Sync failed for user %s: %s", user.remnawave_uuid, exc)
                errors += 1

            await redis.set(
                f"sync:{task_id}",
                json.dumps({"status": "running", "total": total, "done": done, "errors": errors}),
                ex=_REDIS_TTL,
            )

        await redis.set(
            f"sync:{task_id}",
            json.dumps({"status": "completed", "total": total, "done": done, "errors": errors}),
            ex=_REDIS_TTL,
        )
```

- [ ] **Step 4: Run service tests — expect 3 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/services/test_admin_sync_service.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 3 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 131 passed

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/services/admin_sync_service.py tests/services/test_admin_sync_service.py
git commit -m "feat: add admin sync-all background service"
```

---

## Task 5: Admin Sync-All Router Endpoints

**Files:**
- Modify: `backend/app/routers/admin.py` (append two endpoints + imports)
- Modify: `backend/tests/routers/test_admin.py` (append tests)

### Context
- `POST /api/admin/sync/all` — requires admin, creates task_id (UUID4 string), stores initial Redis status, schedules `run_sync_all` via `BackgroundTasks`, returns `{"task_id": task_id}` with 201
- `GET /api/admin/sync/status/{task_id}` — requires admin, reads Redis key `sync:{task_id}`, returns `SyncStatusResponse`, 404 if not found
- In tests: patch `run_sync_all` to avoid actually running it; mock Redis `set`/`get`

- [ ] **Step 1: Append tests to test_admin.py**

Append to `backend/tests/routers/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run new tests — expect failures**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py::test_admin_sync_all_returns_task_id -v 2>&1 | head -15`
Expected: FAILED (404)

- [ ] **Step 3: Append sync endpoints to admin.py**

Add to imports at top of `admin.py`:
```python
import json
from fastapi import BackgroundTasks
from app.redis_client import get_redis
from app.services.admin_sync_service import run_sync_all
from app.schemas.admin import SyncStatusResponse  # add to existing schemas import
from redis.asyncio import Redis
```

Append to the router:

```python

@router.post("/sync/all", status_code=201)
async def sync_all_users(
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    task_id = str(uuid.uuid4())
    await redis.set(
        f"sync:{task_id}",
        json.dumps({"status": "running", "total": 0, "done": 0, "errors": 0}),
        ex=3600,
    )
    background_tasks.add_task(run_sync_all, task_id, redis)
    return {"task_id": task_id}


@router.get("/sync/status/{task_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    task_id: str,
    admin: User = Depends(require_admin),
    redis: Redis = Depends(get_redis),
) -> SyncStatusResponse:
    raw = await redis.get(f"sync:{task_id}")
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    data = json.loads(raw)
    return SyncStatusResponse(**data)
```

- [ ] **Step 4: Run all admin tests — expect 13 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 13 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 134 passed (117 + 1 + 13 + 3)

- [ ] **Step 6: Commit + tag**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/admin.py tests/routers/test_admin.py
git commit -m "feat: add admin sync-all background task and status polling"
git tag plan-6-complete
```

---

## Final Verification

- [ ] **Run full suite**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest -v 2>&1 | tail -10`
Expected: 134 passed, 0 failed

- [ ] **Verify all admin endpoints registered**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run python -c "from app.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'admin' in r])"`
Expected: list containing `/api/admin/users`, `/api/admin/users/{user_id}`, `/api/admin/users/{user_id}/sync`, `/api/admin/users/{user_id}/resolve-conflict`, `/api/admin/sync/all`, `/api/admin/sync/status/{task_id}`
