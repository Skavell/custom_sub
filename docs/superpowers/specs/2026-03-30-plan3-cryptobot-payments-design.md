# Plan 3 Design: CryptoBot Payment Integration

**Date:** 2026-03-30
**Status:** Approved
**Scope:** CryptoBot (Telegram) payment processing with clean provider abstraction, subscription extension on payment, Telegram admin alerts. Promo codes deferred to Plan 4.

---

## Context

Plan 2 delivered: trial activation, subscription status API, Remnawave sync. The `transactions` table, `Plan` model, `Subscription` model, `remnawave_client.py`, and `setting_service.py` are production-ready.

**Constraint:** Paying requires `user.remnawave_uuid IS NOT NULL`. Users must activate trial first.

**Payment provider:** CryptoBot (`@CryptoBot` on Telegram). Creates invoices via REST API, user pays via Telegram link (`t.me/CryptoBot?start=IV...`). No KYC required. Webhook notifies us on payment.

**Currency conversion:** RUB → USDT. Rate stored manually in `settings` table (`usdt_exchange_rate`). Default seed value: `"83"` (1 USDT = 83 RUB). Admin updates via existing `set_setting`. Formula: `usdt_amount = round(amount_rub / rate, 2)`.

---

## Provider Abstraction

Clean interface so adding a new provider in future = one new class + settings entries.

```python
# app/services/payment_providers/base.py
from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class InvoiceResult:
    payment_url: str      # Link shown to user (t.me/CryptoBot?start=IV...)
    external_id: str      # Provider's invoice ID → stored as transaction.external_payment_id


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

```python
# app/services/payment_providers/cryptobot.py
class CryptoBotProvider(PaymentProvider):
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str, usdt_rate: float) -> None:
        self._token = token
        self._rate = usdt_rate  # RUB per 1 USDT

    @property
    def name(self) -> str:
        return "cryptobot"

    async def create_invoice(self, amount_rub: int, order_id: str, description: str) -> InvoiceResult:
        """
        POST /createInvoice
        Headers: Crypto-Pay-API-Token: {token}
        Body: asset="USDT", amount=str(round(amount_rub/rate, 2)),
              description=description, payload=order_id
        Response: result.bot_invoice_url, result.invoice_id
        """

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """
        CryptoBot signs webhooks:
          secret = SHA256(token)
          signature = HMAC-SHA256(secret, raw_body).hexdigest()
        Sent in header: crypto-pay-api-signature
        """
```

```python
# app/services/payment_providers/__init__.py
# (empty — package marker)
```

### Provider factory (used by router to get active provider)

```python
# app/services/payment_providers/factory.py
async def get_active_provider(db: AsyncSession) -> PaymentProvider:
    """
    Reads settings: cryptobot_token (sensitive), usdt_exchange_rate (plain).
    Returns CryptoBotProvider if configured.
    Raises HTTP 503 if not configured.
    """
```

---

## Architecture

### New Files

| File | Responsibility |
|---|---|
| `app/services/payment_providers/__init__.py` | Package marker |
| `app/services/payment_providers/base.py` | `PaymentProvider` ABC + `InvoiceResult` dataclass |
| `app/services/payment_providers/cryptobot.py` | CryptoBot implementation |
| `app/services/payment_providers/factory.py` | `get_active_provider(db)` factory |
| `app/services/telegram_alert.py` | Fire-and-forget admin alerts via Bot API |
| `app/services/payment_service.py` | Price calc, pending dedup, `complete_payment` |
| `app/routers/payments.py` | 3 endpoints |
| `app/schemas/payment.py` | Pydantic schemas |

### New Config Field

`site_url: str` added to `app/config.py` `Settings` (env var `SITE_URL`, default `"http://localhost"`). Used only to construct webhook callback URL.

### New DB Migration

Add `payment_url VARCHAR(2048)` column to `transactions` table (nullable). Stores the invoice URL so deduplication guard can return it without extra API calls.

```sql
ALTER TABLE transactions ADD COLUMN payment_url VARCHAR(2048);
```

### New DB Settings (via `settings` table)

| Key | Sensitive | Fetched with | Description |
|---|---|---|---|
| `cryptobot_token` | yes | `get_setting_decrypted` | CryptoBot API token |
| `usdt_exchange_rate` | no | `get_setting` | RUB per 1 USDT, e.g. `"83"` |
| `cryptobot_webhook_allowed_ips` | no | `get_setting` | JSON array string of CryptoBot IPs. Empty = skip check |
| `telegram_admin_chat_id` | no | `get_setting` | Chat ID for admin error alerts |

`telegram_bot_token` already exists from Plan 1.

### Seed Migration

Add to a new data migration (or seed script):
```sql
INSERT INTO settings (key, value, is_sensitive) VALUES
  ('usdt_exchange_rate', '{"value": "83"}', false)
ON CONFLICT (key) DO NOTHING;
```

---

## Pydantic Schemas (`app/schemas/payment.py`)

```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    plan_id: uuid.UUID
    promo_code: str | None = None  # Only discount_percent codes; bonus_days in Plan 4


class PaymentResponse(BaseModel):
    payment_url: str       # t.me/CryptoBot?start=IV...
    transaction_id: str
    amount_rub: int
    amount_usdt: str       # e.g. "2.41" — shown to user
    is_existing: bool      # True if returning existing pending invoice


class TransactionHistoryItem(BaseModel):
    id: uuid.UUID
    type: str              # "payment" | "trial_activation" | etc.
    status: str
    amount_rub: int | None
    plan_name: str | None  # plan.label if plan_id IS NOT NULL, else None
    days_added: int | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class CryptoBotWebhookPayload(BaseModel):
    """CryptoBot sends update_type="invoice_paid" with nested invoice object."""
    update_type: str        # "invoice_paid"
    update_id: int
    request_date: str

    class Invoice(BaseModel):
        invoice_id: int
        status: str         # "paid" | "active" | "expired"
        asset: str
        amount: str
        payload: str        # our order_id (transaction.id as string)
        model_config = {"extra": "allow"}

    payload: Invoice        # note: field name same as nested model — use alias
    model_config = {"extra": "allow"}
```

> **Implementation note:** CryptoBot webhook body has shape `{"update_type": "invoice_paid", "update_id": N, "request_date": "...", "payload": {...invoice...}}`. The `payload` field inside the invoice object holds our `order_id` string. Parse carefully.

---

## Endpoints

### `POST /api/payments`

**Auth:** Required (`get_current_user`)
**Rate limit:** 5 req/min per IP — Redis key `rate:payment:{client_ip}`, window 60s

**Guard order:**
1. `user.remnawave_uuid is None` → 409 `"Сначала активируйте пробный период"`
2. IP rate limit exceeded → 429
3. `plan_id` not found or `plan.is_active = False` → 404
4. `get_active_provider(db)` → 503 if not configured
5. `get_pending_transaction(db, user.id)` — `SELECT ... FOR UPDATE` (blocking)
6. Found + `created_at > now - 30min` → return 200 with `transaction.payment_url` (`is_existing=True`)
7. Found + `created_at <= now - 30min` → mark `failed`, continue

**Price calculation** (`payment_service.calculate_final_price`):
- Base: `plan.price_rub`
- New user: `not user.has_made_payment AND plan.name == "1_month" AND plan.new_user_price_rub IS NOT NULL` → candidate `plan.new_user_price_rub`
- Promo (`discount_percent`): `round(plan.price_rub * (1 - value/100))`
- Final: `min(candidates)`

**Promo code validation:**
- `is_active=True`, `valid_until IS NULL OR > now`, `max_uses IS NULL OR used_count < max_uses`, no prior `PromoCodeUsage` for this user, `type == discount_percent`
- Invalid → 400 `"Промокод недействителен"`
- Usage recorded only on webhook completion

**Transaction creation (single atomic commit):**
1. `Transaction(type=payment, status=pending, plan_id, amount_rub, days_added=plan.duration_days, payment_provider="cryptobot", external_payment_id=None, payment_url=None, promo_code_id)` — `db.flush()` to get `transaction.id`
2. `invoice = await provider.create_invoice(amount_rub=final_price, order_id=str(transaction.id), description=plan.label)`
3. `transaction.external_payment_id = invoice.external_id`, `transaction.payment_url = invoice.payment_url`
4. `await db.commit()`

If step 2 fails: `transaction.status = failed`, commit, raise 503.

**Response:** 201 for new, 200 for existing.

```json
{"payment_url": "https://t.me/CryptoBot?start=IVxxxxx", "transaction_id": "uuid", "amount_rub": 200, "amount_usdt": "2.41", "is_existing": false}
```

---

### `POST /api/payments/webhook`

**Auth:** None (public, CSRF-exempt)

**Webhook signature verification:**
```python
import hashlib, hmac as _hmac

def verify_cryptobot_webhook(raw_body: bytes, headers: dict[str, str], token: str) -> bool:
    secret = hashlib.sha256(token.encode()).digest()
    signature = headers.get("crypto-pay-api-signature", "")
    expected = _hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected.lower(), signature.lower())
```

**Source verification:**
1. IP allowlist check (`cryptobot_webhook_allowed_ips`). Empty → skip. Failure → 400
2. Signature check (`verify_cryptobot_webhook`). Failure → 400

**Processing logic:**
1. Parse body as `CryptoBotWebhookPayload`
2. Extract `order_id = payload.payload.payload` (the inner `payload` field of the invoice)
3. Find `Transaction` by `order_id`. Not found → 400
4. If `transaction.status == completed` → 200 (idempotent)
5. If `payload.update_type == "invoice_paid"` and `invoice.status == "paid"`:
   - Call `complete_payment(db, transaction, user, plan, rw_client)`
   - On success: 200
   - On Remnawave failure: send Telegram alert, return 500 (CryptoBot retries)
6. Otherwise (expired, unknown): `transaction.status = failed`, commit, 200

---

### `GET /api/payments/history`

**Auth:** Required
**Query:** last 20 transactions for current user, `ORDER BY created_at DESC LIMIT 20`
**Response:** `list[TransactionHistoryItem]` — all types, actual `type` value, `plan_name = plan.label`

---

## `complete_payment` (in `payment_service.py`)

Single atomic `db.commit()` — does NOT call `sync_subscription_from_remnawave` (that function has an internal commit which breaks atomicity):

```
1. rw_user = await rw_client.get_user(str(user.remnawave_uuid))
2. base_date = max(rw_user.expire_at, now_utc)
3. new_expire_at = base_date + timedelta(days=plan.duration_days)
4. rw_user = await rw_client.update_user(str(user.remnawave_uuid),
       traffic_limit_bytes=0,   # unlimited — all paid plans
       expire_at=new_expire_at.strftime("%Y-%m-%dT%H:%M:%SZ"))
5. Upsert local Subscription row directly:
   sub.type = SubscriptionType.paid
   sub.status = SubscriptionStatus.active
   sub.expires_at = rw_user.expire_at
   sub.traffic_limit_gb = None  # 0 bytes → unlimited
   sub.synced_at = now_utc
6. user.has_made_payment = True
7. transaction.status = TransactionStatus.completed
   transaction.completed_at = now_utc
   transaction.days_added = plan.duration_days
8. If transaction.promo_code_id:
   - SELECT promo_code FOR UPDATE
   - INSERT PromoCodeUsage(promo_code_id, user_id, used_at=now_utc)
   - promo_code.used_count += 1
9. await db.commit()
```

Raises `httpx.HTTPStatusError` / `httpx.RequestError` on Remnawave failure → caller sends alert + returns 500.

---

## `TelegramAlertService` (`services/telegram_alert.py`)

```python
async def send_admin_alert(token: str | None, chat_id: str | None, message: str) -> None:
    """Fire-and-forget. No-ops on missing token/chat_id. Swallows all exceptions."""
```

---

## Error Handling

| Scenario | HTTP | Retry? |
|---|---|---|
| Invalid IP on webhook | 400 | No |
| Invalid HMAC on webhook | 400 | No |
| Transaction not found | 400 | No |
| Already completed | 200 | — |
| Remnawave unavailable | 500 | Yes (CryptoBot retries) |
| Invoice expired/other | 200 | — |

---

## Testing Strategy (~22 tests)

| File | Tests |
|---|---|
| `tests/services/test_cryptobot_provider.py` | create_invoice success, HMAC sign correct, verify_webhook valid/invalid |
| `tests/services/test_telegram_alert.py` | message sent, failure swallowed, no-op missing token, no-op missing chat_id |
| `tests/services/test_payment_service.py` | price: no discount, new_user, promo, min-wins; pending dedup; promo invalid→400 |
| `tests/routers/test_payments_create.py` | no_trial→409, rate_limited→429, plan_not_found→404, not_configured→503, duplicate→200, success→201 |
| `tests/routers/test_payments_webhook.py` | invalid_ip→400, invalid_sig→400, already_completed→200, paid_success, remnawave_fail→500+alert, expired→200 |

---

## Task Breakdown

| # | Task | Files |
|---|---|---|
| 1 | Provider abstraction + CryptoBot + migration | `payment_providers/base.py`, `cryptobot.py`, `__init__.py`, `factory.py`, `alembic/versions/*_add_payment_url.py`, `tests/services/test_cryptobot_provider.py` |
| 2 | TelegramAlertService | `services/telegram_alert.py`, `tests/services/test_telegram_alert.py` |
| 3 | `POST /api/payments` | `schemas/payment.py`, `services/payment_service.py`, `routers/payments.py`, `config.py`, register in `main.py`, `tests/routers/test_payments_create.py` |
| 4 | `POST /api/payments/webhook` + `complete_payment` | extend `routers/payments.py`, extend `payment_service.py`, `tests/routers/test_payments_webhook.py` |
| 5 | `GET /api/payments/history` + usdt_exchange_rate seed + smoke | extend router+schema, seed migration, Docker smoke, `git tag plan-3-complete` |
