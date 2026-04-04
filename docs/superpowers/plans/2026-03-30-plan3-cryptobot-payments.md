# Plan 3: CryptoBot Payment Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement CryptoBot cryptocurrency payment processing with a clean provider abstraction, subscription extension on successful payment, and Telegram admin alerts.

**Architecture:** Clean `PaymentProvider` ABC lives in `app/services/payment_providers/`. `CryptoBotProvider` implements it. A factory function reads DB settings and returns the active provider. The payments router uses the provider interface, so adding a new payment method in future = one new class + DB settings. All state mutations on payment completion are a single atomic `db.commit()`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, httpx, pytest-asyncio, pytest-httpx ≥0.36, Redis, Alembic

---

## Existing Codebase Orientation

```
backend/app/
  config.py                     — Settings(BaseSettings); add site_url field
  models/transaction.py         — Transaction; needs payment_url column (migration)
  models/subscription.py        — Subscription; SubscriptionType, SubscriptionStatus
  models/promo_code.py          — PromoCode, PromoCodeUsage
  models/user.py                — User; has_made_payment, remnawave_uuid
  models/plan.py                — Plan; name, duration_days, price_rub, new_user_price_rub
  services/remnawave_client.py  — RemnawaveClient; get_user, update_user
  services/setting_service.py   — get_setting, get_setting_decrypted
  services/rate_limiter.py      — check_rate_limit(redis, key, limit, window_sec) → bool
  redis_client.py               — get_redis() → Redis
  deps.py                       — get_current_user → User
  database.py                   — get_db → AsyncSession
  main.py                       — include routers here
```

Key existing patterns:
- Routers use `Depends(get_db)`, `Depends(get_current_user)`, `Depends(get_redis)`
- Sensitive settings stored AES-encrypted, read via `get_setting_decrypted(db, key)`
- Plain settings read via `get_setting(db, key)` → `str | None`
- After `await db.commit()` always call `await db.refresh(obj)` if you need attributes

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/services/payment_providers/__init__.py` | Create | Package marker (empty) |
| `app/services/payment_providers/base.py` | Create | `PaymentProvider` ABC + `InvoiceResult` dataclass |
| `app/services/payment_providers/cryptobot.py` | Create | `CryptoBotProvider` — CryptoBot API + webhook verification |
| `app/services/payment_providers/factory.py` | Create | `get_active_provider(db)` — reads settings, returns provider |
| `app/services/telegram_alert.py` | Create | `send_admin_alert(token, chat_id, message)` |
| `app/services/payment_service.py` | Create | `calculate_final_price`, `get_pending_transaction`, `complete_payment` |
| `app/schemas/payment.py` | Create | `CreatePaymentRequest`, `PaymentResponse`, `TransactionHistoryItem`, `CryptoBotWebhookPayload` |
| `app/routers/payments.py` | Create | `POST /api/payments`, `POST /api/payments/webhook`, `GET /api/payments/history` |
| `app/config.py` | Modify | Add `site_url: str = "http://localhost"` field |
| `app/main.py` | Modify | `app.include_router(payments.router)` |
| `alembic/versions/*_add_payment_url_to_transactions.py` | Create | `ALTER TABLE transactions ADD COLUMN payment_url VARCHAR(2048)` |
| `alembic/versions/*_seed_usdt_rate.py` | Create | Insert `usdt_exchange_rate = "83"` into settings |
| `tests/services/test_cryptobot_provider.py` | Create | Provider unit tests |
| `tests/services/test_telegram_alert.py` | Create | Alert service tests |
| `tests/services/test_payment_service.py` | Create | Price calc + pending dedup tests |
| `tests/routers/test_payments_create.py` | Create | `POST /api/payments` tests |
| `tests/routers/test_payments_webhook.py` | Create | `POST /api/payments/webhook` tests |

---

## Task 1: Provider Abstraction + CryptoBot Client + DB Migration

**Files:**
- Create: `backend/app/services/payment_providers/__init__.py`
- Create: `backend/app/services/payment_providers/base.py`
- Create: `backend/app/services/payment_providers/cryptobot.py`
- Create: `backend/app/services/payment_providers/factory.py`
- Create: `backend/alembic/versions/<hash>_add_payment_url_to_transactions.py`
- Create: `backend/tests/services/test_cryptobot_provider.py`

- [ ] **Step 1.1: Write failing tests**

```python
# backend/tests/services/test_cryptobot_provider.py
import hashlib
import hmac
import json
import pytest
from pytest_httpx import HTTPXMock

from app.services.payment_providers.cryptobot import CryptoBotProvider


TOKEN = "test-token-123"
RATE = 83.0


@pytest.mark.asyncio
async def test_create_invoice_returns_invoice_result(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        json={
            "ok": True,
            "result": {
                "invoice_id": 12345,
                "bot_invoice_url": "https://t.me/CryptoBot?start=IVtest",
                "status": "active",
                "asset": "USDT",
                "amount": "2.41",
            },
        },
        status_code=200,
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    result = await provider.create_invoice(
        amount_rub=200,
        order_id="some-uuid",
        description="1 месяц",
    )
    assert result.payment_url == "https://t.me/CryptoBot?start=IVtest"
    assert result.external_id == "12345"


@pytest.mark.asyncio
async def test_create_invoice_sends_correct_amount(httpx_mock: HTTPXMock):
    """200 RUB / 83 RUB per USDT = 2.41 USDT."""
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        json={"ok": True, "result": {"invoice_id": 1, "bot_invoice_url": "t.me/x", "status": "active", "asset": "USDT", "amount": "2.41"}},
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    await provider.create_invoice(amount_rub=200, order_id="x", description="test")
    request = httpx_mock.get_request()
    body = json.loads(request.content)
    assert body["amount"] == "2.41"
    assert body["asset"] == "USDT"
    assert body["payload"] == "x"
    assert request.headers["Crypto-Pay-API-Token"] == TOKEN


@pytest.mark.asyncio
async def test_create_invoice_http_error_raises(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://pay.crypt.bot/api/createInvoice",
        status_code=500,
    )
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    with pytest.raises(Exception):
        await provider.create_invoice(amount_rub=200, order_id="x", description="test")


def test_verify_webhook_valid():
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    raw_body = b'{"update_type":"invoice_paid"}'
    secret = hashlib.sha256(TOKEN.encode()).digest()
    sig = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    assert provider.verify_webhook(raw_body, {"crypto-pay-api-signature": sig}) is True


def test_verify_webhook_invalid_signature():
    provider = CryptoBotProvider(token=TOKEN, usdt_rate=RATE)
    raw_body = b'{"update_type":"invoice_paid"}'
    assert provider.verify_webhook(raw_body, {"crypto-pay-api-signature": "deadbeef"}) is False
```

- [ ] **Step 1.2: Run tests — expect FAIL (ImportError)**

```bash
cd backend && uv run pytest tests/services/test_cryptobot_provider.py -v
# Expected: ImportError or ModuleNotFoundError
```

- [ ] **Step 1.3: Create package and base**

```python
# backend/app/services/payment_providers/__init__.py
# (empty)
```

```python
# backend/app/services/payment_providers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class InvoiceResult:
    payment_url: str   # Link shown to user (t.me/CryptoBot?start=IV...)
    external_id: str   # Provider's invoice ID → transaction.external_payment_id


class PaymentProvider(ABC):
    @abstractmethod
    async def create_invoice(
        self,
        amount_rub: int,
        order_id: str,
        description: str,
    ) -> InvoiceResult: ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

- [ ] **Step 1.4: Implement CryptoBotProvider**

```python
# backend/app/services/payment_providers/cryptobot.py
from __future__ import annotations
import hashlib
import hmac as _hmac
import logging

import httpx

from app.services.payment_providers.base import InvoiceResult, PaymentProvider

logger = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(10.0)


class CryptoBotProvider(PaymentProvider):
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str, usdt_rate: float) -> None:
        self._token = token
        self._rate = usdt_rate

    @property
    def name(self) -> str:
        return "cryptobot"

    async def create_invoice(
        self, amount_rub: int, order_id: str, description: str
    ) -> InvoiceResult:
        usdt_amount = str(round(amount_rub / self._rate, 2))
        body = {
            "asset": "USDT",
            "amount": usdt_amount,
            "description": description,
            "payload": order_id,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            resp = await http.post(
                f"{self.BASE_URL}/createInvoice",
                json=body,
                headers={"Crypto-Pay-API-Token": self._token},
            )
            resp.raise_for_status()
            data = resp.json()
        result = data["result"]
        return InvoiceResult(
            payment_url=result["bot_invoice_url"],
            external_id=str(result["invoice_id"]),
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        secret = hashlib.sha256(self._token.encode()).digest()
        signature = headers.get("crypto-pay-api-signature", "")
        expected = _hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected.lower(), signature.lower())
```

- [ ] **Step 1.5: Implement factory**

```python
# backend/app/services/payment_providers/factory.py
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment_providers.base import PaymentProvider
from app.services.payment_providers.cryptobot import CryptoBotProvider
from app.services.setting_service import get_setting, get_setting_decrypted


async def get_active_provider(db: AsyncSession) -> PaymentProvider:
    """Read settings and return the configured payment provider.
    Raises HTTP 503 if no provider is configured.
    """
    token = await get_setting_decrypted(db, "cryptobot_token")
    if token:
        rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
        try:
            rate = float(rate_str)
        except ValueError:
            rate = 83.0
        return CryptoBotProvider(token=token, usdt_rate=rate)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Платёжная система не настроена. Обратитесь в поддержку.",
    )
```

- [ ] **Step 1.6: Create Alembic migration for payment_url column**

```bash
cd backend && uv run alembic revision -m "add_payment_url_to_transactions"
```

Fill the generated file:

```python
# backend/alembic/versions/<hash>_add_payment_url_to_transactions.py
"""add_payment_url_to_transactions

Revision ID: <auto>
Revises: f989da77bf10
Create Date: <auto>
"""
from alembic import op
import sqlalchemy as sa

revision = "<auto>"
down_revision = "f989da77bf10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("payment_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "payment_url")
```

- [ ] **Step 1.7: Add payment_url to Transaction model**

In `backend/app/models/transaction.py`, add after the `external_payment_id` field:
```python
payment_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
```

- [ ] **Step 1.8: Run tests — expect PASS**

```bash
cd backend && uv run pytest tests/services/test_cryptobot_provider.py -v
# Expected: 5 passed
```

- [ ] **Step 1.9: Run full suite — ensure nothing broken**

```bash
cd backend && uv run pytest tests/ -q
# Expected: all 55 previously passing tests still pass, + 5 new
```

- [ ] **Step 1.10: Commit**

```bash
cd backend && git add app/services/payment_providers/ app/models/transaction.py alembic/versions/ tests/services/test_cryptobot_provider.py
git -C .. add backend/app/services/payment_providers/ backend/app/models/transaction.py backend/alembic/versions/ backend/tests/services/test_cryptobot_provider.py
git -C .. commit -m "feat: add CryptoBot payment provider abstraction and payment_url migration"
```

---

## Task 2: Telegram Alert Service

**Files:**
- Create: `backend/app/services/telegram_alert.py`
- Create: `backend/tests/services/test_telegram_alert.py`

- [ ] **Step 2.1: Write failing tests**

```python
# backend/tests/services/test_telegram_alert.py
import pytest
from pytest_httpx import HTTPXMock

from app.services.telegram_alert import send_admin_alert


@pytest.mark.asyncio
async def test_sends_message(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.telegram.org/botmy-token/sendMessage",
        json={"ok": True},
    )
    await send_admin_alert("my-token", "12345", "Test alert")
    request = httpx_mock.get_request()
    import json
    body = json.loads(request.content)
    assert body["chat_id"] == "12345"
    assert body["text"] == "Test alert"


@pytest.mark.asyncio
async def test_no_op_on_missing_token():
    # Should not raise, should not make any HTTP calls
    await send_admin_alert(None, "12345", "Test")


@pytest.mark.asyncio
async def test_no_op_on_missing_chat_id():
    await send_admin_alert("token", None, "Test")


@pytest.mark.asyncio
async def test_swallows_http_error(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.telegram.org/botmy-token/sendMessage",
        status_code=500,
    )
    # Should NOT raise even on server error
    await send_admin_alert("my-token", "12345", "Test")
```

- [ ] **Step 2.2: Run tests — expect FAIL**

```bash
cd backend && uv run pytest tests/services/test_telegram_alert.py -v
```

- [ ] **Step 2.3: Implement**

```python
# backend/app/services/telegram_alert.py
from __future__ import annotations
import logging

import httpx

logger = logging.getLogger(__name__)


async def send_admin_alert(
    token: str | None, chat_id: str | None, message: str
) -> None:
    """Fire-and-forget Telegram alert. No-ops on missing token/chat_id.
    Swallows all exceptions — must never block the main flow.
    """
    if not token or not chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            await http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
            )
    except Exception as exc:
        logger.warning("Telegram alert failed (non-blocking): %s", exc)
```

- [ ] **Step 2.4: Run tests — expect PASS**

```bash
cd backend && uv run pytest tests/services/test_telegram_alert.py -v
# Expected: 4 passed
```

- [ ] **Step 2.5: Commit**

```bash
git -C .. add backend/app/services/telegram_alert.py backend/tests/services/test_telegram_alert.py
git -C .. commit -m "feat: add Telegram admin alert service"
```

---

## Task 3: POST /api/payments — Create Payment Endpoint

**Files:**
- Create: `backend/app/schemas/payment.py`
- Create: `backend/app/services/payment_service.py`
- Create: `backend/app/routers/payments.py` (POST /api/payments only)
- Modify: `backend/app/config.py` (add site_url)
- Modify: `backend/app/main.py` (register router)
- Create: `backend/tests/routers/test_payments_create.py`

- [ ] **Step 3.1: Write failing tests**

```python
# backend/tests/routers/test_payments_create.py
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
from app.models.transaction import Transaction, TransactionStatus
from app.services.payment_providers.base import InvoiceResult

NOW = datetime.now(tz=timezone.utc)
PLAN_ID = uuid.uuid4()


def _make_user(remnawave_uuid=None) -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.remnawave_uuid = remnawave_uuid
    u.has_made_payment = False
    return u


def _make_plan(name="1_month", price=200, duration=30, new_user_price=100):
    p = MagicMock()
    p.id = PLAN_ID
    p.name = name
    p.label = "1 месяц"
    p.price_rub = price
    p.new_user_price_rub = new_user_price
    p.duration_days = duration
    p.is_active = True
    return p


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_create_payment_no_trial_returns_409():
    user = _make_user(remnawave_uuid=None)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(AsyncMock())
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_payment_rate_limited_returns_429():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 6  # over limit of 5
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_create_payment_plan_not_found_returns_404():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(uuid.uuid4())})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_payment_not_configured_returns_503():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    db = AsyncMock(spec=AsyncSession)

    call_count = [0]
    def _side_effect(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # Plan query
            result.scalar_one_or_none = MagicMock(return_value=_make_plan())
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result
    db.execute = AsyncMock(side_effect=_side_effect)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_create_payment_duplicate_pending_returns_200():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    pending_tx = MagicMock(spec=Transaction)
    pending_tx.status = TransactionStatus.pending
    pending_tx.payment_url = "https://t.me/CryptoBot?start=IVexisting"
    pending_tx.id = uuid.uuid4()
    pending_tx.amount_rub = 200
    pending_tx.created_at = NOW  # recent

    db = AsyncMock(spec=AsyncSession)
    call_count = [0]
    def _side_effect(stmt, *a, **kw):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=_make_plan())
        elif call_count[0] == 2:
            # get_active_provider: cryptobot_token → None (but we mock provider separately)
            result.scalar_one_or_none = MagicMock(return_value=None)
        else:
            result.scalar_one_or_none = MagicMock(return_value=pending_tx)
        return result
    db.execute = AsyncMock(side_effect=_side_effect)

    mock_provider = AsyncMock()
    mock_provider.create_invoice = AsyncMock(
        return_value=InvoiceResult(payment_url="https://t.me/CryptoBot?start=IVexisting", external_id="999")
    )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.payments.get_active_provider", return_value=mock_provider), \
         patch("app.services.payment_service.get_pending_transaction", return_value=pending_tx):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["is_existing"] is True


@pytest.mark.asyncio
async def test_create_payment_success_returns_201():
    user = _make_user(remnawave_uuid=uuid.uuid4())
    redis = AsyncMock()
    redis.incr.return_value = 1
    plan = _make_plan()
    new_tx = MagicMock(spec=Transaction)
    new_tx.id = uuid.uuid4()
    new_tx.amount_rub = 100  # new user price
    new_tx.payment_url = "https://t.me/CryptoBot?start=IVnew"

    mock_provider = AsyncMock()
    mock_provider.name = "cryptobot"
    mock_provider.create_invoice = AsyncMock(
        return_value=InvoiceResult(payment_url="https://t.me/CryptoBot?start=IVnew", external_id="123")
    )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.payments.get_active_provider", return_value=mock_provider), \
         patch("app.services.payment_service.get_pending_transaction", return_value=None), \
         patch("app.services.payment_service.calculate_final_price", return_value=(100, None)), \
         patch("app.routers.payments._create_transaction", return_value=new_tx):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments", json={"plan_id": str(PLAN_ID)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["payment_url"] == "https://t.me/CryptoBot?start=IVnew"
    assert data["is_existing"] is False
```

- [ ] **Step 3.2: Run tests — expect FAIL**

```bash
cd backend && uv run pytest tests/routers/test_payments_create.py -v
```

- [ ] **Step 3.3: Add site_url to config**

In `backend/app/config.py`, add after the `frontend_url` line:
```python
site_url: str = "http://localhost"
```

- [ ] **Step 3.4: Create schemas**

```python
# backend/app/schemas/payment.py
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    plan_id: uuid.UUID
    promo_code: str | None = None  # discount_percent only; bonus_days handled in Plan 4


class PaymentResponse(BaseModel):
    payment_url: str
    transaction_id: str
    amount_rub: int
    amount_usdt: str       # e.g. "2.41"
    is_existing: bool


class TransactionHistoryItem(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount_rub: int | None
    plan_name: str | None
    days_added: int | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class CryptoBotWebhookPayload(BaseModel):
    """CryptoBot sends update_type='invoice_paid' with nested invoice in 'payload' field."""
    update_type: str
    update_id: int

    class Invoice(BaseModel):
        invoice_id: int
        status: str          # "paid" | "active" | "expired"
        asset: str
        amount: str
        payload: str         # our order_id = transaction.id (UUID string)
        model_config = {"extra": "allow"}

    payload: Invoice
    model_config = {"extra": "allow"}
```

- [ ] **Step 3.4b: Write failing tests for payment_service.py**

```python
# backend/tests/services/test_payment_service.py
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
```

- [ ] **Step 3.4c: Run payment_service tests — expect FAIL**

```bash
cd backend && uv run pytest tests/services/test_payment_service.py -v
# Expected: ImportError (payment_service.py doesn't exist yet)
```

- [ ] **Step 3.5: Create payment_service.py**

```python
# backend/app/services/payment_service.py
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.promo_code import PromoCode, PromoCodeUsage, PromoCodeType
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User
from app.services.remnawave_client import RemnawaveClient


async def calculate_final_price(
    db: AsyncSession,
    plan: Plan,
    user: User,
    promo_code_str: str | None,
) -> tuple[int, PromoCode | None]:
    """Returns (final_price_rub, validated_promo_or_None).
    Raises HTTP 400 if promo code string is provided but invalid.
    """
    candidates: list[int] = [plan.price_rub]

    # New user discount: only on 1_month plan
    if (
        not user.has_made_payment
        and plan.name == "1_month"
        and plan.new_user_price_rub is not None
    ):
        candidates.append(plan.new_user_price_rub)

    promo: PromoCode | None = None
    if promo_code_str:
        now = datetime.now(tz=timezone.utc)
        result = await db.execute(
            select(PromoCode).where(PromoCode.code == promo_code_str.upper())
        )
        promo = result.scalar_one_or_none()

        if not promo or not promo.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
        if promo.valid_until is not None and promo.valid_until < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
        if promo.max_uses is not None and promo.used_count >= promo.max_uses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")
        if promo.type != PromoCodeType.discount_percent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")

        # Check one-per-user constraint
        usage_result = await db.execute(
            select(PromoCodeUsage).where(
                PromoCodeUsage.promo_code_id == promo.id,
                PromoCodeUsage.user_id == user.id,
            )
        )
        if usage_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Промокод недействителен")

        discounted = round(plan.price_rub * (1 - promo.value / 100))
        candidates.append(discounted)

    return min(candidates), promo


async def get_pending_transaction(
    db: AsyncSession, user_id: uuid.UUID
) -> Transaction | None:
    """SELECT FOR UPDATE (blocking) — serialises concurrent payment creation for the same user."""
    result = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.pending,
        )
        .with_for_update()
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def complete_payment(
    db: AsyncSession,
    transaction: Transaction,
    user: User,
    plan: Plan,
    rw_client: RemnawaveClient,
) -> None:
    """Atomically completes payment: extends Remnawave subscription + updates all local state.
    Single db.commit() at the end — does NOT call sync_subscription_from_remnawave
    (that function has its own internal commit which would break atomicity).
    Raises httpx.HTTPStatusError / httpx.RequestError on Remnawave failure.
    Caller must send alert + return 500.
    """
    now = datetime.now(tz=timezone.utc)

    # Extend Remnawave subscription
    rw_user = await rw_client.get_user(str(user.remnawave_uuid))
    base_date = max(rw_user.expire_at, now)
    new_expire_at = base_date + timedelta(days=plan.duration_days)
    rw_user = await rw_client.update_user(
        str(user.remnawave_uuid),
        traffic_limit_bytes=0,  # unlimited — all paid plans
        expire_at=new_expire_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    # Upsert local subscription directly (no sync_subscription_from_remnawave)
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

    # Update user + transaction
    user.has_made_payment = True
    transaction.status = TransactionStatus.completed
    transaction.completed_at = now
    transaction.days_added = plan.duration_days

    # Record promo code usage if applicable
    if transaction.promo_code_id is not None:
        promo_result = await db.execute(
            select(PromoCode)
            .where(PromoCode.id == transaction.promo_code_id)
            .with_for_update()
        )
        promo = promo_result.scalar_one_or_none()
        if promo is not None:
            db.add(PromoCodeUsage(promo_code_id=promo.id, user_id=user.id))
            promo.used_count += 1

    await db.commit()
```

- [ ] **Step 3.6: Create payments router (POST /api/payments only)**

```python
# backend/app/routers/payments.py
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.plan import Plan
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.payment import CreatePaymentRequest, PaymentResponse
from app.services.payment_providers.base import InvoiceResult
from app.services.payment_providers.factory import get_active_provider
from app.services.payment_service import calculate_final_price, get_pending_transaction
from app.services.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

_PAYMENT_RATE_LIMIT = 5
_PAYMENT_RATE_WINDOW = 60  # seconds
_PENDING_EXPIRY_MINUTES = 30


async def _create_transaction(
    db: AsyncSession,
    user: User,
    plan: Plan,
    amount_rub: int,
    promo_id: uuid.UUID | None,
    provider_name: str,
    order_id: str,
    invoice: InvoiceResult,
) -> Transaction:
    """Create and commit a payment transaction with the Cryptobot invoice details.
    order_id must be a UUID string pre-generated before calling the provider —
    it is used as both Transaction.id and the payload sent to CryptoBot.
    """
    tx = Transaction(
        id=uuid.UUID(order_id),
        user_id=user.id,
        type=TransactionType.payment,
        status=TransactionStatus.pending,
        plan_id=plan.id,
        amount_rub=amount_rub,
        days_added=plan.duration_days,
        payment_provider=provider_name,
        promo_code_id=promo_id,
        external_payment_id=invoice.external_id,
        payment_url=invoice.payment_url,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.post("", status_code=201)
async def create_payment(
    data: CreatePaymentRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PaymentResponse:
    # Guard 1: trial not activated
    if current_user.remnawave_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала активируйте пробный период",
        )

    # Guard 2: rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(redis, f"rate:payment:{client_ip}", _PAYMENT_RATE_LIMIT, _PAYMENT_RATE_WINDOW):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Слишком много запросов")

    # Guard 3: plan exists
    plan_result = await db.execute(select(Plan).where(Plan.id == data.plan_id, Plan.is_active == True))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тариф не найден")

    # Guard 4: provider configured (raises 503 if not)
    provider = await get_active_provider(db)

    # Guard 5/6: deduplication (FOR UPDATE lock serialises concurrent requests)
    now = datetime.now(tz=timezone.utc)
    pending = await get_pending_transaction(db, current_user.id)
    if pending is not None:
        age = now - pending.created_at.replace(tzinfo=timezone.utc) if pending.created_at.tzinfo is None else now - pending.created_at
        if age < timedelta(minutes=_PENDING_EXPIRY_MINUTES):
            response.status_code = 200
            usdt_rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
            usdt_amount = str(round(pending.amount_rub / float(usdt_rate_str), 2))
            return PaymentResponse(
                payment_url=pending.payment_url or "",
                transaction_id=str(pending.id),
                amount_rub=pending.amount_rub,
                amount_usdt=usdt_amount,
                is_existing=True,
            )
        # Expired pending — mark failed
        pending.status = TransactionStatus.failed
        await db.commit()

    # Price calculation (may raise 400 for invalid promo)
    final_price, promo = await calculate_final_price(db, plan, current_user, data.promo_code)

    # Create Cryptobot invoice + transaction (single commit after invoice creation)
    # Generate order_id upfront so invoice and transaction share the same UUID
    order_id = str(uuid.uuid4())

    try:
        invoice = await provider.create_invoice(
            amount_rub=final_price,
            order_id=order_id,
            description=plan.label,
        )
    except Exception as exc:
        logger.exception("Payment provider invoice creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ошибка платёжной системы. Попробуйте позже.",
        )

    tx = await _create_transaction(
        db=db,
        user=current_user,
        plan=plan,
        amount_rub=final_price,
        promo_id=promo.id if promo else None,
        provider_name=provider.name,
        order_id=order_id,
        invoice=invoice,
    )

    usdt_rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
    usdt_amount = str(round(final_price / float(usdt_rate_str), 2))

    return PaymentResponse(
        payment_url=invoice.payment_url,
        transaction_id=str(tx.id),
        amount_rub=final_price,
        amount_usdt=usdt_amount,
        is_existing=False,
    )
```

> **Implementation note:** The `order_id` passed to `create_invoice` should ideally be the transaction ID. But the transaction ID is created after the invoice. A simple fix: generate the order ID before calling the provider, then use the same UUID for the transaction. Update the `_create_transaction` call signature to accept a pre-generated `order_id`. See Step 3.7 cleanup.

- [ ] **Step 3.7: Add get_setting import and verify order_id threading**

Step 3.6 already generates `order_id` upfront and passes it to `_create_transaction`. Verify the top-of-file imports include:

```python
from app.services.setting_service import get_setting
```

This is needed for `usdt_rate_str = await get_setting(db, "usdt_exchange_rate") or "83"` in the response.

> **Note:** `_create_transaction` is kept as a named helper so tests can patch `app.routers.payments._create_transaction`. Do NOT inline or remove it.

- [ ] **Step 3.8: Register router in main.py**

Read `backend/app/main.py`, then add:
```python
from app.routers import payments
# ...
app.include_router(payments.router)
```

- [ ] **Step 3.9: Run tests — expect PASS**

```bash
cd backend && uv run pytest tests/routers/test_payments_create.py tests/services/test_payment_service.py -v
# Expected: 6 router tests + 6 service tests = 12 passed
```

- [ ] **Step 3.10: Run full suite**

```bash
cd backend && uv run pytest tests/ -q
# Expected: 65+ passed, 0 failed
```

- [ ] **Step 3.11: Commit**

```bash
git -C .. add backend/app/schemas/payment.py backend/app/services/payment_service.py \
  backend/app/routers/payments.py backend/app/config.py backend/app/main.py \
  backend/tests/routers/test_payments_create.py backend/tests/services/test_payment_service.py
git -C .. commit -m "feat: add POST /api/payments — create CryptoBot payment invoice"
```

---

## Task 4: POST /api/payments/webhook + complete_payment

**Files:**
- Modify: `backend/app/routers/payments.py` (add webhook endpoint)
- Modify: `backend/app/services/payment_service.py` (complete_payment already written, verify)
- Create: `backend/tests/routers/test_payments_webhook.py`

- [ ] **Step 4.1: Write failing tests**

```python
# backend/tests/routers/test_payments_webhook.py
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
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.plan import Plan


NOW = datetime.now(tz=timezone.utc)
TOKEN = "test-token-123"


def _make_sig(token: str, body: bytes) -> str:
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _make_transaction(status=TransactionStatus.pending) -> Transaction:
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.status = status
    tx.user_id = uuid.uuid4()
    tx.plan_id = uuid.uuid4()
    tx.promo_code_id = None
    tx.amount_rub = 200
    return tx


def _make_plan() -> Plan:
    p = MagicMock(spec=Plan)
    p.id = uuid.uuid4()
    p.label = "1 месяц"
    p.duration_days = 30
    return p


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _make_webhook_body(order_id: str, status: str = "paid") -> bytes:
    return json.dumps({
        "update_type": "invoice_paid",
        "update_id": 1,
        "request_date": "2026-03-30T12:00:00Z",
        "payload": {
            "invoice_id": 12345,
            "status": status,
            "asset": "USDT",
            "amount": "2.41",
            "payload": order_id,
        },
    }).encode()


@pytest.mark.asyncio
async def test_webhook_invalid_ip_returns_400():
    body = _make_webhook_body(str(uuid.uuid4()))
    db = AsyncMock(spec=AsyncSession)
    # IP list contains "1.2.3.4" — our request comes from testclient (127.0.0.1)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(
        return_value=MagicMock(is_sensitive=False, value={"value": '["1.2.3.4"]'})
    )
    db.execute = AsyncMock(return_value=result)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/payments/webhook", content=body)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400():
    order_id = str(uuid.uuid4())
    body = _make_webhook_body(order_id)
    db = AsyncMock(spec=AsyncSession)
    # IP check passes (empty list)
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/payments/webhook",
                content=body,
                headers={"crypto-pay-api-signature": "invalidsignature"},
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_already_completed_returns_200():
    tx = _make_transaction(status=TransactionStatus.completed)
    order_id = str(tx.id)
    body = _make_webhook_body(order_id)

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx):
        db = AsyncMock(spec=AsyncSession)
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                sig = _make_sig(TOKEN, body)
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": sig})
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_cancel_marks_transaction_failed():
    tx = _make_transaction()
    order_id = str(tx.id)
    body = _make_webhook_body(order_id, status="expired")
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": _make_sig(TOKEN, body)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert tx.status == TransactionStatus.failed


@pytest.mark.asyncio
async def test_webhook_paid_success_returns_200():
    """Happy path: paid webhook → complete_payment called → 200 returned."""
    tx = _make_transaction()
    plan = _make_plan()
    order_id = str(tx.id)
    body = _make_webhook_body(order_id, status="paid")
    db = AsyncMock(spec=AsyncSession)

    mock_complete = AsyncMock(return_value=None)

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx), \
         patch("app.routers.payments._load_plan_and_user", return_value=(plan, MagicMock())), \
         patch("app.routers.payments._get_remnawave_client", return_value=MagicMock()), \
         patch("app.routers.payments.complete_payment", mock_complete):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": _make_sig(TOKEN, body)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_paid_remnawave_failure_returns_500():
    tx = _make_transaction()
    plan = _make_plan()
    order_id = str(tx.id)
    body = _make_webhook_body(order_id, status="paid")
    db = AsyncMock(spec=AsyncSession)

    import httpx as _httpx

    with patch("app.routers.payments._get_webhook_token", return_value=TOKEN), \
         patch("app.routers.payments._check_webhook_ip", return_value=True), \
         patch("app.routers.payments._verify_webhook_sig", return_value=True), \
         patch("app.routers.payments._load_transaction", return_value=tx), \
         patch("app.routers.payments._load_plan_and_user", return_value=(plan, MagicMock())), \
         patch("app.routers.payments._get_remnawave_client", return_value=MagicMock()), \
         patch("app.routers.payments.complete_payment",
               side_effect=_httpx.RequestError("timeout")), \
         patch("app.routers.payments.send_admin_alert", new=AsyncMock()):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/payments/webhook", content=body,
                                    headers={"crypto-pay-api-signature": _make_sig(TOKEN, body)})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 500
```

- [ ] **Step 4.2: Run tests — expect FAIL**

```bash
cd backend && uv run pytest tests/routers/test_payments_webhook.py -v
```

- [ ] **Step 4.3: Add webhook endpoint to payments router**

Add to `backend/app/routers/payments.py`:

```python
# Additional imports needed at top:
from sqlalchemy import select as _select
from app.models.transaction import Transaction
from app.schemas.payment import CryptoBotWebhookPayload
from app.services.payment_service import complete_payment
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.telegram_alert import send_admin_alert
import json as _json


# Helper functions (makes webhook testable via patching):

async def _get_webhook_token(db: AsyncSession) -> str | None:
    return await get_setting_decrypted(db, "cryptobot_token")


async def _check_webhook_ip(db: AsyncSession, client_ip: str) -> bool:
    """Returns True if IP is allowed (or no allowlist configured)."""
    allowed_ips_str = await get_setting(db, "cryptobot_webhook_allowed_ips")
    if not allowed_ips_str or allowed_ips_str in ("", "[]"):
        return True
    try:
        allowed = _json.loads(allowed_ips_str)
        return client_ip in allowed
    except (ValueError, TypeError):
        return True


def _verify_webhook_sig(raw_body: bytes, headers: dict, token: str) -> bool:
    from app.services.payment_providers.cryptobot import CryptoBotProvider
    provider = CryptoBotProvider(token=token, usdt_rate=83.0)
    return provider.verify_webhook(raw_body, dict(headers))


async def _load_transaction(db: AsyncSession, order_id: str) -> Transaction | None:
    result = await db.execute(
        _select(Transaction).where(Transaction.id == _uuid_or_none(order_id))
    )
    return result.scalar_one_or_none()


def _uuid_or_none(s: str):
    try:
        import uuid as _uuid
        return _uuid.UUID(s)
    except ValueError:
        return None


async def _load_plan_and_user(db: AsyncSession, transaction: Transaction):
    from app.models.plan import Plan
    from app.models.user import User
    plan_res = await db.execute(_select(Plan).where(Plan.id == transaction.plan_id))
    plan = plan_res.scalar_one_or_none()
    user_res = await db.execute(_select(User).where(User.id == transaction.user_id))
    user = user_res.scalar_one_or_none()
    return plan, user


async def _get_remnawave_client(db: AsyncSession) -> RemnawaveClient | None:
    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        return None
    return RemnawaveClient(url, token)


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    client_ip = request.client.host if request.client else "unknown"

    # Verify 1: IP allowlist
    if not await _check_webhook_ip(db, client_ip):
        return Response(status_code=400)

    # Load token for signature verification
    token = await _get_webhook_token(db)
    if not token:
        return Response(status_code=400)

    # Verify 2: HMAC signature
    if not _verify_webhook_sig(raw_body, dict(request.headers), token):
        return Response(status_code=400)

    # Parse payload
    try:
        payload = CryptoBotWebhookPayload.model_validate_json(raw_body)
    except Exception:
        return Response(status_code=400)

    order_id = payload.payload.payload
    tx = await _load_transaction(db, order_id)
    if tx is None:
        return Response(status_code=400)

    # Idempotency
    if tx.status == TransactionStatus.completed:
        return Response(status_code=200)

    if payload.update_type == "invoice_paid" and payload.payload.status == "paid":
        plan, user = await _load_plan_and_user(db, tx)
        if plan is None or user is None:
            return Response(status_code=400)

        rw_client = await _get_remnawave_client(db)
        if rw_client is None:
            await send_admin_alert(
                await get_setting(db, "telegram_bot_token"),
                await get_setting(db, "telegram_admin_chat_id"),
                f"⚠️ Webhook error: Remnawave not configured\nTransaction: {tx.id}",
            )
            return Response(status_code=500)

        try:
            await complete_payment(db, tx, user, plan, rw_client)
        except Exception as exc:
            logger.exception("complete_payment failed for tx %s: %s", tx.id, exc)
            await send_admin_alert(
                await get_setting(db, "telegram_bot_token"),
                await get_setting(db, "telegram_admin_chat_id"),
                f"⚠️ Webhook error: Remnawave unavailable\n"
                f"Transaction: {tx.id}\nUser: {user.id}\n"
                f"Plan: {plan.label}\nError: {exc}",
            )
            return Response(status_code=500)

        return Response(status_code=200)

    # Failed/expired/other
    tx.status = TransactionStatus.failed
    await db.commit()
    return Response(status_code=200)
```

- [ ] **Step 4.4: Run tests — expect PASS**

```bash
cd backend && uv run pytest tests/routers/test_payments_webhook.py -v
# Expected: 6 passed
```

- [ ] **Step 4.5: Run full suite**

```bash
cd backend && uv run pytest tests/ -q
# Expected: all passing
```

- [ ] **Step 4.6: Commit**

```bash
git -C .. add backend/app/routers/payments.py backend/app/services/payment_service.py \
  backend/tests/routers/test_payments_webhook.py
git -C .. commit -m "feat: add POST /api/payments/webhook with CryptoBot signature verification"
```

---

## Task 5: GET /api/payments/history + usdt_exchange_rate seed + Smoke Test

**Files:**
- Modify: `backend/app/routers/payments.py` (add history endpoint)
- Create: `backend/alembic/versions/<hash>_seed_usdt_exchange_rate.py`

- [ ] **Step 5.1: Add history endpoint to router**

Add to `backend/app/routers/payments.py`:

```python
# Additional imports:
from app.schemas.payment import TransactionHistoryItem

@router.get("/history", response_model=list[TransactionHistoryItem])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionHistoryItem]:
    result = await db.execute(
        _select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .limit(20)
    )
    transactions = result.scalars().all()
    items = []
    for tx in transactions:
        plan_name = None
        if tx.plan_id is not None:
            plan_res = await db.execute(_select(Plan).where(Plan.id == tx.plan_id))
            plan_obj = plan_res.scalar_one_or_none()
            if plan_obj:
                plan_name = plan_obj.label
        items.append(TransactionHistoryItem(
            id=tx.id,
            type=tx.type.value,
            status=tx.status.value,
            amount_rub=tx.amount_rub,
            plan_name=plan_name,
            days_added=tx.days_added,
            created_at=tx.created_at,
            completed_at=tx.completed_at,
        ))
    return items
```

- [ ] **Step 5.2: Create usdt_exchange_rate seed migration**

```bash
cd backend && uv run alembic revision -m "seed_usdt_exchange_rate"
```

Fill the generated file:

```python
"""seed_usdt_exchange_rate

Revision ID: <auto>
Revises: <previous_revision>
Create Date: <auto>
"""
from alembic import op
import sqlalchemy as sa

revision = "<auto>"
down_revision = "<hash_from_payment_url_migration>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        INSERT INTO settings (key, value, is_sensitive)
        VALUES ('usdt_exchange_rate', '{"value": "83"}', false)
        ON CONFLICT (key) DO NOTHING
        """)
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = 'usdt_exchange_rate'")
    )
```

- [ ] **Step 5.3: Run full test suite**

```bash
cd backend && uv run pytest tests/ -q
# Expected: all passing (55 original + 6 provider + 4 alert + 6 service + 6 router create + 6 webhook ≥ 83 total)
```

- [ ] **Step 5.4: Apply migrations in Docker**

```bash
docker exec custom_sub_pages-backend-1 uv run alembic upgrade head
docker exec custom_sub_pages-backend-1 uv run alembic current
```

- [ ] **Step 5.5: Smoke test endpoints**

```bash
# Unauthenticated requests must return 401
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/payments
echo ""
# Expected: 401 (or 405 for GET on POST-only — that's fine too)

curl -s -o /dev/null -w "%{http_code}" http://localhost/api/payments/history
echo ""
# Expected: 401

# Webhook with no body should return 400 (no valid signature)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost/api/payments/webhook
echo ""
# Expected: 400 or 422
```

- [ ] **Step 5.6: Run tests in container**

```bash
docker exec custom_sub_pages-backend-1 uv run pytest tests/ -q
# Expected: all passing
```

- [ ] **Step 5.7: Commit and tag**

```bash
git -C .. add backend/app/routers/payments.py backend/alembic/versions/
git -C .. commit -m "feat: add GET /api/payments/history and usdt_exchange_rate seed"
git -C .. tag plan-3-complete
```
