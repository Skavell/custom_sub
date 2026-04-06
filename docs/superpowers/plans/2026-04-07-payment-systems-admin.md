# Payment Systems Admin Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CryptoBot payment system settings section to the admin panel (enable/disable toggle + token/rate/IP fields), and add a payment provider selector to the subscription page with the pay button disabled when no providers are active.

**Architecture:** New `PaymentProviderInfo` schema + `_is_provider_active` helper in the backend factory; new `GET /api/payments/providers` endpoint for regular authenticated users; `CreatePaymentRequest` gets an optional `provider` field (defaults to `"cryptobot"` for backward compat). Frontend adds a `WebhookIPsSettingRow` component and a `CryptoBotBlock` to admin settings, and extends `SubscriptionPage` with a provider query, auto-sync state, and hard guard on submit.

**Tech Stack:** FastAPI + SQLAlchemy async, Pydantic v2, Alembic, pytest-asyncio / pytest-httpx; React 18, TanStack Query v5, TypeScript 5, Tailwind CSS 3

**Spec:** `docs/superpowers/specs/2026-04-07-payment-systems-admin-design.md`

---

## File Map

| File | Action |
|------|--------|
| `backend/app/schemas/payment.py` | Modify — add `PaymentProviderInfo`, add `provider` field to `CreatePaymentRequest` |
| `backend/app/services/payment_providers/factory.py` | Modify — add `_KNOWN_PROVIDERS`, `_PROVIDER_LABELS`, `_is_provider_active`, update `get_active_provider` signature |
| `backend/app/routers/payments.py` | Modify — add `GET /api/payments/providers`, pass `data.provider` to factory |
| `backend/alembic/versions/f6a7b8c9d0e1_seed_cryptobot_enabled.py` | Create — seed `cryptobot_enabled = "true"` |
| `backend/tests/routers/test_payments_providers.py` | Create — tests for the new endpoint |
| `backend/tests/routers/test_payments_create.py` | Modify — add tests for `provider` field handling |
| `frontend/src/types/api.ts` | Modify — add `PaymentProviderInfo`, add `provider` to `CreatePaymentRequest` |
| `frontend/src/pages/admin/AdminSettingsPage.tsx` | Modify — add `PAYMENT_KEYS`, `WebhookIPsSettingRow`, `CryptoBotBlock`, new section |
| `frontend/src/pages/SubscriptionPage.tsx` | Modify — provider query, selector, disabled state, hard guard |

---

## Task 1: Add `PaymentProviderInfo` schema and `provider` field to `CreatePaymentRequest`

**Files:**
- Modify: `backend/app/schemas/payment.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/schemas/test_payment_schemas.py`:

```python
from app.schemas.payment import PaymentProviderInfo, CreatePaymentRequest


def test_payment_provider_info_schema():
    info = PaymentProviderInfo(name="cryptobot", label="CryptoBot", is_active=True)
    assert info.name == "cryptobot"
    assert info.label == "CryptoBot"
    assert info.is_active is True


def test_create_payment_request_provider_defaults_to_cryptobot():
    req = CreatePaymentRequest(plan_id="00000000-0000-0000-0000-000000000001")
    assert req.provider == "cryptobot"


def test_create_payment_request_provider_explicit():
    req = CreatePaymentRequest(
        plan_id="00000000-0000-0000-0000-000000000001",
        provider="some_provider",
    )
    assert req.provider == "some_provider"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && uv run pytest tests/schemas/test_payment_schemas.py -v
```

Expected: `ImportError` or `AttributeError` — `PaymentProviderInfo` does not exist yet.

- [ ] **Step 3: Implement in `backend/app/schemas/payment.py`**

Add to the end of the existing imports/classes:

```python
class PaymentProviderInfo(BaseModel):
    name: str
    label: str
    is_active: bool


class CreatePaymentRequest(BaseModel):
    plan_id: uuid.UUID
    promo_code: str | None = None
    provider: str = "cryptobot"
```

**Note:** This replaces the existing `CreatePaymentRequest` class (currently has no `provider` field). The new definition is fully backward-compatible — old callers that omit `provider` get `"cryptobot"` by default.

- [ ] **Step 4: Run to confirm passing**

```bash
cd backend && uv run pytest tests/schemas/test_payment_schemas.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/payment.py backend/tests/schemas/test_payment_schemas.py
git commit -m "feat: add PaymentProviderInfo schema and provider field to CreatePaymentRequest"
```

---

## Task 2: Update `factory.py` — registry, `_is_provider_active`, new `get_active_provider` signature

**Files:**
- Modify: `backend/app/services/payment_providers/factory.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_payment_factory.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.services.payment_providers.factory import get_active_provider, _is_provider_active


@pytest.mark.asyncio
async def test_is_provider_active_returns_true_when_enabled_and_token_set():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true") as mock_get,
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is True


@pytest.mark.asyncio
async def test_is_provider_active_returns_false_when_disabled():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="false"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is False


@pytest.mark.asyncio
async def test_is_provider_active_returns_false_when_token_missing():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value=None),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is False


@pytest.mark.asyncio
async def test_is_provider_active_returns_false_when_setting_absent():
    """Absent setting treated as 'false' (strict == 'true' check)."""
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value=None),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        result = await _is_provider_active(db, "cryptobot")
    assert result is False


@pytest.mark.asyncio
async def test_get_active_provider_unknown_raises_400():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_active_provider(db, "nonexistent")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_active_provider_disabled_raises_400():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="false"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="tok"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_active_provider(db, "cryptobot")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_active_provider_no_token_raises_503():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value=None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_active_provider(db, "cryptobot")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_active_provider_returns_cryptobot_provider():
    db = AsyncMock()
    with (
        patch("app.services.payment_providers.factory.get_setting", side_effect=lambda db, key: "true" if key == "cryptobot_enabled" else "83"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="mytoken"),
    ):
        provider = await get_active_provider(db, "cryptobot")
    assert provider.name == "cryptobot"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && uv run pytest tests/services/test_payment_factory.py -v
```

Expected: `ImportError` — `_is_provider_active` does not exist yet.

- [ ] **Step 3: Rewrite `backend/app/services/payment_providers/factory.py`**

```python
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment_providers.base import PaymentProvider
from app.services.payment_providers.cryptobot import CryptoBotProvider
from app.services.setting_service import get_setting, get_setting_decrypted

# ─── Provider registry ────────────────────────────────────────────────────────

_KNOWN_PROVIDERS: list[str] = ["cryptobot"]

_PROVIDER_LABELS: dict[str, str] = {
    "cryptobot": "CryptoBot",
}


async def _is_provider_active(db: AsyncSession, name: str) -> bool:
    """Returns True iff the provider is enabled (== "true") AND has a token set.
    Both disabled and missing-token states return False — both mean "can't pay".
    Uses strict equality (== "true"), NOT the frontend OAuthToggle convention (!= "false").
    """
    if name == "cryptobot":
        enabled = await get_setting(db, "cryptobot_enabled")
        if enabled != "true":
            return False
        token = await get_setting_decrypted(db, "cryptobot_token")
        return bool(token)
    return False


async def get_active_provider(db: AsyncSession, provider_name: str) -> PaymentProvider:
    """Return the configured payment provider by name.

    Raises:
        HTTP 400 — provider name is unknown or provider is disabled
        HTTP 503 — provider is enabled but token is missing/misconfigured
    """
    if provider_name not in _KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неизвестная платёжная система",
        )

    if provider_name == "cryptobot":
        enabled = await get_setting(db, "cryptobot_enabled")
        if enabled != "true":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Платёжная система отключена",
            )
        token = await get_setting_decrypted(db, "cryptobot_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Платёжная система не настроена. Обратитесь в поддержку.",
            )
        rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
        try:
            rate = float(rate_str)
            if rate <= 0:
                rate = 83.0
        except ValueError:
            rate = 83.0
        return CryptoBotProvider(token=token, usdt_rate=rate)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Платёжная система не настроена. Обратитесь в поддержку.",
    )
```

- [ ] **Step 4: Run to confirm passing**

```bash
cd backend && uv run pytest tests/services/test_payment_factory.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Run full backend test suite to catch regressions**

```bash
cd backend && uv run pytest -x -q
```

Expected: all tests pass (existing tests that call `get_active_provider` will fail — fix in Task 3).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/payment_providers/factory.py backend/tests/services/test_payment_factory.py
git commit -m "feat: add provider registry and _is_provider_active to payment factory"
```

---

## Task 3: Update `payments.py` router — `/providers` endpoint + pass `provider` to factory

**Files:**
- Modify: `backend/app/routers/payments.py`
- Create: `backend/tests/routers/test_payments_providers.py`
- Modify: `backend/tests/routers/test_payments_create.py`

- [ ] **Step 1: Write tests for the new `/providers` endpoint**

Create `backend/tests/routers/test_payments_providers.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from unittest.mock import MagicMock


def _make_user():
    u = MagicMock(spec=User)
    u.id = None
    return u


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


@pytest.mark.asyncio
async def test_get_providers_returns_cryptobot_active():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_current_user] = _override_user(_make_user())

    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="true"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="tok"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/payments/providers")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "cryptobot"
    assert data[0]["label"] == "CryptoBot"
    assert data[0]["is_active"] is True


@pytest.mark.asyncio
async def test_get_providers_returns_cryptobot_inactive_when_disabled():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_current_user] = _override_user(_make_user())

    with (
        patch("app.services.payment_providers.factory.get_setting", return_value="false"),
        patch("app.services.payment_providers.factory.get_setting_decrypted", return_value="tok"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/payments/providers")

    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["is_active"] is False


@pytest.mark.asyncio
async def test_get_providers_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/payments/providers")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && uv run pytest tests/routers/test_payments_providers.py -v
```

Expected: 404 (endpoint doesn't exist yet) or auth errors.

- [ ] **Step 3: Add imports and `/providers` endpoint to `payments.py`**

At the top of `backend/app/routers/payments.py`, find and replace the two existing import lines for `payment` schemas and `factory`:

```python
# Before:
from app.schemas.payment import CreatePaymentRequest, PaymentResponse, TransactionHistoryItem
from app.services.payment_providers.factory import get_active_provider

# After:
from app.schemas.payment import CreatePaymentRequest, PaymentResponse, TransactionHistoryItem, PaymentProviderInfo
from app.services.payment_providers.factory import (
    get_active_provider, _KNOWN_PROVIDERS, _PROVIDER_LABELS, _is_provider_active
)
```

These private names are imported here intentionally — `_KNOWN_PROVIDERS`, `_PROVIDER_LABELS`, `_is_provider_active` are used only by the `/providers` endpoint in this module.

Add the new endpoint after the `router` definition line (before `_create_transaction`):

```python
@router.get("/providers", response_model=list[PaymentProviderInfo])
async def get_payment_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentProviderInfo]:
    """Returns all known payment providers with their active status.
    Available to any authenticated user (non-admin). Used by SubscriptionPage.
    """
    result = []
    for name in _KNOWN_PROVIDERS:
        result.append(PaymentProviderInfo(
            name=name,
            label=_PROVIDER_LABELS[name],
            is_active=await _is_provider_active(db, name),
        ))
    return result
```

- [ ] **Step 4: Update `create_payment` to pass `data.provider` to factory**

In `create_payment` (line ~97), find the **only** call site of `get_active_provider`:
```python
provider = await get_active_provider(db)
```
Replace with:
```python
provider = await get_active_provider(db, data.provider)
```

**Note:** This is the only call site in `payments.py` that uses `get_active_provider`. The webhook handler constructs `CryptoBotProvider` directly and does not call `get_active_provider` — no other changes needed.

- [ ] **Step 5: Add test for `provider` field in `test_payments_create.py`**

Open `backend/tests/routers/test_payments_create.py`, find the existing test `test_create_payment_no_trial_returns_409` and read the pattern. Add a new test at the end of that file:

```python
@pytest.mark.asyncio
async def test_create_payment_unknown_provider_returns_400():
    """provider field is validated — unknown names get HTTP 400."""
    user = _make_user(remnawave_uuid=str(uuid.uuid4()))
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)

    app.dependency_overrides[get_db] = _override_db(mock_db)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_redis] = _override_redis(mock_redis)

    # Mock DB to return a valid plan
    from app.models.plan import Plan
    mock_plan = _make_plan()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_plan)
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.routers.payments.check_rate_limit", return_value=True), \
         patch("app.routers.payments.get_pending_transaction", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/payments", json={
                "plan_id": str(PLAN_ID),
                "provider": "nonexistent_provider",
            })

    app.dependency_overrides.clear()
    assert resp.status_code == 400
```

- [ ] **Step 6: Run all payment tests**

```bash
cd backend && uv run pytest tests/routers/test_payments_providers.py tests/routers/test_payments_create.py -v
```

Expected: all PASS.

- [ ] **Step 7: Run full test suite**

```bash
cd backend && uv run pytest -x -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/payments.py backend/tests/routers/test_payments_providers.py backend/tests/routers/test_payments_create.py
git commit -m "feat: add GET /api/payments/providers endpoint and pass provider to factory"
```

---

## Task 4: Alembic migration — seed `cryptobot_enabled`

**Files:**
- Create: `backend/alembic/versions/f6a7b8c9d0e1_seed_cryptobot_enabled.py`

- [ ] **Step 1: Create the migration file**

```python
"""seed cryptobot_enabled setting

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-07 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
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
        {"key": "cryptobot_enabled", "value": json.dumps({"value": "true"}), "is_sensitive": False},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = 'cryptobot_enabled'"),
    )
```

- [ ] **Step 2: Verify migration chain**

```bash
cd backend && uv run alembic heads
```

Expected: `e5f6a7b8c9d0 (head)` — the new migration extends this.

- [ ] **Step 3: Run migration check (dry run)**

```bash
cd backend && uv run alembic check
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/f6a7b8c9d0e1_seed_cryptobot_enabled.py
git commit -m "feat: add migration to seed cryptobot_enabled setting"
```

---

## Task 5: Frontend types — add `PaymentProviderInfo`, update `CreatePaymentRequest`

**Files:**
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add `PaymentProviderInfo` type**

In `frontend/src/types/api.ts`, at the end of the file, add:

```ts
export interface PaymentProviderInfo {
  name: string
  label: string
  is_active: boolean
}
```

- [ ] **Step 2: Update `CreatePaymentRequest` to include `provider`**

Find the existing interface (around line 118):
```ts
export interface CreatePaymentRequest {
  plan_id: string
  promo_code?: string | null
}
```

Replace with:
```ts
export interface CreatePaymentRequest {
  plan_id: string
  promo_code?: string | null
  provider: string
}
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run type-check
```

Expected: 0 errors (the `provider` field is now required on `CreatePaymentRequest` — Step 6 of Task 6 will fix usages in `SubscriptionPage`).

**If type-check fails** with "Property 'provider' is missing": that's expected — it will be fixed in Task 6. Skip this check for now and come back after Task 6.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat: add PaymentProviderInfo type and provider field to CreatePaymentRequest"
```

---

## Task 6: Update `SubscriptionPage.tsx` — provider query, selector, disabled state, hard guard

**Files:**
- Modify: `frontend/src/pages/SubscriptionPage.tsx`

- [ ] **Step 1: Add imports**

At the top of `SubscriptionPage.tsx`, update imports:

```ts
import { useState, useEffect } from 'react'   // add useEffect
```

And in the type imports:
```ts
import type {
  Plan,
  ValidatePromoResponse,
  PaymentResponse,
  ApplyPromoRequest,
  ApplyPromoResponse,
  CreatePaymentRequest,
  OAuthConfigResponse,
  PaymentProviderInfo,   // add this
} from '@/types/api'
```

- [ ] **Step 2: Add provider query and state**

Inside `SubscriptionPage`, after the existing `useQuery` for `oauthConfig`, add:

```ts
const { data: providers = [], isLoading: providersLoading, isError: providersError } = useQuery<PaymentProviderInfo[]>({
  queryKey: ['payment-providers'],
  queryFn: () => api.get<PaymentProviderInfo[]>('/api/payments/providers'),
})

const [selectedProvider, setSelectedProvider] = useState<string | null>(null)

const activeProviders = providers.filter(p => p.is_active)

// Sync selectedProvider when providers list changes.
// Only resets if no selection yet, or current selection no longer active.
// Preserves user's manual choice on background refetches.
useEffect(() => {
  const stillValid = selectedProvider !== null && activeProviders.some(p => p.name === selectedProvider)
  if (!stillValid) {
    setSelectedProvider(activeProviders[0]?.name ?? null)
  }
}, [providers]) // eslint-disable-line react-hooks/exhaustive-deps
```

- [ ] **Step 3: Update `handlePay` — add provider field and hard guard**

Replace existing `handlePay`:

```ts
function handlePay() {
  if (!selectedPlanId) return
  if (!selectedProvider) return  // hard guard — button should already be disabled
  payMutation.mutate({
    plan_id: selectedPlanId,
    promo_code: validatedPromo?.code ?? null,
    provider: selectedProvider,
  })
}
```

- [ ] **Step 4: Determine pay button disabled state**

Find the existing pay button disabled condition:
```ts
disabled={payMutation.isPending || showVerifyBanner}
```

Replace with:
```ts
disabled={payMutation.isPending || showVerifyBanner || providersLoading || providersError || activeProviders.length === 0 || !selectedProvider}
```

- [ ] **Step 5: Add provider selector and disabled message above the pay button**

Inside the "Order summary + pay" block, just before `{payMutation.isError && ...}`, add:

```tsx
{/* Provider selector */}
{providersError && (
  <p className="mb-3 text-xs text-red-400">Не удалось загрузить платёжные системы</p>
)}
{!providersLoading && !providersError && activeProviders.length === 0 && (
  <p className="mb-3 text-xs text-text-muted">Оплата временно недоступна</p>
)}
{!providersLoading && !providersError && activeProviders.length >= 2 && (
  <div className="mb-3">
    <label className="block text-xs text-text-muted mb-1">Способ оплаты</label>
    <select
      value={selectedProvider ?? ''}
      onChange={(e) => setSelectedProvider(e.target.value)}
      className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
    >
      {activeProviders.map(p => (
        <option key={p.name} value={p.name}>{p.label}</option>
      ))}
    </select>
  </div>
)}
```

- [ ] **Step 6: Update pay button label**

The current button shows "Оплатить криптовалютой" hardcoded. Since the provider is now dynamic, make the label reflect the selected provider:

Find:
```tsx
'Оплатить криптовалютой'
```

Replace with:
```tsx
activeProviders.length === 0 ? 'Оплата недоступна' : `Оплатить через ${activeProviders.find(p => p.name === selectedProvider)?.label ?? 'CryptoBot'}`
```

- [ ] **Step 7: Type-check**

```bash
cd frontend && npm run type-check
```

Expected: 0 errors.

- [ ] **Step 8: Build**

```bash
cd frontend && npm run build
```

Expected: successful build, no TypeScript errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/SubscriptionPage.tsx
git commit -m "feat: add payment provider selector and disabled state to SubscriptionPage"
```

---

## Task 7: Update `AdminSettingsPage.tsx` — `PAYMENT_KEYS`, `WebhookIPsSettingRow`, `CryptoBotBlock`, new section

**Files:**
- Modify: `frontend/src/pages/admin/AdminSettingsPage.tsx`

### Step 1-3: Add `PAYMENT_KEYS` constant and exclude from `otherSettings`

- [ ] **Step 1: Add `PAYMENT_KEYS` constant**

In `AdminSettingsPage.tsx`, after the existing constant definitions (around line 34), add:

```ts
const PAYMENT_KEYS = new Set([
  'cryptobot_enabled',
  'cryptobot_token',
  'usdt_exchange_rate',
  'cryptobot_webhook_allowed_ips',
])
```

- [ ] **Step 2: Update `otherSettings` filter to exclude `PAYMENT_KEYS`**

Find the `otherSettings` declaration (around line 507):
```ts
const otherSettings = settings.filter(
  s =>
    !REMNAWAVE_KEYS.has(s.key) &&
    !TRIAL_KEYS.has(s.key) &&
    !EMAIL_SERVICE_KEYS.has(s.key) &&
    !REGISTRATION_KEYS.has(s.key) &&
    !OAUTH_KEYS.has(s.key) &&
    !s.key.startsWith(INSTALL_KEY_PREFIX),
)
```

Add `!PAYMENT_KEYS.has(s.key) &&` to the filter:
```ts
const otherSettings = settings.filter(
  s =>
    !REMNAWAVE_KEYS.has(s.key) &&
    !TRIAL_KEYS.has(s.key) &&
    !EMAIL_SERVICE_KEYS.has(s.key) &&
    !REGISTRATION_KEYS.has(s.key) &&
    !OAUTH_KEYS.has(s.key) &&
    !PAYMENT_KEYS.has(s.key) &&
    !s.key.startsWith(INSTALL_KEY_PREFIX),
)
```

- [ ] **Step 3: Add labels and hints for payment keys**

In `SETTING_LABELS`, add:
```ts
  cryptobot_token: 'API токен CryptoBot',
  usdt_exchange_rate: 'Курс USDT (руб.)',
  cryptobot_webhook_allowed_ips: 'Разрешённые IP вебхуков',
```

In `SETTING_HINTS`, add:
```ts
  usdt_exchange_rate: 'Число, например 90.5',
  cryptobot_webhook_allowed_ips: 'Один IP на строку. Если пусто — разрешены все IP.',
```

### Step 4-6: Add `WebhookIPsSettingRow` component

- [ ] **Step 4: Add `WebhookIPsSettingRow` component**

Add after the `NumberBytesSettingRow` component (around line 309), before `OAuthField`:

```tsx
// ─── Webhook IPs setting row ──────────────────────────────────────────────────
// Stores as JSON array string (e.g. '["1.2.3.4"]') to match backend json.loads() parsing.

function loadWebhookIPs(raw: string | null): string {
  if (!raw || raw.trim() === '') return ''
  try { return (JSON.parse(raw) as string[]).join('\n') }
  catch { return raw }  // graceful fallback for legacy non-JSON data
}

function saveWebhookIPs(text: string): string {
  return JSON.stringify(text.split('\n').map(s => s.trim()).filter(Boolean))
}

function WebhookIPsSettingRow({ setting, label, hint }: { setting: SettingAdminItem; label: string; hint?: string }) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState(() => loadWebhookIPs(setting.value))
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put(`/api/admin/settings/${setting.key}`, { value: v, is_sensitive: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setSaved(true)
      setSaveError(null)
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (e) => setSaveError(e instanceof ApiError ? e.detail : 'Ошибка'),
  })

  return (
    <div className="rounded-input bg-surface border border-border-neutral px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary">{label}</p>
          {hint && <p className="text-xs text-text-muted mt-0.5">{hint}</p>}
        </div>
        <button
          onClick={() => mutation.mutate(saveWebhookIPs(value))}
          disabled={mutation.isPending}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-input text-xs font-medium transition-colors ${
            saved ? 'bg-green-500/20 text-green-400' : 'bg-accent/10 text-accent hover:bg-accent/20'
          } disabled:opacity-50`}
        >
          <Save size={13} />
          {saved ? 'Сохранено' : 'Сохранить'}
        </button>
      </div>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={4}
        placeholder={"1.2.3.4\n5.6.7.8"}
        className="w-full rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono resize-none"
      />
      {saveError && <p className="text-xs text-red-400">{saveError}</p>}
    </div>
  )
}
```

### Step 5-7: Add `CryptoBotEnabledToggle` and `CryptoBotBlock`

- [ ] **Step 5: Add `CryptoBotEnabledToggle` component**

Add after `OAuthToggle` (around line 404), before `CollapsibleSection`:

```tsx
// ─── CryptoBotEnabledToggle ───────────────────────────────────────────────────
// Like OAuthToggle but uses strict === "true" semantics (not !== "false").
// This matches the backend factory._is_provider_active check.

function CryptoBotEnabledToggle({ label, settings }: { label: string; settings: SettingAdminItem[] }) {
  const queryClient = useQueryClient()
  const existing = settings.find(s => s.key === 'cryptobot_enabled')
  const enabled = existing?.value === 'true'

  const mutation = useMutation({
    mutationFn: (v: string) =>
      api.put('/api/admin/settings/cryptobot_enabled', { value: v, is_sensitive: false }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-settings'] }),
  })

  return (
    <button
      onClick={() => mutation.mutate(enabled ? 'false' : 'true')}
      disabled={mutation.isPending}
      className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
    >
      {enabled
        ? <ToggleRight size={20} className="text-accent" />
        : <ToggleLeft size={20} className="text-text-muted" />
      }
      {label}
    </button>
  )
}
```

- [ ] **Step 6: Add `CryptoBotBlock` component**

Add after `CryptoBotEnabledToggle`, before `CollapsibleSection`:

```tsx
// ─── CryptoBotBlock ───────────────────────────────────────────────────────────

function CryptoBotBlock({ settings }: { settings: SettingAdminItem[] }) {
  const [open, setOpen] = useState(false)

  const tokenSetting = settings.find(s => s.key === 'cryptobot_token')
  const rateSetting = settings.find(s => s.key === 'usdt_exchange_rate')
  const ipsSetting = settings.find(s => s.key === 'cryptobot_webhook_allowed_ips')

  const placeholder: SettingAdminItem = { key: '', value: null, is_sensitive: false, updated_at: '' }

  return (
    <div className="rounded-input border border-border-neutral overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-white/3">
        <CryptoBotEnabledToggle label="CryptoBot" settings={settings} />
        <button
          onClick={() => setOpen(v => !v)}
          className="text-text-muted hover:text-text-primary transition-colors"
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
      {open && (
        <div className="px-4 py-3 border-t border-border-neutral space-y-3">
          <OAuthField
            label="API токен CryptoBot"
            settingKey="cryptobot_token"
            sensitive
            placeholder="1234567890:AAF..."
            settings={settings}
          />
          <OAuthField
            label="Курс USDT (руб.)"
            settingKey="usdt_exchange_rate"
            placeholder="90.5"
            settings={settings}
          />
          <WebhookIPsSettingRow
            setting={ipsSetting ?? { ...placeholder, key: 'cryptobot_webhook_allowed_ips' }}
            label="Разрешённые IP вебхуков"
            hint="Один IP на строку. Если пусто — разрешены все IP."
          />
        </div>
      )}
    </div>
  )
}
```

### Step 7: Add the "Платёжные системы" section to the page

- [ ] **Step 7: Add section in the JSX**

In the `return` of `AdminSettingsPage`, find the `{/* OAuth провайдеры */}` section comment and add the payments section **before** it:

```tsx
{/* Платёжные системы */}
<CollapsibleSection title="Платёжные системы">
  <CryptoBotBlock settings={allSettings} />
</CollapsibleSection>

{/* OAuth провайдеры */}
```

- [ ] **Step 8: Type-check**

```bash
cd frontend && npm run type-check
```

Expected: 0 errors.

- [ ] **Step 9: Build**

```bash
cd frontend && npm run build
```

Expected: successful build.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/admin/AdminSettingsPage.tsx
git commit -m "feat: add payment systems section to admin settings page"
```

---

## Task 8: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && uv run pytest -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend build and type-check**

```bash
cd frontend && npm run type-check && npm run build
```

Expected: 0 TypeScript errors, successful build.

- [ ] **Step 3: Verify migration chain**

```bash
cd backend && uv run alembic history --verbose | head -20
```

Expected: `f6a7b8c9d0e1` listed as head revision, `e5f6a7b8c9d0` as its parent.

- [ ] **Step 4: Final commit if any loose files**

```bash
git status
```

If clean: done. If loose files remain, add and commit.
