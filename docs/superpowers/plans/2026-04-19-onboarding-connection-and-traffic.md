# Onboarding First-Connection & Trial Traffic Display — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark onboarding step 3 done only when user actually connects to VPN (via Remnawave webhook + API fallback), and show real remaining traffic in TrialCard.

**Architecture:** Remnawave sends `user.first_connected` webhook → backend validates HMAC, writes `first_connected_at` to DB. As fallback, `GET /api/subscriptions/me` fetches Remnawave user data (Redis-cached 5 min), writes `first_connected_at` if missed, and returns `traffic_used_bytes` for trial users. Frontend consumes `has_connected` and `traffic_used_bytes` from subscription response.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, Redis, React/TypeScript, TanStack Query

**Spec:** `docs/superpowers/specs/2026-04-19-onboarding-connection-and-traffic-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/app/models/user.py` | Modify | Add `first_connected_at` column |
| `backend/alembic/versions/c1d2e3f4a5b6_add_first_connected_at_users.py` | Create | DB migration for new column |
| `backend/alembic/versions/d2e3f4a5b6c7_seed_remnawave_webhook_secret.py` | Create | Seed `remnawave_webhook_secret` setting |
| `backend/app/services/remnawave_client.py` | Modify | Add `used_traffic_bytes`, `first_connected_at` to `RemnawaveUser` |
| `backend/app/schemas/subscription.py` | Modify | Add `has_connected`, `traffic_used_bytes` to response |
| `backend/app/routers/subscriptions.py` | Modify | Update `_to_response`, enrich `GET /me` with Remnawave data |
| `backend/app/routers/remnawave_webhook.py` | Create | Webhook endpoint with HMAC validation |
| `backend/app/main.py` | Modify | Register webhook router |
| `backend/tests/routers/test_remnawave_webhook.py` | Create | Tests for webhook endpoint |
| `backend/tests/routers/test_subscriptions.py` | Modify | Update helper + add tests for new fields |
| `frontend/src/types/api.ts` | Modify | Add `has_connected`, `traffic_used_bytes` |
| `frontend/src/components/OnboardingCard.tsx` | Modify | Replace `installVisited` with `hasConnected`, rename step |
| `frontend/src/pages/HomePage.tsx` | Modify | Wire `hasConnected`, add `TrafficDisplay` to TrialCard |
| `frontend/src/pages/admin/AdminSettingsPage.tsx` | Modify | Expose `remnawave_webhook_secret` in admin |

---

## Task 1: Add `first_connected_at` to User model + migration

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/c1d2e3f4a5b6_add_first_connected_at_users.py`

- [ ] **Step 1: Add column to User model**

In `backend/app/models/user.py`, after `last_seen_at`:

```python
first_connected_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

The `datetime` import is already present. No other change needed.

- [ ] **Step 2: Create Alembic migration**

Create `backend/alembic/versions/c1d2e3f4a5b6_add_first_connected_at_users.py`:

```python
"""add first_connected_at to users

Revision ID: c1d2e3f4a5b6
Revises: 744b110fd9e1
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = '744b110fd9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('first_connected_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'first_connected_at')
```

- [ ] **Step 3: Run migration to verify it applies**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade 744b110fd9e1 -> c1d2e3f4a5b6, add first_connected_at to users`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/c1d2e3f4a5b6_add_first_connected_at_users.py
git commit -m "feat: add first_connected_at column to users"
```

---

## Task 2: Seed `remnawave_webhook_secret` setting

**Files:**
- Create: `backend/alembic/versions/d2e3f4a5b6c7_seed_remnawave_webhook_secret.py`

- [ ] **Step 1: Create seed migration**

```python
"""seed remnawave_webhook_secret setting

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-19 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO settings (key, value, is_sensitive) "
            "VALUES (:key, CAST(:value AS jsonb), :is_sensitive) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {"key": "remnawave_webhook_secret", "value": json.dumps({"value": ""}), "is_sensitive": False},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = :key"),
        {"key": "remnawave_webhook_secret"},
    )
```

- [ ] **Step 2: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade c1d2e3f4a5b6 -> d2e3f4a5b6c7, seed remnawave_webhook_secret setting`

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/d2e3f4a5b6c7_seed_remnawave_webhook_secret.py
git commit -m "feat: seed remnawave_webhook_secret setting"
```

---

## Task 3: Extend `RemnawaveClient` with traffic and connection fields

**Files:**
- Modify: `backend/app/services/remnawave_client.py`

- [ ] **Step 1: Extend `RemnawaveUser` dataclass**

Add two fields after `telegram_id`:

```python
@dataclass
class RemnawaveUser:
    id: str
    username: str
    expire_at: datetime
    traffic_limit_bytes: int
    status: str
    subscription_url: str
    telegram_id: int | None
    used_traffic_bytes: int           # from userTraffic.usedTrafficBytes
    first_connected_at: datetime | None  # from userTraffic.firstConnectedAt
```

- [ ] **Step 2: Update `_parse_user` to parse `userTraffic`**

Replace the existing `_parse_user` function:

```python
def _parse_user(data: dict[str, Any]) -> RemnawaveUser:
    if "response" in data:
        data = data["response"]
    user_traffic = data.get("userTraffic") or {}
    fca_str = user_traffic.get("firstConnectedAt")
    first_connected_at = (
        datetime.fromisoformat(fca_str.replace("Z", "+00:00")) if fca_str else None
    )
    return RemnawaveUser(
        id=data["uuid"],
        username=data["username"],
        expire_at=datetime.fromisoformat(data["expireAt"].replace("Z", "+00:00")),
        traffic_limit_bytes=data.get("trafficLimitBytes") or 0,
        status=data.get("status", "ACTIVE"),
        subscription_url=data.get("subscriptionUrl", ""),
        telegram_id=data.get("telegramId"),
        used_traffic_bytes=user_traffic.get("usedTrafficBytes") or 0,
        first_connected_at=first_connected_at,
    )
```

- [ ] **Step 3: Verify no existing tests break**

```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | head -30
```

Expected: all existing tests pass (new fields have defaults, `_parse_user` is backwards-compatible when `userTraffic` is absent).

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/remnawave_client.py
git commit -m "feat: add used_traffic_bytes and first_connected_at to RemnawaveUser"
```

---

## Task 4: Update subscription schema and `_to_response`

**Files:**
- Modify: `backend/app/schemas/subscription.py`
- Modify: `backend/app/routers/subscriptions.py`

- [ ] **Step 1: Add fields to `SubscriptionResponse`**

Replace `backend/app/schemas/subscription.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    type: str
    status: str
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None
    days_remaining: int
    has_connected: bool
    traffic_used_bytes: int | None


class TrialActivateResponse(BaseModel):
    subscription: SubscriptionResponse
    message: str
```

- [ ] **Step 2: Update `_to_response` in `subscriptions.py`**

Replace the existing `_to_response` function:

```python
def _to_response(
    sub,
    has_connected: bool = False,
    traffic_used_bytes: int | None = None,
) -> SubscriptionResponse:
    now = datetime.now(tz=timezone.utc)
    expires = sub.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    days_remaining = max(0, (expires - now).days)
    return SubscriptionResponse(
        type=sub.type.value,
        status=sub.status.value,
        started_at=sub.started_at,
        expires_at=expires,
        traffic_limit_gb=sub.traffic_limit_gb,
        days_remaining=days_remaining,
        has_connected=has_connected,
        traffic_used_bytes=traffic_used_bytes,
    )
```

Note: the `activate_trial` endpoint calls `_to_response(sub)` — defaults `has_connected=False, traffic_used_bytes=None` are correct at activation time.

- [ ] **Step 3: Update `_make_user` helper in existing subscription test**

In `backend/tests/routers/test_subscriptions.py`, add `first_connected_at = None` to `_make_user`:

```python
def _make_user(remnawave_uuid=None) -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.remnawave_uuid = uuid.UUID(str(remnawave_uuid)) if remnawave_uuid else None
    user.has_made_payment = False
    user.first_connected_at = None   # NEW
    return user
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/routers/test_subscriptions.py -v
```

Expected: all pass. The existing `test_get_me_with_subscription` test still passes because it uses `user.remnawave_uuid = None`, so the new Remnawave fetch block is skipped — response now includes `has_connected: false, traffic_used_bytes: null` which the existing assertions don't contradict.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/subscription.py backend/app/routers/subscriptions.py backend/tests/routers/test_subscriptions.py
git commit -m "feat: add has_connected and traffic_used_bytes to SubscriptionResponse"
```

---

## Task 5: Create Remnawave webhook endpoint

**Files:**
- Create: `backend/app/routers/remnawave_webhook.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/routers/test_remnawave_webhook.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/routers/test_remnawave_webhook.py`:

```python
import hashlib
import hmac
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.user import User


NOW = datetime.now(tz=timezone.utc)
SECRET = "test-webhook-secret"


def _make_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _make_body(event: str = "user.first_connected", remnawave_uuid: str | None = None) -> bytes:
    rw_uuid = remnawave_uuid or str(uuid.uuid4())
    return json.dumps({
        "event": event,
        "data": {
            "uuid": rw_uuid,
            "userTraffic": {
                "usedTrafficBytes": 1024,
                "lifetimeUsedTrafficBytes": 1024,
                "onlineAt": None,
                "firstConnectedAt": "2026-04-19T10:00:00Z",
            },
        },
    }, separators=(",", ":")).encode()


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


@pytest.mark.asyncio
async def test_webhook_missing_secret_returns_401():
    """Returns 401 when remnawave_webhook_secret is not configured."""
    body = _make_body()
    sig = _make_sig(SECRET, body)
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value="")):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401():
    """Returns 401 when signature does not match."""
    body = _make_body()
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": "wrongsignature"},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_unknown_event_returns_200():
    """Returns 200 for unknown events without touching DB."""
    body = json.dumps({"event": "user.expired", "data": {"uuid": str(uuid.uuid4())}},
                      separators=(",", ":")).encode()
    sig = _make_sig(SECRET, body)
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_first_connected_user_not_found_returns_200():
    """Returns 200 and does not crash when no user matches remnawave_uuid."""
    body = _make_body()
    sig = _make_sig(SECRET, body)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_first_connected_writes_timestamp():
    """Writes first_connected_at from userTraffic.firstConnectedAt when user found."""
    rw_uuid = uuid.uuid4()
    body = _make_body(remnawave_uuid=str(rw_uuid))
    sig = _make_sig(SECRET, body)

    user = MagicMock(spec=User)
    user.first_connected_at = None

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.first_connected_at is not None
    assert user.first_connected_at == datetime(2026, 4, 19, 10, 0, 0, tzinfo=timezone.utc)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_first_connected_skips_if_already_set():
    """Does not overwrite first_connected_at if already set."""
    rw_uuid = uuid.uuid4()
    body = _make_body(remnawave_uuid=str(rw_uuid))
    sig = _make_sig(SECRET, body)

    existing_ts = datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc)
    user = MagicMock(spec=User)
    user.first_connected_at = existing_ts

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.first_connected_at == existing_ts
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_null_first_connected_at_skips_write():
    """Does not write first_connected_at when userTraffic.firstConnectedAt is null."""
    rw_uuid = uuid.uuid4()
    body = json.dumps({
        "event": "user.first_connected",
        "data": {
            "uuid": str(rw_uuid),
            "userTraffic": {
                "usedTrafficBytes": 0,
                "lifetimeUsedTrafficBytes": 0,
                "onlineAt": None,
                "firstConnectedAt": None,
            },
        },
    }, separators=(",", ":")).encode()
    sig = _make_sig(SECRET, body)

    user = MagicMock(spec=User)
    user.first_connected_at = None

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.first_connected_at is None
    db.commit.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail (router doesn't exist yet)**

```bash
cd backend && python -m pytest tests/routers/test_remnawave_webhook.py -v 2>&1 | head -20
```

Expected: `ImportError` or 404 errors — confirms tests are driving real implementation.

- [ ] **Step 3: Create the webhook router**

Create `backend/app/routers/remnawave_webhook.py`:

```python
import hashlib
import hmac
import json
import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.setting_service import get_setting_decrypted

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


async def _validate_signature(raw_body: bytes, header_sig: str, secret: str) -> bool:
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, header_sig)


@router.post("/remnawave")
async def remnawave_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    secret = await get_setting_decrypted(db, "remnawave_webhook_secret")
    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook not configured")

    header_sig = request.headers.get("x-remnawave-signature", "")
    if not await _validate_signature(raw_body, header_sig, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"ok": True}

    event = payload.get("event", "")
    if event != "user.first_connected":
        return {"ok": True}

    data = payload.get("data", {})
    rw_uuid_str = data.get("uuid")
    if not rw_uuid_str:
        return {"ok": True}

    try:
        rw_uuid = _uuid.UUID(rw_uuid_str)
    except ValueError:
        return {"ok": True}

    result = await db.execute(select(User).where(User.remnawave_uuid == rw_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        return {"ok": True}

    if user.first_connected_at is not None:
        return {"ok": True}

    user_traffic = data.get("userTraffic") or {}
    fca_str = user_traffic.get("firstConnectedAt")
    if not fca_str:
        return {"ok": True}

    user.first_connected_at = datetime.fromisoformat(fca_str.replace("Z", "+00:00"))
    await db.commit()
    logger.info("first_connected_at set for user %s via webhook", user.id)

    return {"ok": True}
```

- [ ] **Step 4: Register the router in `main.py`**

In `backend/app/main.py`, add after the existing router imports:

```python
from app.routers import remnawave_webhook
```

And after `app.include_router(admin.router)`:

```python
app.include_router(remnawave_webhook.router)
```

- [ ] **Step 5: Run all webhook tests**

```bash
cd backend && python -m pytest tests/routers/test_remnawave_webhook.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 6: Run full test suite**

```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/remnawave_webhook.py backend/app/main.py backend/tests/routers/test_remnawave_webhook.py
git commit -m "feat: add Remnawave webhook endpoint with HMAC validation"
```

---

## Task 6: Enrich `GET /api/subscriptions/me` with Remnawave data

**Files:**
- Modify: `backend/app/routers/subscriptions.py`
- Modify: `backend/tests/routers/test_subscriptions.py`

- [ ] **Step 1: Write failing tests for enriched response**

Add these tests to `backend/tests/routers/test_subscriptions.py`:

```python
@pytest.mark.asyncio
async def test_get_me_returns_has_connected_false_when_not_connected():
    """Returns has_connected=False when first_connected_at is None."""
    from datetime import timedelta
    user = _make_user()
    user.first_connected_at = None
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = None  # cache miss

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_connected"] is False
    assert data["traffic_used_bytes"] is None


@pytest.mark.asyncio
async def test_get_me_returns_has_connected_true_from_db():
    """Returns has_connected=True when first_connected_at is set in DB."""
    from datetime import timedelta
    user = _make_user()
    user.first_connected_at = NOW

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["has_connected"] is True


@pytest.mark.asyncio
async def test_get_me_fetches_remnawave_traffic_from_cache():
    """Returns traffic_used_bytes from Redis cache for trial user."""
    import json as _json
    from datetime import timedelta
    rw_uuid = uuid.uuid4()
    user = _make_user(remnawave_uuid=rw_uuid)
    user.first_connected_at = NOW

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    cached = _json.dumps({
        "used_traffic_bytes": 5 * 1024 ** 3,
        "first_connected_at": NOW.isoformat(),
    })

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = cached  # str, matching decode_responses=True Redis behaviour

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["traffic_used_bytes"] == 5 * 1024 ** 3


@pytest.mark.asyncio
async def test_get_me_writes_first_connected_from_remnawave_fallback():
    """Writes first_connected_at from Remnawave API when DB is null (fallback)."""
    import json as _json
    from datetime import timedelta
    from app.services.remnawave_client import RemnawaveUser

    rw_uuid = uuid.uuid4()
    user = _make_user(remnawave_uuid=rw_uuid)
    user.first_connected_at = None

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    rw_user = RemnawaveUser(
        id=str(rw_uuid),
        username="ws_test",
        expire_at=NOW,
        traffic_limit_bytes=30 * 1024 ** 3,
        status="ACTIVE",
        subscription_url="https://example.com/sub",
        telegram_id=None,
        used_traffic_bytes=2 * 1024 ** 3,
        first_connected_at=NOW,
    )

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = None  # cache miss

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        with patch("app.routers.subscriptions.get_setting", new=AsyncMock(return_value="http://rw")):
            with patch("app.routers.subscriptions.get_setting_decrypted", new=AsyncMock(return_value="tok")):
                with patch("app.routers.subscriptions.RemnawaveClient") as MockRW:
                    MockRW.return_value.get_user = AsyncMock(return_value=rw_user)
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_connected"] is True
    assert data["traffic_used_bytes"] == 2 * 1024 ** 3
    assert user.first_connected_at == NOW
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_get_me_remnawave_unreachable_still_returns_200():
    """Returns 200 with has_connected from DB when Remnawave is unreachable."""
    from datetime import timedelta
    rw_uuid = uuid.uuid4()
    user = _make_user(remnawave_uuid=rw_uuid)
    user.first_connected_at = None

    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW + timedelta(days=2)
    sub.traffic_limit_gb = 30

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=sub))
    redis = AsyncMock()
    redis.get.return_value = None  # cache miss

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        with patch("app.routers.subscriptions.get_setting", new=AsyncMock(return_value="http://rw")):
            with patch("app.routers.subscriptions.get_setting_decrypted", new=AsyncMock(return_value="tok")):
                with patch("app.routers.subscriptions.RemnawaveClient") as MockRW:
                    MockRW.return_value.get_user = AsyncMock(side_effect=Exception("timeout"))
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.get("/api/subscriptions/me")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_connected"] is False
    assert data["traffic_used_bytes"] is None
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd backend && python -m pytest tests/routers/test_subscriptions.py::test_get_me_returns_has_connected_false_when_not_connected tests/routers/test_subscriptions.py::test_get_me_fetches_remnawave_traffic_from_cache -v 2>&1 | tail -15
```

Expected: FAIL (new fields not yet in response).

- [ ] **Step 3: Implement enriched `get_my_subscription`**

Replace the `get_my_subscription` endpoint and add `json` import in `backend/app/routers/subscriptions.py`:

Add at top of file (after existing imports):
```python
import json
```

Note: `from app.services.remnawave_client import RemnawaveClient` is already imported at line 14 of `subscriptions.py` — do NOT add it again.

Replace `get_my_subscription`:

```python
@router.get("/me", response_model=SubscriptionResponse | None)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SubscriptionResponse | None:
    sub = await get_user_subscription(db, current_user.id)
    if sub is None:
        return None

    has_connected = current_user.first_connected_at is not None
    traffic_used_bytes: int | None = None

    if current_user.remnawave_uuid is not None:
        cache_key = f"rw:user_data:{current_user.id}"
        cached_raw = await redis.get(cache_key)

        if cached_raw is not None:
            rw_data = json.loads(cached_raw)
        else:
            remnawave_url = await get_setting(db, "remnawave_url")
            remnawave_token = await get_setting_decrypted(db, "remnawave_token")
            rw_data = None
            if remnawave_url and remnawave_token:
                try:
                    rw_user = await RemnawaveClient(remnawave_url, remnawave_token).get_user(
                        str(current_user.remnawave_uuid)
                    )
                    rw_data = {
                        "used_traffic_bytes": rw_user.used_traffic_bytes,
                        "first_connected_at": rw_user.first_connected_at.isoformat()
                        if rw_user.first_connected_at else None,
                    }
                    await redis.setex(cache_key, 300, json.dumps(rw_data))
                except Exception:
                    logger.warning("Failed to fetch Remnawave user data for %s", current_user.id)

        if rw_data:
            if current_user.first_connected_at is None and rw_data.get("first_connected_at"):
                current_user.first_connected_at = datetime.fromisoformat(
                    rw_data["first_connected_at"]
                )
                await db.commit()
                has_connected = True

            if sub.type.value == "trial":
                traffic_used_bytes = rw_data.get("used_traffic_bytes")

    return _to_response(sub, has_connected=has_connected, traffic_used_bytes=traffic_used_bytes)
```

- [ ] **Step 4: Run all subscription tests**

```bash
cd backend && python -m pytest tests/routers/test_subscriptions.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/subscriptions.py backend/tests/routers/test_subscriptions.py
git commit -m "feat: enrich GET /api/subscriptions/me with Remnawave traffic and connection data"
```

---

## Task 7: Admin panel — expose `remnawave_webhook_secret`

**Files:**
- Modify: `frontend/src/pages/admin/AdminSettingsPage.tsx`

- [ ] **Step 1: Add to `REMNAWAVE_KEYS`**

In `AdminSettingsPage.tsx`, find:

```typescript
const REMNAWAVE_KEYS = new Set([
  'remnawave_url', 'remnawave_token',
  'remnawave_trial_internal_squad_uuids', 'remnawave_trial_external_squad_uuids',
  'remnawave_paid_internal_squad_uuids', 'remnawave_paid_external_squad_uuids',
])
```

Replace with:

```typescript
const REMNAWAVE_KEYS = new Set([
  'remnawave_url', 'remnawave_token', 'remnawave_webhook_secret',
  'remnawave_trial_internal_squad_uuids', 'remnawave_trial_external_squad_uuids',
  'remnawave_paid_internal_squad_uuids', 'remnawave_paid_external_squad_uuids',
])
```

- [ ] **Step 2: Add label**

In `SETTING_LABELS`, after `remnawave_token`:

```typescript
remnawave_webhook_secret: 'Секрет вебхука (WEBHOOK_SECRET_HEADER)',
```

- [ ] **Step 3: Add to `rw_api` filter**

Find:

```typescript
const rw_api = remnawave.filter(s => s.key === 'remnawave_url' || s.key === 'remnawave_token')
```

Replace with:

```typescript
const rw_api = remnawave.filter(
  s => s.key === 'remnawave_url' ||
       s.key === 'remnawave_token' ||
       s.key === 'remnawave_webhook_secret'
)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/AdminSettingsPage.tsx
git commit -m "feat: expose remnawave_webhook_secret in admin settings"
```

---

## Task 8: Frontend — types and OnboardingCard

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/components/OnboardingCard.tsx`

- [ ] **Step 1: Update `SubscriptionResponse` type**

In `frontend/src/types/api.ts`, find the `SubscriptionResponse` interface and add the two new fields:

```typescript
export interface SubscriptionResponse {
  type: 'trial' | 'paid'
  status: 'active' | 'expired' | 'disabled'
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  days_remaining: number
  has_connected: boolean
  traffic_used_bytes: number | null
}
```

(If the interface already has all other fields, just add `has_connected` and `traffic_used_bytes`.)

- [ ] **Step 2: Update `OnboardingCard`**

Replace the entire file `frontend/src/components/OnboardingCard.tsx`:

```tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'

interface Props {
  hasMadePayment: boolean
  hasSubscription: boolean
  hasConnected: boolean
  onActivateTrial: () => void
}

const LS_DISMISSED = 'onboarding_dismissed'
const LS_COMPLETED = 'onboarding_completed'

export function OnboardingCard({ hasMadePayment, hasSubscription, hasConnected, onActivateTrial }: Props) {
  const navigate = useNavigate()
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(LS_DISMISSED) === 'true')
  const [completed, setCompleted] = useState(() => localStorage.getItem(LS_COMPLETED) === 'true')
  const [celebrating, setCelebrating] = useState(false)

  const steps = [
    {
      label: 'Создать аккаунт',
      done: true,
      locked: false,
      action: null,
    },
    {
      label: 'Активировать пробный период',
      done: hasSubscription,
      locked: false,
      action: hasSubscription ? null : onActivateTrial,
    },
    {
      label: 'Установить приложение и подключиться',
      done: hasConnected,
      locked: !hasSubscription,
      action: () => navigate('/install'),
    },
    {
      label: 'Продлить подписку',
      done: hasMadePayment,
      locked: !hasConnected,
      action: () => navigate('/subscription'),
    },
  ]

  const allDone = steps.every(s => s.done)
  const currentStepIndex = steps.findIndex(s => !s.done && !s.locked)

  useEffect(() => {
    if (allDone && !completed) {
      setCelebrating(true)
      const t = setTimeout(() => {
        localStorage.setItem(LS_COMPLETED, 'true')
        setCompleted(true)
      }, 2000)
      return () => clearTimeout(t)
    }
  }, [allDone, completed])

  if (dismissed || completed) return null

  const handleDismiss = () => {
    localStorage.setItem(LS_DISMISSED, 'true')
    setDismissed(true)
  }

  if (celebrating) {
    return (
      <div className="rounded-card border border-green-500/40 bg-green-500/5 p-4 mb-4 flex flex-col items-center gap-2 text-center">
        <span className="text-2xl">🎉</span>
        <p className="text-sm font-semibold text-green-400">Всё настроено!</p>
      </div>
    )
  }

  return (
    <div className="rounded-card border border-accent/50 bg-accent/5 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-accent">🚀 Начало работы</span>
        <button
          onClick={handleDismiss}
          className="text-text-muted hover:text-text-secondary transition-colors"
          aria-label="Скрыть"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex gap-1 mb-4">
        {steps.map((s, i) => (
          <div
            key={i}
            className={`flex-1 h-1 rounded-full transition-colors duration-300 ${
              s.done ? 'bg-green-500' : i === currentStepIndex ? 'bg-accent' : 'bg-border-neutral'
            }`}
          />
        ))}
      </div>

      <div className="flex flex-col gap-2">
        {steps.map((s, i) => {
          const isActive = i === currentStepIndex
          return (
            <button
              key={i}
              onClick={s.action && !s.locked ? s.action : undefined}
              disabled={s.locked || s.done || !s.action}
              className={`flex items-center gap-3 rounded-input px-3 py-2 text-sm transition-colors w-full text-left ${
                isActive
                  ? 'bg-accent/10 hover:bg-accent/20 cursor-pointer'
                  : 'cursor-default'
              } ${s.locked ? 'opacity-40' : ''}`}
            >
              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                s.done
                  ? 'bg-green-500 text-white'
                  : isActive
                  ? 'bg-accent text-white'
                  : 'bg-border-neutral text-text-muted'
              }`}>
                {s.done ? '✓' : s.locked ? '🔒' : i + 1}
              </div>

              <span className={`flex-1 ${s.done ? 'line-through text-text-muted' : isActive ? 'text-text-primary font-medium' : 'text-text-secondary'}`}>
                {s.label}
              </span>

              {isActive && <span className="text-accent text-xs">→</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/components/OnboardingCard.tsx
git commit -m "feat: update OnboardingCard to use hasConnected, rename step 3"
```

---

## Task 9: Frontend — wire `hasConnected` and `TrafficDisplay` in `HomePage`

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Pass `hasConnected` to `OnboardingCard`**

In `HomePage.tsx`, find the `<OnboardingCard>` usage and add the new prop:

```tsx
<OnboardingCard
  hasMadePayment={user?.has_made_payment ?? false}
  hasSubscription={sub !== null && sub !== undefined}
  hasConnected={sub?.has_connected ?? false}
  onActivateTrial={scrollToTrialCta}
/>
```

- [ ] **Step 2: Add `TrafficDisplay` component and update `TrialCard`**

Add the `TrafficDisplay` function before `TrialCard` (or inline inside it):

```tsx
function TrafficDisplay({ sub }: { sub: SubscriptionResponse }) {
  if (sub.traffic_used_bytes === null || sub.traffic_limit_gb === null) {
    const gb = sub.traffic_limit_gb
    return <span>{gb != null ? `Трафик: ${gb} ГБ (пробный лимит)` : 'Трафик: недоступен'}</span>
  }
  const limitBytes = sub.traffic_limit_gb * 1024 ** 3
  const remainingBytes = Math.max(0, limitBytes - sub.traffic_used_bytes)
  const remainingGb = (remainingBytes / 1024 ** 3).toFixed(1)
  return <span>{remainingGb} из {sub.traffic_limit_gb} ГБ осталось</span>
}
```

In `TrialCard`, replace the hardcoded line:

```tsx
<span>Трафик: 30 ГБ (пробный лимит)</span>
```

with:

```tsx
<TrafficDisplay sub={sub} />
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/HomePage.tsx
git commit -m "feat: show real traffic remaining and wire hasConnected in HomePage"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: all pass, 0 errors.

- [ ] **TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Manual smoke test checklist**
  - Admin panel → Remnawave section shows "Секрет вебхука" field
  - HomePage for trial user: traffic shows "X из 30 ГБ осталось" (or fallback if Remnawave unreachable)
  - OnboardingCard step 3 label reads "Установить приложение и подключиться"
  - OnboardingCard step 3 stays unchecked until `has_connected: true` in API response
  - Step 4 stays locked until step 3 is done
  - `POST /api/webhooks/remnawave` with wrong signature → 401
  - `POST /api/webhooks/remnawave` with `user.expired` event → 200, no DB write
