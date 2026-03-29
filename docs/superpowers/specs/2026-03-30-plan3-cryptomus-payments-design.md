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
| `app/services/cryptomus_client.py` | httpx wrapper for Cryptomus REST API (create invoice, verify HMAC) |
| `app/services/telegram_alert.py` | Send admin alert messages via Telegram Bot API |
| `app/services/payment_service.py` | Business logic: price calculation, pending-invoice deduplication, transaction lifecycle |
| `app/routers/payments.py` | Three endpoints: create payment, webhook, history |

### New DB Settings (stored AES-encrypted via `settings` table)

| Key | Type | Description |
|---|---|---|
| `cryptomus_merchant_id` | sensitive | Cryptomus merchant UUID |
| `cryptomus_api_key` | sensitive | Cryptomus secret key for HMAC signing |
| `cryptomus_webhook_allowed_ips` | plain | JSON array of Cryptomus IP addresses, e.g. `["91.227.144.54", "91.227.144.55"]`. Empty array = skip IP check (for initial setup) |
| `telegram_admin_chat_id` | plain | Telegram chat/user ID to receive admin alerts |

### New Config Field

`settings.site_url` — base URL for constructing the webhook callback URL (e.g. `https://my.example.com`). Added to `app/config.py` `Settings` class.

---

## Endpoints

### `POST /api/payments`

**Auth:** Required (`get_current_user`)
**Rate limit:** 5 requests/minute per IP (Redis, same `check_rate_limit` helper)

**Request body:**
```json
{"plan_id": "uuid", "promo_code": "PROMO123"}
```
`promo_code` is optional; only `discount_percent` type codes are accepted here. `bonus_days` codes have their own endpoint (Plan 4).

**Guard order:**
1. `user.remnawave_uuid is None` → 409 `"Сначала активируйте пробный период"`
2. IP rate limit exceeded → 429
3. Plan not found or `is_active = false` → 404
4. Cryptomus not configured (merchant_id or api_key missing) → 503
5. Existing `pending` transaction for this user < 30 min old → 200 with existing `payment_url` (no new invoice)
6. Existing `pending` transaction ≥ 30 min old → mark `failed`, continue to create new

**Price calculation:**
- Base: `plan.price_rub`
- New user discount: if `not user.has_made_payment AND plan.name == "1_month" AND plan.new_user_price_rub IS NOT NULL` → candidate = `plan.new_user_price_rub`
- Promo discount: if valid `discount_percent` code provided → candidate = `round(plan.price_rub * (1 - value/100))`
- Final: `min(all candidates)` — lowest price wins
- Amount stored in `transaction.amount_rub`

**Cryptomus invoice creation:**
- Currency: `RUB` (Cryptomus handles conversion internally)
- `order_id = str(transaction.id)` — idempotency key
- `url_callback = settings.site_url + "/api/payments/webhook"`
- Transaction row created with `status=pending`, `external_payment_id=cryptomus_invoice_uuid`

**Response (200/201):**
```json
{"payment_url": "https://pay.cryptomus.com/...", "transaction_id": "uuid", "amount_rub": 200}
```

---

### `POST /api/payments/webhook`

**Auth:** None (public endpoint, CSRF-exempt)
**Source verification (order matters):**
1. IP allowlist check: `request.client.host` must be in `cryptomus_webhook_allowed_ips` setting. If the list is empty, skip this check. Failure → 400 (reason not disclosed)
2. HMAC-MD5 verification: `md5(base64(raw_body) + api_key)` must match `sign` field in payload. Failure → 400

**Processing logic:**
1. Find transaction by `order_id` from payload
2. If transaction not found → 400
3. If transaction already `completed` → 200 (idempotent)
4. If Cryptomus status == `paid`:
   a. `GET /users/{remnawave_uuid}` → current `expire_at`
   b. `new_expire_at = expire_at + timedelta(days=plan.duration_days)`
   c. `PATCH /users/{remnawave_uuid}` with `expireAt=new_expire_at`, `trafficLimitBytes=0` (unlimited — paid tier)
   d. `sync_subscription_from_remnawave(db, user, remnawave_user)` — update local subscription row
   e. `user.has_made_payment = True`
   f. `transaction.status = completed`, `transaction.completed_at = now`
   g. `await db.commit()`
   h. Return 200
5. If Remnawave call fails at step (a) or (c): transaction stays `pending`, send Telegram alert, return 500 (triggers Cryptomus retry)
6. If Cryptomus status == `failed` or `expired`: `transaction.status = failed`, return 200

**Telegram alert format on Remnawave failure:**
```
⚠️ Webhook error: Remnawave unavailable
Transaction: {transaction_id}
User: {user_id}
Plan: {plan_name}
Error: {exc}
```
Bot token: `settings["telegram_bot_token"]` (already stored from Plan 1).
Admin chat ID: `settings["telegram_admin_chat_id"]`.

---

### `GET /api/payments/history`

**Auth:** Required
**Response:** Last 20 transactions for the current user, ordered by `created_at DESC`.

```json
[
  {
    "id": "uuid",
    "type": "payment",
    "status": "completed",
    "amount_rub": 200,
    "plan_name": "1 месяц",
    "days_added": 30,
    "created_at": "2026-03-30T12:00:00Z",
    "completed_at": "2026-03-30T12:05:00Z"
  }
]
```

---

## Services

### `CryptomусClient`

Stateless httpx wrapper. Instantiated per-request from DB settings (same pattern as `RemnawaveClient`).

```python
class CryptomусClient:
    def __init__(self, merchant_id: str, api_key: str) -> None: ...
    async def create_invoice(self, amount: int, currency: str, order_id: str, url_callback: str) -> CryptomусInvoice: ...

@dataclass
class CryptomусInvoice:
    uuid: str        # Cryptomus invoice ID → stored as external_payment_id
    url: str         # Redirect URL for user
    order_id: str
    status: str
```

HMAC signature for requests: `md5(base64(json_body) + api_key)`, sent as `sign` header.

### `TelegramAlertService`

Simple fire-and-forget: `POST https://api.telegram.org/bot{token}/sendMessage`. Failures are logged and swallowed — never block the main flow.

```python
async def send_admin_alert(token: str, chat_id: str, message: str) -> None: ...
```

### `payment_service.py`

Contains pure business logic functions called by the router:
- `calculate_final_price(plan, user, promo_code_row | None) -> int`
- `get_or_create_pending_transaction(db, user, plan) -> tuple[Transaction, bool]` — returns (tx, is_new)
- `complete_payment(db, transaction, remnawave_client) -> None` — extends Remnawave + updates local state

---

## Error Handling Summary

| Scenario | HTTP | Cryptomus retry? |
|---|---|---|
| Invalid IP on webhook | 400 | No |
| Invalid HMAC on webhook | 400 | No |
| Transaction not found | 400 | No |
| Already completed | 200 | — |
| Remnawave unavailable | 500 | Yes (Cryptomus retries on 5xx) |
| Payment failed/expired | 200 | — |

---

## Testing Strategy

**~20 new tests across 5 test files:**

| File | Tests |
|---|---|
| `tests/services/test_cryptomus_client.py` | create_invoice success, HMAC sign correct, HTTP error bubbles up |
| `tests/services/test_telegram_alert.py` | message sent, failure swallowed |
| `tests/services/test_payment_service.py` | price calc (new user discount, promo, min logic), pending deduplication |
| `tests/routers/test_payments_create.py` | no remnawave_uuid→409, rate limited→429, plan not found→404, not configured→503, duplicate pending→200 with existing URL, success→201 |
| `tests/routers/test_payments_webhook.py` | invalid IP→400, invalid HMAC→400, already completed→200, paid success, remnawave failure→500+alert, payment failed→200 |

All 55 existing tests must remain green.

---

## Task Breakdown

| # | Task | Files |
|---|---|---|
| 1 | `CryptomусClient` | `services/cryptomus_client.py` + `tests/services/test_cryptomus_client.py` |
| 2 | `TelegramAlertService` | `services/telegram_alert.py` + `tests/services/test_telegram_alert.py` |
| 3 | `POST /api/payments` | `services/payment_service.py` + `routers/payments.py` (create only) + `tests/routers/test_payments_create.py` |
| 4 | `POST /api/payments/webhook` | extend `routers/payments.py` + `tests/routers/test_payments_webhook.py` |
| 5 | `GET /api/payments/history` + smoke test | extend `routers/payments.py` + Docker smoke + `git tag plan-3-complete` |
