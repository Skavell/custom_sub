# Plan 3 Design: Cryptomus Payment Integration

**Date:** 2026-03-30
**Status:** Approved
**Scope:** Cryptomus cryptocurrency payment processing, subscription extension on payment, Telegram admin alerts. Promo codes are deferred to Plan 4.

---

## Context

Plan 2 delivered: trial activation, subscription status API, Remnawave sync on first Telegram login. The local `transactions` table, `Plan` model, and `Subscription` model are all in place. `remnawave_client.py` and `setting_service.py` (with AES-256-GCM decryption) are production-ready.

**Constraint:** Paying requires an active Remnawave account. Users must activate the trial first (`POST /api/subscriptions/trial`) before they can pay. This guarantees `user.remnawave_uuid IS NOT NULL` at payment time.

---

## Architecture

### New Files

| File | Responsibility |
|---|---|
| `app/services/cryptomus_client.py` | httpx wrapper for Cryptomus REST API (create invoice, HMAC signing) |
| `app/services/telegram_alert.py` | Send admin alert messages via Telegram Bot API (fire-and-forget) |
| `app/services/payment_service.py` | Business logic: price calculation, pending-invoice deduplication, transaction lifecycle |
| `app/routers/payments.py` | Three endpoints: create payment, webhook, history |
| `app/schemas/payment.py` | Pydantic schemas for request/response |

### New Config Field

`site_url: str` added to `app/config.py` `Settings` class (read from env var `SITE_URL`, default `"http://localhost"`). Stored in env/config rather than the DB settings table because it is a deployment-time constant, not an admin-UI parameter.

### New DB Migration

Add `payment_url: str | None` column to the `transactions` table (nullable VARCHAR 2048). Required to return existing pending invoice URLs during deduplication (guard 5) without an extra Cryptomus API round-trip.

```sql
ALTER TABLE transactions ADD COLUMN payment_url VARCHAR(2048);
```

### New DB Settings (via `settings` table)

| Key | Sensitive | Fetched with |
|---|---|---|
| `cryptomus_merchant_id` | yes | `get_setting_decrypted` |
| `cryptomus_api_key` | yes | `get_setting_decrypted` |
| `cryptomus_webhook_allowed_ips` | no | `get_setting` |
| `telegram_admin_chat_id` | no | `get_setting` |

`telegram_bot_token` already exists from Plan 1 (fetched with `get_setting`).

---

## Pydantic Schemas (`app/schemas/payment.py`)

```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    plan_id: uuid.UUID
    promo_code: str | None = None  # Only discount_percent codes; bonus_days handled in Plan 4


class PaymentResponse(BaseModel):
    payment_url: str
    transaction_id: str
    amount_rub: int
    is_existing: bool  # True if returning an existing pending invoice


class TransactionHistoryItem(BaseModel):
    id: uuid.UUID
    type: str          # actual TransactionType value: "payment", "trial_activation", etc.
    status: str
    amount_rub: int | None
    plan_name: str | None  # plan.label if plan_id IS NOT NULL, else None
    days_added: int | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class CryptomусWebhookPayload(BaseModel):
    """Subset of Cryptomus webhook fields. Extra fields are ignored."""
    order_id: str   # our transaction.id (UUID string)
    uuid: str       # Cryptomus invoice UUID = transaction.external_payment_id
    status: str     # "paid"|"paid_over"|"cancel"|"wrong_amount"|"fail"|"check"|"wrong_amount_waiting"
    sign: str       # HMAC-MD5 signature — removed from body before verification
    amount: str
    currency: str
    model_config = {"extra": "allow"}
```

---

## Endpoints

### `POST /api/payments`

**Auth:** Required (`get_current_user`)
**Rate limit:** 5 requests/minute per IP — Redis key: `rate:payment:{client_ip}`, window 60 seconds

**Guard order:**
1. `user.remnawave_uuid is None` → 409 `"Сначала активируйте пробный период"`
2. IP rate limit exceeded → 429
3. `plan_id` not found or `plan.is_active = False` → 404
4. `cryptomus_merchant_id` or `cryptomus_api_key` missing from settings → 503
5. Load pending transaction using `SELECT ... FOR UPDATE` (blocking, not SKIP LOCKED) to serialise concurrent requests for the same user
6. Existing `pending` transaction where `created_at > now - 30min` → return 200 with `transaction.payment_url` (`is_existing=True`). The blocking `FOR UPDATE` lock ensures only one concurrent request enters this branch.
7. Existing `pending` transaction where `created_at <= now - 30min` → mark it `failed`, continue

**Price calculation** (`payment_service.calculate_final_price`):
- Candidates list starts with `[plan.price_rub]`
- New user discount: `not user.has_made_payment AND plan.name == "1_month" AND plan.new_user_price_rub IS NOT NULL` → add `plan.new_user_price_rub`. (Note: `"1_month"` matches the seed migration from Plan 2 — `f989da77bf10_seed_plans.py`.)
- Promo discount (`discount_percent` type): if promo code provided and valid → add `round(plan.price_rub * (1 - value/100))`
- Final: `min(candidates)` — lowest price wins

**Promo code validation:**
- `promo_code.is_active = True`
- `promo_code.valid_until IS NULL OR promo_code.valid_until > now`
- `promo_code.max_uses IS NULL OR promo_code.used_count < promo_code.max_uses`
- No `PromoCodeUsage` row for `(promo_code.id, user.id)`
- `promo_code.type == PromoCodeType.discount_percent`
- Invalid for any reason → 400 `"Промокод недействителен"`
- `PromoCodeUsage` insert + `used_count` increment deferred to webhook completion (see below)

**Transaction creation (single atomic commit):**
1. Create `Transaction(type=TransactionType.payment, status=pending, plan_id=plan.id, amount_rub=final_price, days_added=plan.duration_days, payment_provider="cryptomus", external_payment_id=None, payment_url=None, promo_code_id=promo.id if promo else None)`. Flush (do not commit yet).
2. Call `CryptomусClient.create_invoice(amount=str(final_price) + ".00", currency="RUB", order_id=str(transaction.id), url_callback=settings.site_url + "/api/payments/webhook")`
3. Set `transaction.external_payment_id = invoice.uuid` and `transaction.payment_url = invoice.url`.
4. `await db.commit()` — single commit for the whole creation.

If step 2 fails (httpx error or non-2xx from Cryptomus): set `transaction.status = failed`, commit, raise HTTP 503.

**Response:** HTTP 201 for new invoice, HTTP 200 for existing pending invoice. Use `Response` object with explicit `status_code`.

```json
{"payment_url": "https://pay.cryptomus.com/...", "transaction_id": "uuid", "amount_rub": 200, "is_existing": false}
```

---

### `POST /api/payments/webhook`

**Auth:** None (public, CSRF-exempt)

**HMAC verification (canonical raw-bytes approach):**

Cryptomus computes: `sign = md5(base64(webhook_body_with_sign_replaced_by_empty_string) + api_key)`

The only correct verification approach that avoids JSON re-serialisation key-order issues:

```python
import hashlib, base64, re, hmac as _hmac

def verify_cryptomus_sign(raw_body: bytes, api_key: str) -> bool:
    # Replace the sign value in the raw JSON bytes with an empty string
    # Matches: "sign":"<any chars except quote>"  →  "sign":""
    body_without_sign = re.sub(
        rb'"sign"\s*:\s*"[^"]*"',
        b'"sign":""',
        raw_body,
    )
    encoded = base64.b64encode(body_without_sign).decode()
    expected = hashlib.md5((encoded + api_key).encode()).hexdigest()
    # Extract sign from parsed body for comparison
    import json
    sign = json.loads(raw_body).get("sign", "")
    return _hmac.compare_digest(expected.lower(), sign.lower())
```

This is the canonical implementation. Do not use `json.loads` + `json.dumps` re-serialisation — it will break if Cryptomus sends formatted JSON or if key order differs.

**Source verification (order matters):**
1. IP allowlist: parse `cryptomus_webhook_allowed_ips` setting as JSON array. If missing/empty/`"[]"` → skip check. If `request.client.host` not in list → 400 (no detail, no logging to avoid log spam)
2. HMAC: `verify_cryptomus_sign(raw_body, api_key)`. Failure → 400 (no detail)

**Processing logic:**
1. Find `Transaction` by `order_id`. Not found → 400
2. If `transaction.status == completed` → return 200 (idempotent)
3. If status == `"check"` → return 200 (Cryptomus health-check ping, no action)
4. If status in `{"paid", "paid_over"}`: call `complete_payment(db, transaction, user, plan, rw_client)` (see service below). On success return 200. On `RemnawaveError` → send Telegram alert, return 500.
5. If status in `{"cancel", "wrong_amount", "fail", "wrong_amount_waiting"}` → `transaction.status = failed`, `await db.commit()`, return 200.

**Telegram alert on Remnawave failure:**
```python
token = await get_setting(db, "telegram_bot_token")
chat_id = await get_setting(db, "telegram_admin_chat_id")
await send_admin_alert(token, chat_id,
    f"⚠️ Webhook error: Remnawave unavailable\n"
    f"Transaction: {transaction.id}\nUser: {user.id}\n"
    f"Plan: {plan.label}\nError: {exc}"
)
```

---

### `GET /api/payments/history`

**Auth:** Required
**Query:** `SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 20`
Returns all transaction types (payment, trial_activation, etc.) with their actual `type` value.
`plan_name` = `transaction.plan.label` if `plan_id IS NOT NULL`, else `None`.

---

## Services

### `CryptomусClient` (`services/cryptomus_client.py`)

```python
@dataclass
class CryptomусInvoice:
    uuid: str    # Cryptomus invoice UUID → transaction.external_payment_id
    url: str     # Redirect URL for user → transaction.payment_url
    order_id: str
    status: str

class CryptomусClient:
    BASE_URL = "https://api.cryptomus.com/v1"

    def __init__(self, merchant_id: str, api_key: str) -> None:
        self._merchant_id = merchant_id
        self._api_key = api_key

    def _sign(self, body: dict) -> str:
        """md5(base64(compact_json_body) + api_key) for outgoing request signing."""
        encoded = base64.b64encode(json.dumps(body, separators=(",", ":")).encode()).decode()
        return hashlib.md5((encoded + self._api_key).encode()).hexdigest()

    async def create_invoice(
        self, amount: str, currency: str, order_id: str, url_callback: str
    ) -> CryptomусInvoice:
        """
        amount: decimal string, e.g. "200.00" (required by Cryptomus API).
        Request headers: merchant={merchant_id}, sign={_sign(body)}, Content-Type=application/json.
        Response JSON contains: result.uuid, result.url, result.order_id, result.status.
        """
```

### `TelegramAlertService` (`services/telegram_alert.py`)

```python
async def send_admin_alert(token: str | None, chat_id: str | None, message: str) -> None:
    """Fire-and-forget. No-ops if token or chat_id is None/empty. Swallows all failures."""
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

### `payment_service.py`

```python
async def calculate_final_price(
    db: AsyncSession, plan: Plan, user: User, promo_code_str: str | None
) -> tuple[int, PromoCode | None]:
    """Returns (final_price_rub, validated_promo_or_None). Raises HTTP 400 for invalid promo."""

async def get_pending_transaction(
    db: AsyncSession, user_id: uuid.UUID
) -> Transaction | None:
    """SELECT ... FOR UPDATE (blocking). Returns most recent pending tx or None."""

async def complete_payment(
    db: AsyncSession,
    transaction: Transaction,
    user: User,
    plan: Plan,
    rw_client: RemnawaveClient,
) -> None:
    """
    Atomically:
    1. GET remnawave user for current expire_at
    2. new_expire_at = max(expire_at, now) + timedelta(days=plan.duration_days)
    3. PATCH remnawave user: trafficLimitBytes=0, expireAt=new_expire_at
    4. Update local subscription fields directly (type, status, expires_at, traffic_limit_gb,
       synced_at) WITHOUT calling sync_subscription_from_remnawave — that function has an
       internal commit which would break atomicity. Instead, upsert the Subscription row
       manually, then call db.flush() (not commit).
    5. user.has_made_payment = True
    6. transaction.status = completed, transaction.completed_at = now
    7. transaction.days_added = plan.duration_days (explicit set)
    8. If transaction.promo_code_id IS NOT NULL:
       - SELECT promo_code FOR UPDATE (blocking, prevents max_uses race)
       - INSERT PromoCodeUsage(promo_code_id, user_id, used_at=now)
       - promo_code.used_count += 1
    9. await db.commit()  — single commit for entire payment completion
    Raises: RemnawaveError (or httpx.HTTPStatusError) if Remnawave call fails.
    Caller handles the exception: sends Telegram alert, returns 500.
    """
```

**Key atomicity note:** `complete_payment` does NOT call `sync_subscription_from_remnawave` because that function internally commits (which would split the payment completion into two separate transactions, creating a crash-recovery window). Instead, it updates the `Subscription` row directly and commits everything in one `db.commit()`.

---

## Error Handling Summary

| Scenario | HTTP | Cryptomus retry? |
|---|---|---|
| Invalid IP on webhook | 400 | No |
| Invalid HMAC on webhook | 400 | No |
| Transaction not found | 400 | No |
| Status "check" | 200 | — |
| Already completed | 200 | — |
| Remnawave unavailable | 500 | Yes |
| Payment failed/cancel/wrong_amount | 200 | — |

---

## Testing Strategy

**~22 new tests across 5 test files:**

| File | Tests |
|---|---|
| `tests/services/test_cryptomus_client.py` | create_invoice success (amount is str "200.00"), HMAC sign header correct, HTTP error bubbles up |
| `tests/services/test_telegram_alert.py` | message sent, failure swallowed, no-op on missing token, no-op on missing chat_id |
| `tests/services/test_payment_service.py` | price: no discount, new_user discount, promo discount, min-wins; pending dedup returns existing (FOR UPDATE); promo invalid → 400 |
| `tests/routers/test_payments_create.py` | no remnawave_uuid→409, rate_limited→429, plan_not_found→404, not_configured→503, duplicate_pending→200 is_existing=True, success→201 with payment_url |
| `tests/routers/test_payments_webhook.py` | invalid IP→400, invalid HMAC→400, status=check→200, already_completed→200, paid_success (all fields committed, single commit), remnawave_fail→500+alert+tx_still_pending, cancel→200 tx=failed |

All 55 existing tests must remain green.

---

## Task Breakdown

| # | Task | Files changed |
|---|---|---|
| 1 | `CryptomусClient` + `payment_url` migration | `services/cryptomus_client.py`, `alembic/versions/*_add_payment_url_to_transactions.py`, `tests/services/test_cryptomus_client.py` |
| 2 | `TelegramAlertService` | `services/telegram_alert.py`, `tests/services/test_telegram_alert.py` |
| 3 | `POST /api/payments` | `schemas/payment.py`, `services/payment_service.py`, `routers/payments.py` (create only), `config.py` (site_url), register in `main.py`, `tests/routers/test_payments_create.py` |
| 4 | `POST /api/payments/webhook` | extend `routers/payments.py` (webhook + complete_payment integration), extend `services/payment_service.py` (complete_payment), `tests/routers/test_payments_webhook.py` |
| 5 | `GET /api/payments/history` + smoke test | extend `routers/payments.py`, extend `schemas/payment.py`, Docker smoke, `git tag plan-3-complete` |
