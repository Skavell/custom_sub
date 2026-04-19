# Design: Onboarding First-Connection Step & Trial Traffic Display

**Date:** 2026-04-19

---

## Overview

Two related features:

1. **Onboarding step "Установить приложение"** should be marked done only when the user has actually connected to the VPN for the first time — not just by visiting the `/install` page.
2. **TrialCard on the home page** should show real remaining traffic fetched from Remnawave instead of a hardcoded "30 ГБ".

---

## Feature 1: First-Connection Tracking

### Approach

Approach C — webhook as primary, API fallback on subscription fetch.

- **Primary path (webhook):** Remnawave sends `POST /api/webhooks/remnawave` with event `user.first_connected`. Backend validates HMAC-SHA256 signature, finds user by `remnawave_uuid`, writes `first_connected_at` from `data.userTraffic.firstConnectedAt` to DB.
- **Fallback path (API):** On every `GET /api/subscriptions/me`, if `user.first_connected_at` is still null, backend checks the cached Remnawave user data (TTL 5 min). If `firstConnectedAt` is not null there, it writes it to DB and returns `has_connected: true`. This catches any missed webhooks.
- **Edge case — webhook arrives before `remnawave_uuid` is set:** Extremely unlikely (trial activation happens before any connection), but if it occurs, the user won't be found by `remnawave_uuid` and the write is skipped. The fallback path on subscription fetch will catch it on next page load. No retry logic needed.

### DB Change

Add column to `users` table:

```sql
first_connected_at TIMESTAMPTZ NULL
```

Alembic migration required.

### New Setting

`remnawave_webhook_secret` — stored in DB, seeded with `is_sensitive=False` and `{"value": ""}`. The `SettingRow` save path in the admin will encrypt it when the admin first sets a real value (same pattern as other settings). If the value is empty after fetching via `get_setting_decrypted`, the webhook endpoint returns 401.

Exposed in admin panel: add to `REMNAWAVE_KEYS` (this automatically excludes it from `otherSettings` as well) and add to `rw_api` filter so it renders under "Подключение к API" alongside URL and token.

---

## Feature 2: Real Traffic Display

Remnawave user object includes `userTraffic.usedTrafficBytes` and `trafficLimitBytes`. We fetch this once per 5 minutes (Redis cache) and include it in the subscription response.

For trial users: display `"X из Y ГБ осталось"` calculated on the frontend.
For paid users: `traffic_used_bytes` is `null` — display unchanged ("Безлимитный трафик").

---

## Backend Changes

### `services/remnawave_client.py`

Extend `RemnawaveUser` dataclass:

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
    used_traffic_bytes: int           # NEW — from userTraffic.usedTrafficBytes (default 0)
    first_connected_at: datetime | None  # NEW — from userTraffic.firstConnectedAt (nullable)
```

Update `_parse_user`: read `user_traffic = data.get("userTraffic") or {}`. Parse `firstConnectedAt` with a null guard:

```python
fca_str = user_traffic.get("firstConnectedAt")
first_connected_at = datetime.fromisoformat(fca_str.replace("Z", "+00:00")) if fca_str else None
```

### `models/user.py`

```python
first_connected_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

### `schemas/subscription.py`

```python
class SubscriptionResponse(BaseModel):
    type: str
    status: str
    started_at: datetime
    expires_at: datetime
    traffic_limit_gb: int | None
    days_remaining: int
    has_connected: bool           # NEW
    traffic_used_bytes: int | None  # NEW — None for paid subscriptions
```

### `routers/remnawave_webhook.py` (new file)

`POST /api/webhooks/remnawave`

**Signature validation:**
- Read raw body as bytes via `await Request.body()` before JSON parsing (required for correct HMAC).
- Fetch `X-Remnawave-Signature` header.
- Fetch `remnawave_webhook_secret` via `get_setting_decrypted`. If empty → 401.
- Compute: `hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()` (secret first, body second).
- Compare with `hmac.compare_digest(computed, header_signature)`. If mismatch → 401.

**Logic:**
1. Parse body JSON. If `event != "user.first_connected"` → return 200 (ignore gracefully).
2. Extract `data["uuid"]` → query `User` by `remnawave_uuid`.
3. If user not found → return 200 (handles race condition where webhook arrives before uuid is set; fallback covers it).
4. If `user.first_connected_at is None`:
   - Read `fca_str = data.get("userTraffic", {}).get("firstConnectedAt")`.
   - If `fca_str` is null or missing → skip write, return 200 (do not use `now()` fallback).
   - Otherwise parse and write `user.first_connected_at = datetime.fromisoformat(fca_str...)`.
5. Return `{"ok": True}` with status 200 always.

### `routers/subscriptions.py`

Update `_to_response` signature:

```python
def _to_response(
    sub,
    has_connected: bool = False,
    traffic_used_bytes: int | None = None,
) -> SubscriptionResponse:
    ...
    return SubscriptionResponse(
        ...,
        has_connected=has_connected,
        traffic_used_bytes=traffic_used_bytes,
    )
```

`POST /api/subscriptions/trial` calls `_to_response(sub)` — defaults `has_connected=False, traffic_used_bytes=None` are correct at activation time (user has never connected yet).

Update `GET /api/subscriptions/me`:

```python
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
                    rw_data = None
            else:
                rw_data = None

        if rw_data:
            # Fallback: write first_connected_at if webhook was missed.
            # Note: if webhook already wrote it, first_connected_at is not None
            # so this branch is skipped — no cache invalidation needed.
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

Remnawave is unreachable → `rw_data = None` → response still returns with `has_connected` from DB and `traffic_used_bytes=None`. Never blocks the response.

### `main.py`

```python
from app.routers import remnawave_webhook
app.include_router(remnawave_webhook.router)
```

### Alembic migrations (2 new)

1. `add_first_connected_at_to_users` — adds nullable `first_connected_at TIMESTAMPTZ` column to `users`.
2. `seed_remnawave_webhook_secret` — inserts setting `remnawave_webhook_secret` with `is_sensitive=False`, `{"value": ""}`, using `ON CONFLICT DO NOTHING` pattern from existing seed migrations.

---

## Frontend Changes

### `types/api.ts`

```typescript
export interface SubscriptionResponse {
  type: 'trial' | 'paid'
  status: 'active' | 'expired' | 'disabled'
  started_at: string
  expires_at: string
  traffic_limit_gb: number | null
  days_remaining: number
  has_connected: boolean         // NEW
  traffic_used_bytes: number | null  // NEW
}
```

### `components/OnboardingCard.tsx`

- Remove `LS_INSTALL_VISITED`, `installVisited` entirely.
- Add `hasConnected: boolean` to `Props`.
- Step 3: `done: hasConnected` (was `installVisited && hasSubscription`).
- Step 4: `locked: !hasConnected` (was `!(installVisited && hasSubscription)`).

### `pages/HomePage.tsx`

`OnboardingCard` call:
```tsx
<OnboardingCard
  hasMadePayment={user?.has_made_payment ?? false}
  hasSubscription={sub !== null && sub !== undefined}
  hasConnected={sub?.has_connected ?? false}
  onActivateTrial={scrollToTrialCta}
/>
```

`TrialCard` traffic display — replace hardcoded `<span>Трафик: 30 ГБ (пробный лимит)</span>` with:

```tsx
function TrafficDisplay({ sub }: { sub: SubscriptionResponse }) {
  if (sub.traffic_used_bytes === null || sub.traffic_limit_gb === null) {
    // Fallback: traffic_limit_gb null means no data at all
    const gb = sub.traffic_limit_gb
    return <span>{gb != null ? `Трафик: ${gb} ГБ (пробный лимит)` : 'Трафик: недоступен'}</span>
  }
  const limitBytes = sub.traffic_limit_gb * 1024 ** 3
  const remainingBytes = Math.max(0, limitBytes - sub.traffic_used_bytes)
  const remainingGb = (remainingBytes / 1024 ** 3).toFixed(1)
  return <span>{remainingGb} из {sub.traffic_limit_gb} ГБ осталось</span>
}
```

Used inside the existing `<Zap>` row in `TrialCard`.

### `pages/admin/AdminSettingsPage.tsx`

- Add `'remnawave_webhook_secret'` to `REMNAWAVE_KEYS` (this also auto-excludes it from `otherSettings`).
- Add to `SETTING_LABELS`: `remnawave_webhook_secret: 'Секрет вебхука (WEBHOOK_SECRET_HEADER)'`.
- Expand `rw_api` filter:
  ```typescript
  const rw_api = remnawave.filter(
    s => s.key === 'remnawave_url' ||
         s.key === 'remnawave_token' ||
         s.key === 'remnawave_webhook_secret'
  )
  ```

---

## Data Flow Summary

```
[Remnawave] --webhook user.first_connected--> POST /api/webhooks/remnawave
  → validate HMAC-SHA256: hmac.new(secret, raw_body, sha256).hexdigest()
  → if firstConnectedAt present: find User by remnawave_uuid, write to DB
  → always return 200

[Frontend] --GET /api/subscriptions/me--> Backend
  → read sub + user.first_connected_at from DB
  → if remnawave_uuid set: Redis cache (rw:user_data:{id}, TTL 5 min)
    → if miss: call Remnawave GET /users/{uuid} (non-blocking on failure)
  → if first_connected_at null in DB but found in cache → write to DB
  → return SubscriptionResponse { has_connected, traffic_used_bytes }

[OnboardingCard] uses has_connected for step 3 done state
[TrialCard] uses traffic_used_bytes to show "X из Y ГБ осталось"
```

---

## Out of Scope

- Webhook retry handling (Remnawave retries if non-2xx; we always return 200).
- Support for other webhook events (ignored gracefully).
- Traffic display for paid users (unlimited, no change needed).
