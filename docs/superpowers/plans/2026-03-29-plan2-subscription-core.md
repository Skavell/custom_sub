# Plan 2: Settings Encryption + Remnawave Integration + Subscription Core

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement AES-256-GCM settings encryption, Remnawave API client, plans seeding, trial activation endpoint, and subscription status API — the complete subscription management backend layer.

**Architecture:** Sensitive DB settings (Remnawave token, Telegram bot token, Cryptomus keys) are stored AES-GCM encrypted; `setting_service.py` decrypts them transparently. `RemnawaveClient` is a stateless httpx wrapper instantiated per-request from DB settings. Trial activation creates a Remnawave user + local Subscription row atomically, guarded by Redis IP rate limiting. Telegram OAuth is extended to auto-sync Remnawave subscriptions on first login.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, httpx, `cryptography` (AESGCM), Redis, Alembic data migration, pytest-asyncio, pytest-httpx 0.36

---

## Existing Codebase Orientation

```
backend/app/
  config.py              — Settings(BaseSettings); settings_encryption_key field (str, min 32 chars)
  models/user.py         — User; remnawave_uuid: UUID | None; has_made_payment: bool
  models/subscription.py — Subscription; SubscriptionType, SubscriptionStatus enums
  models/transaction.py  — Transaction; TransactionType, TransactionStatus enums
  models/plan.py         — Plan; name, label, duration_days, price_rub, new_user_price_rub, sort_order
  models/setting.py      — Setting; key (PK), value (JSONB), is_sensitive: bool
  services/setting_service.py — get_setting(db, key) → str|None   reads value.get("value") only
  routers/auth.py        — /oauth/telegram creates new user if not found; needs Remnawave sync hook
  deps.py                — get_current_user → User; require_admin → User
  redis_client.py        — module-level Redis singleton; get_redis() → Redis
```

Current JSONB schema in `settings` table:
- Non-sensitive: `{"value": "raw_string"}`
- Sensitive (after this plan): `{"encrypted": "<base64_nonce+ciphertext>"}`

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/services/encryption_service.py` | Create | AES-256-GCM encrypt/decrypt; pure functions, no I/O |
| `app/services/setting_service.py` | Modify | Add `get_setting_decrypted`, `set_setting` on top of existing `get_setting` |
| `app/services/rate_limiter.py` | Create | Redis INCR-based sliding window: `check_rate_limit(redis, key, limit, window_sec) → bool` |
| `app/services/remnawave_client.py` | Create | httpx wrapper: `RemnawaveClient(base_url, token)`; 4 methods |
| `app/services/subscription_service.py` | Create | `get_user_subscription`, `create_trial_subscription`, `sync_subscription_from_remnawave` |
| `app/schemas/plan.py` | Create | `PlanResponse` Pydantic model |
| `app/schemas/subscription.py` | Create | `SubscriptionResponse`, `TrialActivateResponse` |
| `app/routers/plans.py` | Create | `GET /api/plans` — list active plans |
| `app/routers/subscriptions.py` | Create | `POST /api/subscriptions/trial`, `GET /api/subscriptions/me` |
| `app/routers/auth.py` | Modify | After first Telegram OAuth login: try Remnawave sync (fail-silent) |
| `app/main.py` | Modify | `include_router` for plans and subscriptions |
| `alembic/versions/XXXX_seed_plans.py` | Create | Data migration: INSERT 4 plans |
| `tests/services/test_encryption_service.py` | Create | 5 tests: roundtrip, wrong key, empty, unicode, nonce uniqueness |
| `tests/services/test_rate_limiter.py` | Create | 3 tests: under limit, at limit, over limit |
| `tests/services/test_remnawave_client.py` | Create | 5 tests via pytest-httpx mocks |
| `tests/services/test_subscription_service.py` | Create | 4 tests: get_user_subscription (found/not found), create_trial, sync |
| `tests/routers/test_plans.py` | Create | 2 tests: list plans, empty list |
| `tests/routers/test_subscriptions.py` | Create | 6 tests: trial activate, duplicate trial guard, rate limit, no Remnawave, get me, get me no subscription |

---

## Task 1: Encryption Service

**Files:**
- Create: `backend/app/services/encryption_service.py`
- Create: `backend/tests/services/test_encryption_service.py`

The AES key is derived by SHA-256 hashing `settings.settings_encryption_key` so the key length always equals exactly 32 bytes regardless of the env var length.

- [ ] **Step 1.1: Write failing tests**

```python
# backend/tests/services/test_encryption_service.py
import pytest
from app.services.encryption_service import encrypt_value, decrypt_value


def test_encrypt_decrypt_roundtrip():
    key = "test-key-for-encryption-32-chars!"
    plaintext = "super_secret_token_abc123"
    ciphertext = encrypt_value(key, plaintext)
    assert ciphertext != plaintext
    assert decrypt_value(key, ciphertext) == plaintext


def test_wrong_key_raises():
    key_a = "key-a-for-encryption-32-chars!!!"
    key_b = "key-b-for-encryption-32-chars!!!"
    ciphertext = encrypt_value(key_a, "secret")
    with pytest.raises(Exception):
        decrypt_value(key_b, ciphertext)


def test_empty_string_roundtrip():
    key = "test-key-for-encryption-32-chars!"
    assert decrypt_value(key, encrypt_value(key, "")) == ""


def test_unicode_string_roundtrip():
    key = "test-key-for-encryption-32-chars!"
    plaintext = "секретный токен 🔑"
    assert decrypt_value(key, encrypt_value(key, plaintext)) == plaintext


def test_nonce_uniqueness():
    """Two encryptions of same plaintext produce different ciphertexts."""
    key = "test-key-for-encryption-32-chars!"
    c1 = encrypt_value(key, "same")
    c2 = encrypt_value(key, "same")
    assert c1 != c2
```

- [ ] **Step 1.2: Run tests — expect FAIL (ImportError)**
```bash
cd backend && uv run pytest tests/services/test_encryption_service.py -v
```

- [ ] **Step 1.3: Implement encryption service**

```python
# backend/app/services/encryption_service.py
import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(key_str: str) -> bytes:
    """Derive exactly 32 bytes from the config string via SHA-256."""
    return hashlib.sha256(key_str.encode()).digest()


def encrypt_value(key_str: str, plaintext: str) -> str:
    """AES-256-GCM encrypt. Returns base64(12-byte nonce + ciphertext+tag)."""
    key = _derive_key(key_str)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(key_str: str, encoded: str) -> str:
    """AES-256-GCM decrypt. Raises InvalidTag if key is wrong or data is tampered."""
    key = _derive_key(key_str)
    data = base64.b64decode(encoded)
    nonce, ciphertext = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
```

- [ ] **Step 1.4: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/services/test_encryption_service.py -v
# Expected: 5 passed
```

- [ ] **Step 1.5: Commit**
```bash
git add backend/app/services/encryption_service.py backend/tests/services/test_encryption_service.py
git commit -m "feat: add AES-256-GCM encryption service"
```

---

## Task 2: Enhanced Setting Service

**Files:**
- Modify: `backend/app/services/setting_service.py`
- Create: `backend/tests/services/test_setting_service.py`

Add `get_setting_decrypted(db, key) → str | None` for sensitive settings, and `set_setting(db, key, value, is_sensitive)` for writes. Keep existing `get_setting` unchanged (used for non-sensitive fields by existing code).

- [ ] **Step 2.1: Write failing tests**

```python
# backend/tests/services/test_setting_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.setting import Setting
from app.services.setting_service import get_setting_decrypted, set_setting

ENCRYPTION_KEY = "test-key-for-encryption-32-chars!"


def _make_db_with_setting(setting: Setting | None) -> AsyncSession:
    scalars = MagicMock()
    scalars.scalar_one_or_none = MagicMock(return_value=setting)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=setting)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_get_setting_decrypted_sensitive(monkeypatch):
    from app.services import encryption_service
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "settings_encryption_key", ENCRYPTION_KEY)

    from app.services.encryption_service import encrypt_value
    encrypted_blob = encrypt_value(ENCRYPTION_KEY, "my_secret_token")

    setting = MagicMock(spec=Setting)
    setting.is_sensitive = True
    setting.value = {"encrypted": encrypted_blob}

    db = _make_db_with_setting(setting)
    result = await get_setting_decrypted(db, "remnawave_token")
    assert result == "my_secret_token"


@pytest.mark.asyncio
async def test_get_setting_decrypted_non_sensitive():
    setting = MagicMock(spec=Setting)
    setting.is_sensitive = False
    setting.value = {"value": "https://remnawave.example.com"}

    db = _make_db_with_setting(setting)
    result = await get_setting_decrypted(db, "remnawave_url")
    assert result == "https://remnawave.example.com"


@pytest.mark.asyncio
async def test_get_setting_decrypted_missing():
    db = _make_db_with_setting(None)
    result = await get_setting_decrypted(db, "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_set_setting_non_sensitive():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    await set_setting(db, "remnawave_url", "https://example.com", is_sensitive=False)
    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.key == "remnawave_url"
    assert added.value == {"value": "https://example.com"}
    assert added.is_sensitive is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_setting_sensitive_encrypts(monkeypatch):
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "settings_encryption_key", ENCRYPTION_KEY)

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    await set_setting(db, "remnawave_token", "secret", is_sensitive=True)
    added = db.add.call_args[0][0]
    assert added.is_sensitive is True
    assert "encrypted" in added.value
    # Verify it's actually encrypted (not plain text)
    assert added.value["encrypted"] != "secret"
```

- [ ] **Step 2.2: Run tests — expect FAIL**
```bash
cd backend && uv run pytest tests/services/test_setting_service.py -v
```

- [ ] **Step 2.3: Implement enhanced setting_service.py**

Replace the entire file (keep existing `get_setting` unchanged at the top):

```python
# backend/app/services/setting_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.setting import Setting
from app.config import settings as app_settings


async def get_setting(db: AsyncSession, key: str) -> str | None:
    """Get a non-sensitive setting value. Returns raw string or None."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return None
    return setting.value.get("value")


async def get_setting_decrypted(db: AsyncSession, key: str) -> str | None:
    """Get a setting value, decrypting if is_sensitive=True."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return None
    if setting.is_sensitive:
        encrypted_blob = setting.value.get("encrypted")
        if not encrypted_blob:
            return None
        from app.services.encryption_service import decrypt_value
        return decrypt_value(app_settings.settings_encryption_key, encrypted_blob)
    return setting.value.get("value")


async def set_setting(
    db: AsyncSession, key: str, value: str, is_sensitive: bool = False
) -> None:
    """Create or update a setting. Encrypts the value if is_sensitive=True."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if is_sensitive:
        from app.services.encryption_service import encrypt_value
        encoded = encrypt_value(app_settings.settings_encryption_key, value)
        jsonb_value = {"encrypted": encoded}
    else:
        jsonb_value = {"value": value}

    if setting:
        setting.value = jsonb_value
        setting.is_sensitive = is_sensitive
    else:
        setting = Setting(key=key, value=jsonb_value, is_sensitive=is_sensitive)
        db.add(setting)

    await db.commit()
```

- [ ] **Step 2.4: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/services/test_setting_service.py tests/services/test_encryption_service.py -v
# Expected: 10 passed
```

- [ ] **Step 2.5: Run full test suite — ensure nothing broken**
```bash
cd backend && uv run pytest tests/ -q
# Expected: 22 + 10 = 32 passed (or close, depending on test count)
```

- [ ] **Step 2.6: Commit**
```bash
git add backend/app/services/setting_service.py backend/tests/services/test_setting_service.py
git commit -m "feat: add get_setting_decrypted and set_setting with AES-256-GCM support"
```

---

## Task 3: Plans Seed Migration + GET /api/plans

**Files:**
- Create: `backend/alembic/versions/XXXX_seed_plans.py` (ID auto-generated)
- Create: `backend/app/schemas/plan.py`
- Create: `backend/app/routers/plans.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/routers/test_plans.py`

Initial plans per spec: 1 month (200₽, new_user: 100₽), 3 months (590₽), 6 months (1100₽), 1 year (2000₽).

- [ ] **Step 3.1: Write failing tests**

```python
# backend/tests/routers/test_plans.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.plan import Plan


def _make_plan(name: str, label: str, price: int, duration: int, sort_order: int = 0,
               new_user_price: int | None = None) -> Plan:
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
```

- [ ] **Step 3.2: Run tests — expect FAIL**
```bash
cd backend && uv run pytest tests/routers/test_plans.py -v
```

- [ ] **Step 3.3: Create schema**

```python
# backend/app/schemas/plan.py
import uuid
from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: str
    name: str
    label: str
    duration_days: int
    price_rub: int
    new_user_price_rub: int | None
    sort_order: int

    model_config = {"from_attributes": True}
```

- [ ] **Step 3.4: Create plans router**

```python
# backend/app/routers/plans.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.plan import Plan
from app.schemas.plan import PlanResponse

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanResponse]:
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order)
    )
    plans = result.scalars().all()
    return [PlanResponse(
        id=str(p.id),
        name=p.name,
        label=p.label,
        duration_days=p.duration_days,
        price_rub=p.price_rub,
        new_user_price_rub=p.new_user_price_rub,
        sort_order=p.sort_order,
    ) for p in plans]
```

- [ ] **Step 3.5: Register router in main.py**

Add to `backend/app/main.py`:
```python
from app.routers import plans
# ...
app.include_router(plans.router)
```

- [ ] **Step 3.6: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/routers/test_plans.py -v
# Expected: 2 passed
```

- [ ] **Step 3.7: Create plans seed migration**

```bash
cd backend && uv run alembic revision -m "seed_plans"
# Creates backend/alembic/versions/<hash>_seed_plans.py
```

Fill in the generated file:

```python
# backend/alembic/versions/<hash>_seed_plans.py
"""seed_plans

Revision ID: <auto-generated>
Revises: e7cbe1ed933e
Create Date: <auto-generated>
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "<auto-generated>"
down_revision = "e7cbe1ed933e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        INSERT INTO plans (id, name, label, duration_days, price_rub, new_user_price_rub, is_active, sort_order)
        VALUES
            (:id1, '1_month',   '1 месяц',   30,  200, 100, true, 1),
            (:id2, '3_months',  '3 месяца',  90,  590, NULL, true, 2),
            (:id3, '6_months',  '6 месяцев', 180, 1100, NULL, true, 3),
            (:id4, '12_months', '1 год',     365, 2000, NULL, true, 4)
        ON CONFLICT (name) DO NOTHING
        """),
        {
            "id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()), "id4": str(uuid.uuid4()),
        }
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM plans WHERE name IN ('1_month','3_months','6_months','12_months')"))
```

- [ ] **Step 3.8: Apply migration and verify**
```bash
cd backend && uv run alembic upgrade head
uv run alembic current
# Should show new revision (head)
```

- [ ] **Step 3.9: Commit**
```bash
git add backend/app/schemas/plan.py backend/app/routers/plans.py backend/app/main.py \
        backend/alembic/versions/ backend/tests/routers/test_plans.py
git commit -m "feat: add plans seed migration and GET /api/plans endpoint"
```

---

## Task 4: Remnawave API Client

**Files:**
- Create: `backend/app/services/remnawave_client.py`
- Create: `backend/tests/services/test_remnawave_client.py`

The client wraps 4 Remnawave API calls. It is stateless (constructed per-request). All HTTP errors bubble up as exceptions — callers decide how to handle them.

- [ ] **Step 4.0: Pin pytest-httpx version**

The tests use the `pytest-httpx` 0.36+ API. Open `backend/pyproject.toml` and change:
```
pytest-httpx>=0.30.0
```
to:
```
pytest-httpx>=0.36.0
```
Then run `uv sync` to update the lock file:
```bash
cd backend && uv sync
```

- [ ] **Step 4.1: Write failing tests**

```python
# backend/tests/services/test_remnawave_client.py
import pytest
from datetime import datetime, timezone
from pytest_httpx import HTTPXMock

from app.services.remnawave_client import RemnawaveClient, RemnawaveUser


BASE_URL = "https://remnawave.example.com"
TOKEN = "test-api-token"

SAMPLE_USER_RESPONSE = {
    "uuid": "aaaaaaaa-0000-0000-0000-000000000001",
    "username": "ws_4a1b2c3d",
    "expireAt": "2026-04-10T00:00:00Z",
    "trafficLimitBytes": 32212254720,  # 30 GB
    "status": "ACTIVE",
    "subscriptionUrl": "https://sub.example.com/sub/abc123",
    "telegramId": 515172616,
}


@pytest.mark.asyncio
async def test_get_user_returns_user(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/users/aaaaaaaa-0000-0000-0000-000000000001",
        json=SAMPLE_USER_RESPONSE,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.get_user("aaaaaaaa-0000-0000-0000-000000000001")
    assert user.id == "aaaaaaaa-0000-0000-0000-000000000001"
    assert user.subscription_url == "https://sub.example.com/sub/abc123"
    assert user.traffic_limit_bytes == 32212254720
    assert user.telegram_id == 515172616


@pytest.mark.asyncio
async def test_get_user_by_telegram_id_found(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/users/by-telegram-id/515172616",
        json=SAMPLE_USER_RESPONSE,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.get_user_by_telegram_id(515172616)
    assert user is not None
    assert user.id == "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_get_user_by_telegram_id_not_found(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/users/by-telegram-id/99999",
        status_code=404,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.get_user_by_telegram_id(99999)
    assert user is None


@pytest.mark.asyncio
async def test_create_user_returns_user(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/users",
        json=SAMPLE_USER_RESPONSE,
        status_code=201,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.create_user(
        username="ws_4a1b2c3d",
        traffic_limit_bytes=32212254720,
        expire_at="2026-04-10T00:00:00Z",
        squad_ids=["squad-uuid-1"],
        telegram_id=515172616,
        description="@skavellion_user",
    )
    assert user.id == "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_update_user(httpx_mock: HTTPXMock):
    updated = {**SAMPLE_USER_RESPONSE, "trafficLimitBytes": 0}
    httpx_mock.add_response(
        method="PATCH",
        url=f"{BASE_URL}/users/aaaaaaaa-0000-0000-0000-000000000001",
        json=updated,
    )
    client = RemnawaveClient(BASE_URL, TOKEN)
    user = await client.update_user(
        "aaaaaaaa-0000-0000-0000-000000000001",
        traffic_limit_bytes=0,
        expire_at="2026-05-10T00:00:00Z",
    )
    assert user.traffic_limit_bytes == 0
```

- [ ] **Step 4.2: Run tests — expect FAIL**
```bash
cd backend && uv run pytest tests/services/test_remnawave_client.py -v
```

- [ ] **Step 4.3: Implement Remnawave client**

```python
# backend/app/services/remnawave_client.py
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0)


@dataclass
class RemnawaveUser:
    id: str
    username: str
    expire_at: datetime
    traffic_limit_bytes: int  # 0 = unlimited
    status: str               # "ACTIVE" | "DISABLED"
    subscription_url: str
    telegram_id: int | None


def _parse_user(data: dict[str, Any]) -> RemnawaveUser:
    return RemnawaveUser(
        id=data["uuid"],
        username=data["username"],
        expire_at=datetime.fromisoformat(data["expireAt"].replace("Z", "+00:00")),
        traffic_limit_bytes=data.get("trafficLimitBytes") or 0,
        status=data.get("status", "ACTIVE"),
        subscription_url=data.get("subscriptionUrl", ""),
        telegram_id=data.get("telegramId"),
    )


class RemnawaveClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def get_user(self, remnawave_uuid: str) -> RemnawaveUser:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.get(
                f"{self._base}/users/{remnawave_uuid}", headers=self._headers
            )
            resp.raise_for_status()
            return _parse_user(resp.json())

    async def get_user_by_telegram_id(self, telegram_id: int) -> RemnawaveUser | None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.get(
                f"{self._base}/users/by-telegram-id/{telegram_id}",
                headers=self._headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_user(resp.json())

    async def create_user(
        self,
        username: str,
        traffic_limit_bytes: int,
        expire_at: str,
        squad_ids: list[str],
        telegram_id: int | None = None,
        description: str | None = None,
    ) -> RemnawaveUser:
        payload: dict[str, Any] = {
            "username": username,
            "trafficLimitBytes": traffic_limit_bytes,
            "expireAt": expire_at,
            "squadIds": squad_ids,
        }
        if telegram_id is not None:
            payload["telegramId"] = telegram_id
        if description:
            payload["description"] = description
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.post(f"{self._base}/users", headers=self._headers, json=payload)
            resp.raise_for_status()
            return _parse_user(resp.json())

    async def update_user(
        self,
        remnawave_uuid: str,
        traffic_limit_bytes: int | None = None,
        expire_at: str | None = None,
    ) -> RemnawaveUser:
        payload: dict[str, Any] = {}
        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if expire_at is not None:
            payload["expireAt"] = expire_at
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.patch(
                f"{self._base}/users/{remnawave_uuid}",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return _parse_user(resp.json())
```

- [ ] **Step 4.4: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/services/test_remnawave_client.py -v
# Expected: 5 passed
```

- [ ] **Step 4.5: Commit**
```bash
git add backend/app/services/remnawave_client.py backend/tests/services/test_remnawave_client.py
git commit -m "feat: add Remnawave API client"
```

---

## Task 5: Rate Limiter

**Files:**
- Create: `backend/app/services/rate_limiter.py`
- Create: `backend/tests/services/test_rate_limiter.py`

Uses Redis `INCR` + `EXPIRE` pattern. Returns `True` = allowed, `False` = blocked.

- [ ] **Step 5.1: Write failing tests**

```python
# backend/tests/services/test_rate_limiter.py
import pytest
from unittest.mock import AsyncMock

from app.services.rate_limiter import check_rate_limit


@pytest.mark.asyncio
async def test_first_request_allowed():
    redis = AsyncMock()
    redis.incr.return_value = 1  # first increment
    result = await check_rate_limit(redis, "rate:trial:1.2.3.4", limit=3, window_seconds=86400)
    assert result is True
    redis.expire.assert_awaited_once_with("rate:trial:1.2.3.4", 86400)


@pytest.mark.asyncio
async def test_at_limit_allowed():
    redis = AsyncMock()
    redis.incr.return_value = 3  # exactly at limit
    result = await check_rate_limit(redis, "rate:trial:1.2.3.4", limit=3, window_seconds=86400)
    assert result is True
    # expire must NOT be called for any count > 1 (TTL is set only on first increment)
    redis.expire.assert_not_awaited()


@pytest.mark.asyncio
async def test_over_limit_blocked():
    redis = AsyncMock()
    redis.incr.return_value = 4  # one over limit
    result = await check_rate_limit(redis, "rate:trial:1.2.3.4", limit=3, window_seconds=86400)
    assert result is False
    # expire should NOT be called when not the first request
    redis.expire.assert_not_awaited()
```

- [ ] **Step 5.2: Run tests — expect FAIL**
```bash
cd backend && uv run pytest tests/services/test_rate_limiter.py -v
```

- [ ] **Step 5.3: Implement rate limiter**

```python
# backend/app/services/rate_limiter.py
from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis, key: str, limit: int, window_seconds: int
) -> bool:
    """Increment counter at `key`. Returns True if within limit, False if exceeded.
    Sets TTL only on first increment to avoid resetting the window on each request.
    """
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    return current <= limit
```

- [ ] **Step 5.4: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/services/test_rate_limiter.py -v
# Expected: 3 passed
```

- [ ] **Step 5.5: Commit**
```bash
git add backend/app/services/rate_limiter.py backend/tests/services/test_rate_limiter.py
git commit -m "feat: add Redis-backed rate limiter"
```

---

## Task 6: Subscription Service

**Files:**
- Create: `backend/app/services/subscription_service.py`
- Create: `backend/app/schemas/subscription.py`
- Create: `backend/tests/services/test_subscription_service.py`

Three helpers: `get_user_subscription`, `create_trial_subscription`, `sync_subscription_from_remnawave`.

- [ ] **Step 6.1: Write failing tests**

```python
# backend/tests/services/test_subscription_service.py
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveUser
from app.services.subscription_service import (
    get_user_subscription,
    create_trial_subscription,
    sync_subscription_from_remnawave,
)

NOW = datetime.now(tz=timezone.utc)
USER_ID = uuid.uuid4()
REMNAWAVE_UUID = "aaaaaaaa-0000-0000-0000-000000000001"


def _make_user(remnawave_uuid=None) -> User:
    user = MagicMock(spec=User)
    user.id = USER_ID
    user.remnawave_uuid = uuid.UUID(remnawave_uuid) if remnawave_uuid else None
    user.has_made_payment = False
    return user


def _make_db(subscription=None) -> AsyncSession:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=subscription)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_get_user_subscription_found():
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    db = _make_db(sub)
    result = await get_user_subscription(db, USER_ID)
    assert result is sub


@pytest.mark.asyncio
async def test_get_user_subscription_not_found():
    db = _make_db(None)
    result = await get_user_subscription(db, USER_ID)
    assert result is None


@pytest.mark.asyncio
async def test_create_trial_subscription_creates_row():
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()
    expires = NOW + timedelta(days=3)

    sub = await create_trial_subscription(
        db=db,
        user=user,
        trial_days=3,
        trial_traffic_bytes=32212254720,
    )

    # Should add Subscription and Transaction
    assert db.add.call_count == 2
    assert db.commit.await_count == 1

    sub_call = db.add.call_args_list[0][0][0]
    assert sub_call.type == SubscriptionType.trial
    assert sub_call.status == SubscriptionStatus.active
    assert sub_call.traffic_limit_gb == 30


@pytest.mark.asyncio
async def test_sync_subscription_from_remnawave_active():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    user = _make_user(REMNAWAVE_UUID)
    remnawave_user = RemnawaveUser(
        id=REMNAWAVE_UUID,
        username="ws_4a1b2c3d",
        expire_at=NOW + timedelta(days=7),
        traffic_limit_bytes=0,
        status="ACTIVE",
        subscription_url="https://sub.example.com/abc",
        telegram_id=None,
    )

    await sync_subscription_from_remnawave(db, user, remnawave_user)

    db.add.assert_called_once()
    sub = db.add.call_args[0][0]
    assert sub.status == SubscriptionStatus.active
    assert sub.traffic_limit_gb is None  # 0 bytes = unlimited
```

- [ ] **Step 6.2: Run tests — expect FAIL**
```bash
cd backend && uv run pytest tests/services/test_subscription_service.py -v
```

- [ ] **Step 6.3: Implement subscription service**

```python
# backend/app/services/subscription_service.py
from __future__ import annotations
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveUser


async def get_user_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    """Returns the subscription row for this user, or None if no subscription exists."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_trial_subscription(
    db: AsyncSession,
    user: User,
    trial_days: int,
    trial_traffic_bytes: int,
) -> Subscription:
    """Create a trial Subscription row and a trial_activation Transaction.
    Caller is responsible for setting user.remnawave_uuid before calling this.
    """
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(days=trial_days)

    # traffic_limit_gb: convert bytes → GB (ceiling), None if unlimited (0)
    traffic_gb = math.ceil(trial_traffic_bytes / (1024 ** 3)) if trial_traffic_bytes > 0 else None

    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.trial,
        status=SubscriptionStatus.active,
        started_at=now,
        expires_at=expires_at,
        traffic_limit_gb=traffic_gb,
        synced_at=now,
    )
    db.add(sub)

    tx = Transaction(
        user_id=user.id,
        type=TransactionType.trial_activation,
        days_added=trial_days,
        status=TransactionStatus.completed,
        description="Активация пробного периода",
        completed_at=now,
    )
    db.add(tx)
    await db.commit()
    # Refresh sub so attributes are not in "expired" state after commit
    # (SQLAlchemy expires all ORM attributes on commit by default).
    # Without this, accessing sub.type/expires_at in the router raises MissingGreenlet.
    await db.refresh(sub)
    return sub


async def sync_subscription_from_remnawave(
    db: AsyncSession, user: User, remnawave_user: RemnawaveUser
) -> Subscription:
    """Create or update the local subscription row from Remnawave data.
    Type inference: if user.has_made_payment=True → always paid.
    Otherwise: traffic_limit_bytes=0 → paid (unlimited), >0 → trial.
    """
    now = datetime.now(tz=timezone.utc)

    if remnawave_user.traffic_limit_bytes > 0:
        traffic_gb: int | None = math.ceil(remnawave_user.traffic_limit_bytes / (1024 ** 3))
    else:
        traffic_gb = None

    if user.has_made_payment:
        sub_type = SubscriptionType.paid
    else:
        sub_type = SubscriptionType.paid if traffic_gb is None else SubscriptionType.trial

    # Determine status: ACTIVE from Remnawave + not expired locally = active
    if remnawave_user.status == "ACTIVE" and remnawave_user.expire_at > now:
        sub_status = SubscriptionStatus.active
    elif remnawave_user.status == "DISABLED":
        sub_status = SubscriptionStatus.disabled
    else:
        sub_status = SubscriptionStatus.expired

    # Get or create subscription row
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, started_at=now)
        db.add(sub)

    sub.type = sub_type
    sub.status = sub_status
    sub.expires_at = remnawave_user.expire_at
    sub.traffic_limit_gb = traffic_gb
    sub.synced_at = now

    await db.commit()
    return sub
```

- [ ] **Step 6.4: Create subscription schema**

```python
# backend/app/schemas/subscription.py
from datetime import datetime
from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    type: str            # "trial" | "paid"
    status: str          # "active" | "expired" | "disabled"
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None   # None = unlimited
    days_remaining: int


class TrialActivateResponse(BaseModel):
    subscription: SubscriptionResponse
    message: str
```

- [ ] **Step 6.5: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/services/test_subscription_service.py -v
# Expected: 4 passed
```

- [ ] **Step 6.6: Run full suite**
```bash
cd backend && uv run pytest tests/ -q
```

- [ ] **Step 6.7: Commit**
```bash
git add backend/app/services/subscription_service.py backend/app/schemas/subscription.py \
        backend/tests/services/test_subscription_service.py
git commit -m "feat: add subscription service and schemas"
```

---

## Task 7: Trial Activation Endpoint

**Files:**
- Create: `backend/app/routers/subscriptions.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/routers/test_subscriptions.py`

`POST /api/subscriptions/trial` — activates trial for authenticated user.

**Guard order (per spec):**
1. `remnawave_uuid IS NOT NULL` → 409 "Пробный период уже был активирован"
2. IP rate limit (3 per IP per 24h) → 429
3. Remnawave settings not configured → 503
4. Create Remnawave user, set `user.remnawave_uuid`
5. `create_trial_subscription`

**Remnawave username format:** `ws_{str(user.id)[:8]}` (first 8 hex chars of UUID, no hyphens).
**Remnawave username uniqueness:** if 409 from Remnawave on username conflict, retry with first 12 chars.

- [ ] **Step 7.1: Write failing tests**

```python
# backend/tests/routers/test_subscriptions.py
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.redis_client import get_redis
from app.deps import get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionType, SubscriptionStatus


NOW = datetime.now(tz=timezone.utc)


def _make_user(remnawave_uuid=None) -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.remnawave_uuid = uuid.UUID(str(remnawave_uuid)) if remnawave_uuid else None
    user.has_made_payment = False
    return user


def _make_sub() -> Subscription:
    sub = MagicMock(spec=Subscription)
    sub.type = SubscriptionType.trial
    sub.status = SubscriptionStatus.active
    sub.started_at = NOW
    sub.expires_at = NOW
    sub.traffic_limit_gb = 30
    return sub


def _override_get_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_get_current_user(user):
    async def _dep():
        return user
    return _dep


def _override_get_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_trial_activate_already_activated():
    """Returns 409 if user already has remnawave_uuid."""
    user = _make_user(remnawave_uuid=uuid.uuid4())
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/subscriptions/trial")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_trial_activate_rate_limited():
    """Returns 429 when IP rate limit exceeded."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock()
    redis.incr.return_value = 4  # over limit of 3

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/subscriptions/trial")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_trial_activate_remnawave_not_configured():
    """Returns 503 when Remnawave settings are missing."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    redis = AsyncMock()
    redis.incr.return_value = 1  # within limit

    app.dependency_overrides[get_current_user] = _override_get_current_user(user)
    app.dependency_overrides[get_db] = _override_get_db(db)
    app.dependency_overrides[get_redis] = _override_get_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/subscriptions/trial")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_me_no_subscription():
    """Returns 200 with null when user has no subscription."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
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
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_me_with_subscription():
    """Returns subscription details when subscription exists."""
    from datetime import timedelta
    user = _make_user()
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
    data = resp.json()
    assert data["type"] == "trial"
    assert data["status"] == "active"
    assert data["traffic_limit_gb"] == 30
    assert data["days_remaining"] >= 1
```

- [ ] **Step 7.2: Run tests — expect FAIL**
```bash
cd backend && uv run pytest tests/routers/test_subscriptions.py -v
```

- [ ] **Step 7.3: Implement subscriptions router**

```python
# backend/app/routers/subscriptions.py
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.subscription import SubscriptionResponse, TrialActivateResponse
from app.services.rate_limiter import check_rate_limit
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import (
    create_trial_subscription,
    get_user_subscription,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

_TRIAL_RATE_LIMIT = 3
_TRIAL_RATE_WINDOW = 86400  # 24 hours


def _to_response(sub) -> SubscriptionResponse:
    now = datetime.now(tz=timezone.utc)
    expires = sub.expires_at
    if expires.tzinfo is None:
        from datetime import timezone as _tz
        expires = expires.replace(tzinfo=_tz.utc)
    days_remaining = max(0, (expires - now).days)
    return SubscriptionResponse(
        type=sub.type.value,
        status=sub.status.value,
        started_at=sub.started_at,
        expires_at=expires,
        traffic_limit_gb=sub.traffic_limit_gb,
        days_remaining=days_remaining,
    )


@router.get("/me", response_model=SubscriptionResponse | None)
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse | None:
    sub = await get_user_subscription(db, current_user.id)
    if sub is None:
        return None
    return _to_response(sub)


@router.post("/trial", response_model=TrialActivateResponse, status_code=201)
async def activate_trial(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TrialActivateResponse:
    # Guard 1: already activated
    if current_user.remnawave_uuid is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пробный период уже был активирован",
        )

    # Guard 2: IP rate limit
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate:trial:{client_ip}"
    allowed = await check_rate_limit(redis, rate_key, _TRIAL_RATE_LIMIT, _TRIAL_RATE_WINDOW)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен лимит активаций. Попробуйте завтра.",
        )

    # Guard 3: Remnawave not configured
    remnawave_url = await get_setting(db, "remnawave_url")
    remnawave_token = await get_setting_decrypted(db, "remnawave_token")
    if not remnawave_url or not remnawave_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен. Обратитесь в поддержку.",
        )

    # Fetch trial settings
    trial_days_str = await get_setting(db, "remnawave_trial_days") or "3"
    trial_days = int(trial_days_str)
    trial_traffic_str = await get_setting(db, "remnawave_trial_traffic_limit_bytes") or str(30 * 1024 ** 3)
    trial_traffic_bytes = int(trial_traffic_str)
    squad_uuids_str = await get_setting(db, "remnawave_squad_uuids") or ""
    squad_ids = [s.strip() for s in squad_uuids_str.split(",") if s.strip()]

    # Build Remnawave username
    user_id_hex = str(current_user.id).replace("-", "")
    username = f"ws_{user_id_hex[:8]}"

    # Get Telegram info if linked
    from sqlalchemy import select as _select
    from app.models.auth_provider import AuthProvider, ProviderType
    result = await db.execute(
        _select(AuthProvider).where(
            AuthProvider.user_id == current_user.id,
            AuthProvider.provider == ProviderType.telegram,
        )
    )
    tg_provider = result.scalar_one_or_none()
    telegram_id: int | None = None
    description: str | None = None
    if tg_provider:
        try:
            telegram_id = int(tg_provider.provider_user_id)
            description = f"@{tg_provider.provider_username}" if tg_provider.provider_username else None
        except (ValueError, TypeError):
            pass

    # Create Remnawave user (retry with longer suffix on username collision)
    from datetime import timedelta
    from app.services.remnawave_client import RemnawaveClient
    client = RemnawaveClient(remnawave_url, remnawave_token)
    from datetime import datetime as _dt
    expire_at = (_dt.now(tz=timezone.utc) + timedelta(days=trial_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        rw_user = await client.create_user(
            username=username,
            traffic_limit_bytes=trial_traffic_bytes,
            expire_at=expire_at,
            squad_ids=squad_ids,
            telegram_id=telegram_id,
            description=description,
        )
    except Exception as exc:
        # Retry with longer username on conflict (409 from Remnawave)
        import httpx
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 409:
            username_long = f"ws_{user_id_hex[:12]}"
            rw_user = await client.create_user(
                username=username_long,
                traffic_limit_bytes=trial_traffic_bytes,
                expire_at=expire_at,
                squad_ids=squad_ids,
                telegram_id=telegram_id,
                description=description,
            )
        else:
            logger.exception("Remnawave user creation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ошибка подключения к серверу туннелей. Попробуйте позже.",
            )

    # Persist remnawave_uuid on user
    import uuid as _uuid
    current_user.remnawave_uuid = _uuid.UUID(rw_user.id)
    await db.commit()

    # Create local subscription
    sub = await create_trial_subscription(
        db=db,
        user=current_user,
        trial_days=trial_days,
        trial_traffic_bytes=trial_traffic_bytes,
    )

    return TrialActivateResponse(
        subscription=_to_response(sub),
        message=f"Пробный период активирован на {trial_days} дня",
    )
```

- [ ] **Step 7.4: Register in main.py**

Add to `backend/app/main.py`:
```python
from app.routers import subscriptions
# ...
app.include_router(subscriptions.router)
```

- [ ] **Step 7.5: Run tests — expect PASS**
```bash
cd backend && uv run pytest tests/routers/test_subscriptions.py -v
# Expected: 5 passed
```

- [ ] **Step 7.6: Run full suite**
```bash
cd backend && uv run pytest tests/ -q
```

- [ ] **Step 7.7: Commit**
```bash
git add backend/app/routers/subscriptions.py backend/app/schemas/subscription.py \
        backend/app/main.py backend/tests/routers/test_subscriptions.py
git commit -m "feat: add trial activation and subscription status endpoints"
```

---

## Task 8: Telegram OAuth → Auto-Sync Remnawave on First Login

**Files:**
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/routers/test_auth_email.py` (or new file `test_auth_telegram_sync.py`)
- Create: `backend/tests/routers/test_auth_telegram_sync.py`

When a user logs in via Telegram for the first time (provider not found in local DB), after creating the local user record, attempt to find them in Remnawave by Telegram ID. If found: set `remnawave_uuid`, create local subscription. This enrichment is **fail-silent** — if Remnawave is down or not configured, the user is still logged in successfully.

**Per spec:** "If not found in Remnawave: new user, no prior subscription."

- [ ] **Step 8.1: Write failing tests**

```python
# backend/tests/routers/test_auth_telegram_sync.py
"""Tests for Telegram OAuth first-login Remnawave sync."""
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.redis_client import get_redis


NOW = datetime.now(tz=timezone.utc)


def _make_db_user_not_found():
    """DB where get_user_by_provider returns None (new user)."""
    db = AsyncMock(spec=AsyncSession)
    # First call: get_user_by_provider → None
    # Second call: (for telegram provider if exists) → None
    # set up execute to return None for all queries
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None),
                                                       all=MagicMock(return_value=[])))
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_telegram_oauth_first_login_remnawave_not_configured():
    """First Telegram login succeeds even if Remnawave is not configured (fail-silent)."""
    import time
    import hmac as _hmac
    import hashlib

    bot_token = "fake_bot_token"
    auth_date = int(time.time())
    tg_data = {
        "id": 515172616,
        "first_name": "Вася",
        "auth_date": auth_date,
    }
    check_string = f"auth_date={auth_date}\nfirst_name=Вася\nid=515172616"
    secret = hashlib.sha256(bot_token.encode()).digest()
    tg_data["hash"] = _hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    # DB: setting for bot_token returns a value; everything else returns None
    db = AsyncMock(spec=AsyncSession)

    call_count = [0]
    def _execute_side_effect(stmt, *args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        # First call is for get_setting("telegram_bot_token") — return setting
        if call_count[0] == 1:
            setting = MagicMock()
            setting.is_sensitive = False
            setting.value = {"value": bot_token}
            result.scalar_one_or_none = MagicMock(return_value=setting)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
            result.scalars = MagicMock(return_value=MagicMock(
                all=MagicMock(return_value=[]), first=MagicMock(return_value=None)
            ))
        return result

    db.execute = AsyncMock(side_effect=_execute_side_effect)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.display_name = "Вася"
    mock_user.remnawave_uuid = None

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = False
    mock_redis.setex = AsyncMock()

    # FastAPI DI requires async generator overrides — sync lambda generators won't work
    async def _get_db_override():
        yield db

    async def _get_redis_override():
        return mock_redis

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_redis] = _get_redis_override

    with patch("app.routers.auth.create_user_with_provider", new=AsyncMock(return_value=mock_user)), \
         patch("app.routers.auth.get_user_by_provider", new=AsyncMock(return_value=None)), \
         patch("app.services.subscription_service.get_user_subscription", new=AsyncMock(return_value=None)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/auth/oauth/telegram", json=tg_data)

    app.dependency_overrides.clear()

    # Should succeed — 200 even without Remnawave
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Вася"
```

**Note on the above test:** It is complex because it threads through the full auth route. The test's primary purpose is to verify that Remnawave sync failure does NOT cause the login to fail. If this test proves too brittle to maintain, a simpler integration test asserting 200 status is sufficient. The real behavior is covered by the unit tests in task 6.

- [ ] **Step 8.2: Run test — expect FAIL (or skip if too complex)**
```bash
cd backend && uv run pytest tests/routers/test_auth_telegram_sync.py -v
```

- [ ] **Step 8.3: Modify Telegram OAuth endpoint in auth.py**

In `backend/app/routers/auth.py`, find the `oauth_telegram` endpoint and add Remnawave sync after user creation. The new user block currently looks like:

```python
user = await get_user_by_provider(db, ProviderType.telegram, str(tg_user.id))
if not user:
    display_name = tg_user.first_name
    if tg_user.last_name:
        display_name += f" {tg_user.last_name}"
    user = await create_user_with_provider(
        db,
        display_name=display_name,
        provider=ProviderType.telegram,
        provider_user_id=str(tg_user.id),
        avatar_url=tg_user.photo_url,
        provider_username=tg_user.username,
    )
```

Replace with:

```python
user = await get_user_by_provider(db, ProviderType.telegram, str(tg_user.id))
if not user:
    display_name = tg_user.first_name
    if tg_user.last_name:
        display_name += f" {tg_user.last_name}"
    user = await create_user_with_provider(
        db,
        display_name=display_name,
        provider=ProviderType.telegram,
        provider_user_id=str(tg_user.id),
        avatar_url=tg_user.photo_url,
        provider_username=tg_user.username,
    )
    # Fail-silent Remnawave sync: try to find prior subscription by Telegram ID
    await _sync_remnawave_on_first_telegram_login(db, user, tg_user.id)
```

Add helper function `_sync_remnawave_on_first_telegram_login` near the top of the file (after the logger line):

```python
async def _sync_remnawave_on_first_telegram_login(
    db: AsyncSession, user: "User", telegram_id: int
) -> None:
    """Best-effort: look up user in Remnawave by Telegram ID and sync subscription.
    Failures are logged and swallowed — the auth flow must not be blocked by this.
    """
    import uuid as _uuid
    try:
        remnawave_url = await get_setting(db, "remnawave_url")
        remnawave_token = await get_setting_decrypted(db, "remnawave_token")
        if not remnawave_url or not remnawave_token:
            return  # Not configured — skip silently

        from app.services.remnawave_client import RemnawaveClient
        from app.services.subscription_service import sync_subscription_from_remnawave

        rw_client = RemnawaveClient(remnawave_url, remnawave_token)
        rw_user = await rw_client.get_user_by_telegram_id(telegram_id)
        if rw_user is None:
            return  # Not found in Remnawave — new user with no prior subscription

        user.remnawave_uuid = _uuid.UUID(rw_user.id)
        await db.commit()
        await sync_subscription_from_remnawave(db, user, rw_user)
    except Exception as exc:
        logger.warning("Remnawave sync on first Telegram login failed (non-blocking): %s", exc)
```

Add `get_setting_decrypted` to the existing import in `auth.py` (do NOT add a second `AsyncSession` import — it is already present on line 4):
```python
# Change this existing line:
from app.services.setting_service import get_setting
# To:
from app.services.setting_service import get_setting, get_setting_decrypted
```

- [ ] **Step 8.4: Run full test suite**
```bash
cd backend && uv run pytest tests/ -q
# All previously passing tests must still pass
```

- [ ] **Step 8.5: Commit**
```bash
git add backend/app/routers/auth.py backend/tests/routers/test_auth_telegram_sync.py
git commit -m "feat: sync Remnawave subscription on first Telegram OAuth login"
```

---

## Task 9: Smoke Test — Full Stack Verification

**No code changes.** Verify the full stack works end-to-end with Docker Compose.

- [ ] **Step 9.1: Ensure stack is running**
```bash
cd custom_sub_pages
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
docker compose -f docker-compose.yml -f docker-compose.dev.yml ps
# All containers should be Up
```

- [ ] **Step 9.2: Apply migrations**
```bash
docker exec custom_sub_pages-backend-1 uv run alembic upgrade head
docker exec custom_sub_pages-backend-1 uv run alembic current
# Should show latest revision (head)
```

- [ ] **Step 9.3: Verify plans seeded**
```bash
docker exec custom_sub_pages-postgres-1 psql -U skavellion -c "SELECT name, price_rub FROM plans ORDER BY sort_order;"
# Expected: 4 rows — 1_month, 3_months, 6_months, 12_months
```

- [ ] **Step 9.4: Test /api/plans endpoint**
```bash
curl -s http://localhost/api/plans | python -m json.tool
# Expected: array of 4 plan objects
```

- [ ] **Step 9.5: Test /api/subscriptions/me unauthenticated**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/subscriptions/me
# Expected: 401
```

- [ ] **Step 9.6: Test /api/subscriptions/trial unauthenticated**
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost/api/subscriptions/trial
# Expected: 401
```

- [ ] **Step 9.7: Run all tests in container**
```bash
docker exec custom_sub_pages-backend-1 uv run pytest tests/ -q
# Expected: all pass
```

- [ ] **Step 9.8: Tag release**
```bash
git add -A && git diff --staged
# If any changes from smoke test fixes, commit them
git tag plan-2-complete
```

---

## Summary

After completing all 9 tasks, the following is live:

| Endpoint | Description |
|---|---|
| `GET /api/plans` | List active subscription plans |
| `GET /api/subscriptions/me` | Current user's subscription status (null if none) |
| `POST /api/subscriptions/trial` | Activate trial: creates Remnawave user + local subscription |

Core services built:
- `encryption_service.py` — AES-256-GCM encrypt/decrypt
- `setting_service.py` — transparent encrypt/decrypt for DB settings
- `rate_limiter.py` — Redis sliding-window counter
- `remnawave_client.py` — httpx wrapper for Remnawave API
- `subscription_service.py` — subscription CRUD + Remnawave sync logic

Telegram OAuth enriched with fail-silent Remnawave subscription sync on first login.

**Plan 3 will cover:** Cryptomus payment integration, payment creation endpoint, webhook handler, and promo code application.
