# Payment Systems Admin Settings — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Overview

Add a dedicated "Платёжные системы" section to the admin settings page for configuring CryptoBot (and future providers). Add a payment provider selector to the subscription payment page, with the pay button disabled when no providers are active.

---

## Backend

### 1. New Setting: `cryptobot_enabled`

- Key: `cryptobot_enabled`
- Type: string `"true"` / `"false"`
- `is_sensitive`: false
- Seeded via Alembic migration with value `"true"` (assumes existing installs already have a token configured)

### 2. New Endpoint: `GET /api/payments/providers`

- Auth: requires authenticated user (`get_current_user`)
- Returns: `list[PaymentProviderInfo]`
- Logic: for each known provider, check if enabled (setting = `"true"`) AND token is not empty
- Response schema:

```python
class PaymentProviderInfo(BaseModel):
    name: str       # e.g. "cryptobot"
    label: str      # e.g. "CryptoBot"
    is_active: bool
```

- Always returns the full list of known providers (even inactive ones), so the frontend can show a "no providers" state.

### 3. `CreatePaymentRequest` — add `provider` field

```python
class CreatePaymentRequest(BaseModel):
    plan_id: uuid.UUID
    promo_code: str | None = None
    provider: str  # required, must match an active provider name
```

### 4. `factory.py` — `get_active_provider(db, provider_name: str)`

- Signature change: takes `provider_name: str`
- Validates: provider is known, enabled, and token is set
- Raises `HTTP 400` (not 503) if the named provider is inactive or unknown
- Raises `HTTP 503` only if the token is missing/misconfigured for a known+enabled provider

### 5. `payments.py` router — `create_payment`

- Passes `data.provider` to `get_active_provider(db, data.provider)`
- No other changes to the payment flow

---

## Frontend

### 6. `AdminSettingsPage.tsx` — new "Платёжные системы" section

New constant:
```ts
const PAYMENT_KEYS = new Set([
  'cryptobot_enabled',
  'cryptobot_token',
  'usdt_exchange_rate',
  'cryptobot_webhook_allowed_ips',
])
```

These keys are excluded from "Прочее".

New collapsible section **«Платёжные системы»** rendered before «OAuth провайдеры», using `OAuthProviderBlock`-style layout:

- **CryptoBot block** (uses existing `OAuthProviderBlock` component):
  - Toggle: `cryptobot_enabled`
  - Fields when expanded:
    - `cryptobot_token` — sensitive input, label «API токен CryptoBot»
    - `usdt_exchange_rate` — plain input, label «Курс USDT (руб.)»
    - `cryptobot_webhook_allowed_ips` — textarea (one IP per line), label «Разрешённые IP вебхуков»

Labels added to `SETTING_LABELS`, hints added to `SETTING_HINTS` where needed.

### 7. New type in `src/types/api.ts`

```ts
export interface PaymentProviderInfo {
  name: string
  label: string
  is_active: boolean
}
```

### 8. `SubscriptionPage.tsx` — provider selector + payment guard

- New query: `useQuery(['payment-providers'], () => api.get<PaymentProviderInfo[]>('/api/payments/providers'))`
- Logic:
  - `activeProviders = providers.filter(p => p.is_active)`
  - If `activeProviders.length === 0`: pay button is disabled, show message «Оплата временно недоступна»
  - If `activeProviders.length === 1`: no dropdown shown, provider is auto-selected
  - If `activeProviders.length >= 2`: show `<select>` dropdown above the pay button
- `selectedProvider` state (string) — initialized to first active provider on load
- `CreatePaymentRequest` sent with `provider: selectedProvider`

---

## Migration chain

New migration appended after current tail (`e5f6a7b8c9d0` or whatever the current head is):

```
seed: cryptobot_enabled = "true"
```

---

## Out of scope

- Adding a second payment provider (Stripe, YooMoney, etc.) — architecture supports it but no implementation
- Per-user provider preference persistence
- Admin-side transaction filtering by provider
