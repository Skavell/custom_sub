# Payment Systems Admin Settings — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Overview

Add a dedicated "Платёжные системы" section to the admin settings page for configuring CryptoBot (and future providers). Add a payment provider selector to the subscription payment page, with the pay button disabled when no providers are active.

---

## Backend

### 1. New Setting: `cryptobot_enabled`

- Key: `cryptobot_enabled`, value `"true"`/`"false"`, not sensitive
- Seeded via Alembic migration with value `"true"`
- **Absent/empty value is treated as `"false"`** — active check is strict equality `== "true"`. This is intentional and differs from the `OAuthToggle` frontend convention (`!== "false"`). Both backend and frontend code for this feature must use strict `== "true"` / `=== "true"`.
- Pre-migration absence → backend returns `is_active: false` → pay button disabled. Safe failure mode.

### 2. Known providers registry in `factory.py`

```python
_KNOWN_PROVIDERS = ["cryptobot"]

_PROVIDER_LABELS: dict[str, str] = {
    "cryptobot": "CryptoBot",
}
```

### 3. Shared helper `_is_provider_active(db, name) → bool`

A private async helper in `factory.py` that reads the enabled flag and token for a given provider name and returns whether it is active. Used by both `get_active_provider` and the `/providers` endpoint to ensure consistent logic.

Both conditions — disabled (`cryptobot_enabled != "true"`) AND token not set — produce `is_active: False`. These are collapsed intentionally: from the user's perspective both mean "can't pay." Admins can see the token field in the settings panel to diagnose which condition applies.

```python
async def _is_provider_active(db: AsyncSession, name: str) -> bool:
    # For "cryptobot": cryptobot_enabled == "true" AND cryptobot_token not empty
    ...
```

### 4. New Endpoint: `GET /api/payments/providers`

- Auth: `get_current_user` (regular authenticated users — not admin-only)
- Intended consumers: `SubscriptionPage` for regular users
- Returns full list of known providers, including inactive — so frontend can show disabled state
- `is_active` visibility to non-admin users is intentional and not a security concern
- Schema placed in `backend/app/schemas/payment.py` (file already exists):

```python
class PaymentProviderInfo(BaseModel):
    name: str
    label: str
    is_active: bool
```

### 5. `CreatePaymentRequest` — add optional `provider` field

```python
provider: str = "cryptobot"  # default for backward compat with old clients that omit the field
```

`create_payment` response (`PaymentResponse`) does not echo back `provider` — no change to response schema.

### 6. `factory.py` — `get_active_provider(db, provider_name: str)`

Three mutually exclusive conditions checked in order:

1. `provider_name not in _KNOWN_PROVIDERS` → `HTTP 400` ("Неизвестная платёжная система")
2. `cryptobot_enabled != "true"` → `HTTP 400` ("Платёжная система отключена")
3. Token is empty/None (enabled but not configured) → `HTTP 503` ("Платёжная система не настроена")

Uses `_is_provider_active` from §3 for step 2.

### 7. Deduplication path in `create_payment`

Existing pending tx is returned early (before provider resolution) regardless of `provider` field.
**MVP assumption:** only one provider exists; deduplication is provider-agnostic by design. This is a known limitation to document when a second provider is added.

### 8. Webhook IP storage format

The existing `payments.py` webhook handler uses `json.loads(cryptobot_webhook_allowed_ips)` expecting a JSON array.

Storage format: JSON array string — `'["1.2.3.4","5.6.7.8"]'`

Backend reads the setting as-is with `json.loads`. New `WebhookIPsSettingRow` frontend component handles serialization (see §11).

---

## Frontend

### 9. `AdminSettingsPage.tsx`

New constant:
```ts
const PAYMENT_KEYS = new Set([
  'cryptobot_enabled',
  'cryptobot_token',
  'usdt_exchange_rate',
  'cryptobot_webhook_allowed_ips',
])
```

**Note:** when adding a second provider in the future, its setting keys must be added here manually to prevent them appearing in «Прочее».

The `otherSettings` filter must add `!PAYMENT_KEYS.has(s.key)`.

New collapsible section **«Платёжные системы»** before «OAuth провайдеры». Uses a **custom CryptoBot block** (NOT `OAuthProviderBlock` — that component only supports plain text/password inputs):

- Header row: **`ToggleSettingRow`** for `cryptobot_enabled` (NOT `OAuthToggle`) + chevron expand button
  - `ToggleSettingRow` already uses `value === 'true'` semantics, matching the backend's strict `== "true"` check. This avoids the absent=ON footgun of `OAuthToggle`.
- Expanded body:
  - `OAuthField` — `cryptobot_token`, `sensitive=true`, label «API токен CryptoBot»
  - `OAuthField` — `usdt_exchange_rate`, `sensitive=false` (plain text, no masking), label «Курс USDT (руб.)», hint «Число, например 90.5»
  - `WebhookIPsSettingRow` — `cryptobot_webhook_allowed_ips`, label «Разрешённые IP вебхуков», hint «Один IP на строку. Если пусто — разрешены все IP.»

Loading and error states: follow the same patterns as other `OAuthField`/`OAuthToggle` usages in the existing admin settings page.

### 10. New type in `src/types/api.ts`

```ts
export interface PaymentProviderInfo {
  name: string
  label: string
  is_active: boolean
}
```

### 11. `WebhookIPsSettingRow` component (inline in `AdminSettingsPage.tsx`)

Textarea, one IP per line.

```ts
// Load — defensive parse (handles legacy empty or non-JSON values)
const loadIPs = (raw: string): string => {
  try { return (JSON.parse(raw) as string[]).join('\n') }
  catch { return raw }
}

// Save
const saveIPs = (text: string): string =>
  JSON.stringify(text.split('\n').map(s => s.trim()).filter(Boolean))
```

No lowercasing — IP addresses are case-sensitive for IPv6. Renders with save button (same pattern as `TextareaSettingRow`).

### 12. `SubscriptionPage.tsx` — provider selector + payment guard

```ts
const { data: providers = [], isLoading: providersLoading, isError: providersError } =
  useQuery({
    queryKey: ['payment-providers'],
    queryFn: () => api.get<PaymentProviderInfo[]>('/api/payments/providers'),
  })

const [selectedProvider, setSelectedProvider] = useState<string | null>(null)

// Sync selectedProvider when providers change.
// Only resets if: (a) no selection yet, or (b) current selection is no longer in active set.
// Preserves user's manual selection on background refetches.
useEffect(() => {
  const active = providers.filter(p => p.is_active)
  const stillValid = selectedProvider && active.some(p => p.name === selectedProvider)
  if (!stillValid) {
    setSelectedProvider(active[0]?.name ?? null)
  }
}, [providers])  // intentionally omit selectedProvider from deps to avoid infinite loop
```

Pay button logic:
- `providersLoading` → disabled
- `providersError` → disabled + «Не удалось загрузить платёжные системы»
- `activeProviders.length === 0` → disabled + «Оплата временно недоступна»
- `activeProviders.length === 1` → no dropdown, auto-selected
- `activeProviders.length >= 2` → `<select>` dropdown above pay button

On submit — **hard guard**:
```ts
if (!selectedProvider) return  // should never reach here if button is disabled correctly
// send: { ..., provider: selectedProvider }
```

Frontend always sends the actual `selectedProvider` value — never falls back to a hardcoded default.

---

## Migration chain

New migration appended after current tail. Seeds `cryptobot_enabled = "true"`.

---

## Out of scope

- Adding a second payment provider — architecture supports it but no implementation
- Per-user provider preference persistence
- Admin-side transaction filtering by provider
