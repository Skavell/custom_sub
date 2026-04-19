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

- **Primary path (webhook):** Remnawave sends `POST /api/webhooks/remnawave` with event `user.first_connected`. Backend validates HMAC-SHA256 signature, finds user by `remnawave_uuid`, writes `first_connected_at` from `data.userTraffic.firstConnectedAt` to DB. Instant, zero polling overhead.
- **Fallback path (API):** On every `GET /api/subscriptions/me`, if `user.first_connected_at` is still null, backend checks the cached Remnawave user data (TTL 5 min). If `firstConnectedAt` is not null there, it writes it to DB and returns `has_connected: true`. This catches any missed webhooks.

### DB Change

Add column to `users` table:

```sql
first_connected_at TIMESTAMPTZ NULL
```

Alembic migration required.

### New Setting

`remnawave_webhook_secret` — encrypted, empty by default. Exposed in admin panel under Remnawave > "Подключение к API". If empty, webhook endpoint returns 401.

Seed migration: insert setting with `is_secret=True`, value `""`.

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
    used_traffic_bytes: int          # NEW — from userTraffic.usedTrafficBytes
    first_connected_at: datetime | None  # NEW — from userTraffic.firstConnectedAt
```

Update `_parse_user` to read from `data["userTraffic"]` (gracefully handle missing key with `or {}`).

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
    has_connected: bool          # NEW
    traffic_used_bytes: int | None  # NEW — None for paid subscriptions
```

### `routers/remnawave_webhook.py` (new file)

`POST /api/webhooks/remnawave`

- Read raw body bytes via `Request.body()` before JSON parsing (required for HMAC).
- Validate `X-Remnawave-Signature` header: `HMAC-SHA256(raw_body, webhook_secret)`, compared with `hmac.compare_digest`.
- If secret not configured or signature invalid → 401.
- Parse JSON body into `RemnawaveWebhookPayload` (fields: `event: str`, `data: dict`).
- If `event != "user.first_connected"` → return 200 immediately (ignore other events gracefully).
- Extract `data["uuid"]` → query `User` by `remnawave_uuid`.
- If user found and `user.first_connected_at is None`:
  - Parse `data["userTraffic"]["firstConnectedAt"]` as datetime.
  - Write to DB.
- Return `{"ok": True}` with status 200 always (prevents Remnawave from retrying valid deliveries).

### `routers/subscriptions.py`

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
            # Update first_connected_at in DB if webhook was missed
            if current_user.first_connected_at is None and rw_data.get("first_connected_at"):
                current_user.first_connected_at = datetime.fromisoformat(rw_data["first_connected_at"])
                await db.commit()
                has_connected = True

            # Traffic only for trial
            if sub.type.value == "trial":
                traffic_used_bytes = rw_data.get("used_traffic_bytes")

    return _to_response(sub, has_connected=has_connected, traffic_used_bytes=traffic_used_bytes)
```

Update `_to_response` to accept and forward `has_connected` and `traffic_used_bytes`.

### `main.py`

Register new router:
```python
from app.routers import remnawave_webhook
app.include_router(remnawave_webhook.router)
```

### Alembic migrations (2 new)

1. `add_first_connected_at_to_users` — adds nullable `first_connected_at` column.
2. `seed_remnawave_webhook_secret` — inserts `remnawave_webhook_secret` setting with `is_secret=True`, value `""`.

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
  has_connected: boolean        // NEW
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

`TrialCard` traffic display:
```tsx
function TrafficDisplay({ sub }: { sub: SubscriptionResponse }) {
  if (sub.traffic_used_bytes === null || sub.traffic_limit_gb === null) {
    return <span>Трафик: {sub.traffic_limit_gb} ГБ (пробный лимит)</span>
  }
  const limitBytes = sub.traffic_limit_gb * 1024 ** 3
  const remainingBytes = Math.max(0, limitBytes - sub.traffic_used_bytes)
  const remainingGb = (remainingBytes / 1024 ** 3).toFixed(1)
  const limitGb = sub.traffic_limit_gb
  return <span>{remainingGb} из {limitGb} ГБ осталось</span>
}
```

Used inside the existing `<Zap>` row in `TrialCard`.

### `pages/admin/AdminSettingsPage.tsx`

- Add `'remnawave_webhook_secret'` to `REMNAWAVE_KEYS`.
- Add to `SETTING_LABELS`: `remnawave_webhook_secret: 'Секрет вебхука (WEBHOOK_SECRET_HEADER)'`.
- The existing `rw_api` filter (`key === 'remnawave_url' || key === 'remnawave_token'`) must be expanded to include `remnawave_webhook_secret`:
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
  → validate HMAC signature
  → find User by remnawave_uuid
  → write first_connected_at from userTraffic.firstConnectedAt

[Frontend] --GET /api/subscriptions/me--> Backend
  → read sub from DB
  → if remnawave_uuid set: check Redis cache (TTL 5 min)
    → if miss: call Remnawave GET /users/{uuid}
    → cache result
  → if first_connected_at null in DB but found in cache → write to DB
  → return SubscriptionResponse { has_connected, traffic_used_bytes }

[OnboardingCard] uses has_connected for step 3 done state
[TrialCard] uses traffic_used_bytes to show "X из Y ГБ осталось"
```

---

## Out of Scope

- Webhook retry handling (Remnawave retries automatically if we return non-2xx; we always return 200).
- Support for other webhook events (ignored gracefully).
- Traffic display for paid users (they have unlimited traffic, no change needed).
