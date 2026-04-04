# Skavellion — VPN Web Service Design Spec

**Date:** 2026-03-29
**Status:** Approved
**Domain:** my.example.com

---

## Overview

A web service to replace the Telegram bot for managing VPN (tunnel) subscriptions. The site allows users to register, activate a trial, pay for a subscription, and install the VPN client — all without Telegram. The Telegram bot continues to run in parallel during the transition period.

The service integrates with the **Remnawave** panel (v2.4.4) as the source of truth for subscription state. The website maintains a local database that mirrors relevant Remnawave data and can be manually synced by the admin.

**Target scale:** 50–1000 users. Russian language (ru locale). Prices in RUB. Payments via cryptocurrency (Cryptomus).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| Package manager | uv (virtual environment: `.venv`) |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, Shadcn/ui, TanStack Query, React Router v6 |
| Database | PostgreSQL 16 |
| Cache / Sessions | Redis 7 |
| Reverse proxy | Nginx (SSL termination, routing) |
| Deployment | Docker Compose (5 services: nginx, backend, frontend, postgres, redis) |
| External APIs | Remnawave API, Cryptomus, Telegram Bot API, OAuth (Telegram/Google/VK) |

---

## Architecture

```
User (Browser/Mobile)
        ↕ HTTPS
    Nginx
    ├── /api/* → FastAPI backend (port 8000)
    └── /* → React SPA (port 3000, served as static in production)

FastAPI backend
    ├── PostgreSQL (data)
    ├── Redis (JWT blacklist, rate limiting, email tokens, API cache)
    ├── Remnawave API (create/sync users and subscriptions)
    ├── Cryptomus API (create payments, receive webhooks)
    ├── Telegram Bot API (support notifications)
    └── OAuth providers (Telegram, Google, VK)
```

All 5 Docker services share an internal network. The backend communicates with Remnawave over HTTPS.

---

## Design System

- **Theme:** Dark, single theme (no light mode)
- **Background:** `#080d12`
- **Sidebar/cards:** `#0d1520`
- **Accent:** Cyan gradient `#06b6d4 → #0891b2`
- **Text:** `#e2e8f0` (primary), `#94a3b8` (secondary), `#475569` (muted)
- **Borders:** `rgba(6,182,212,0.15)` for accent, `rgba(255,255,255,0.07)` for neutral
- **Radius:** 14px cards, 10px inputs/buttons
- **Typography:** System font stack
- **Brand name:** Skavellion (no "VPN" suffix anywhere in UI — use "туннель")
- **Navigation desktop:** Left sidebar (220px). Mobile: bottom navigation bar.
- **Responsive:** Mobile-first, works on phone/tablet/desktop.

---

## Database Schema

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| display_name | VARCHAR | |
| avatar_url | VARCHAR | nullable |
| is_admin | BOOLEAN | default false |
| remnawave_uuid | UUID | nullable, set on trial activation |
| has_made_payment | BOOLEAN | default false — used for new user discount |
| subscription_conflict | BOOLEAN | default false — set when two active paid subscriptions collide on Telegram link |
| created_at | TIMESTAMPTZ | |
| last_seen_at | TIMESTAMPTZ | |

### `auth_providers`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users | |
| provider | ENUM | telegram / google / vk / email |
| provider_user_id | VARCHAR | e.g. Telegram ID, Google sub |
| provider_username | VARCHAR | nullable (e.g. Telegram @username) |
| password_hash | VARCHAR | nullable, only for email provider |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** `(provider, provider_user_id)`

### `subscriptions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users | **UNIQUE** — one subscription record per user |
| type | ENUM | trial / paid |
| status | ENUM | active / expired / disabled |
| started_at | TIMESTAMPTZ | |
| expires_at | TIMESTAMPTZ | |
| traffic_limit_gb | INTEGER | null = unlimited (paid); 30 for trial |
| synced_at | TIMESTAMPTZ | last sync with Remnawave |

**Unique constraint:** `user_id` — one active subscription row per user. Status transitions update this row in place.

### `plans`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR | e.g. "1_month" |
| label | VARCHAR | display name, e.g. "1 месяц" |
| duration_days | INTEGER | 30 / 90 / 180 / 365 |
| price_rub | INTEGER | regular price in RUB |
| new_user_price_rub | INTEGER | nullable — discounted price for first-time buyers. **Business rule: only enforced at service level for the 1-month plan.** The column exists on all plans for future flexibility, but the service checks `plan.name = "1_month" AND NOT user.has_made_payment` before applying it. |
| is_active | BOOLEAN | |
| sort_order | INTEGER | |

Initial data:
- 1 месяц: 200₽ (new user: 100₽), 30 days
- 3 месяца: 590₽, 90 days
- 6 месяцев: 1100₽, 180 days
- 1 год: 2000₽, 365 days

### `transactions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users | |
| type | ENUM | trial_activation / payment / promo_bonus / manual |
| plan_id | UUID FK → plans | nullable |
| promo_code_id | UUID FK → promo_codes | nullable |
| amount_rub | INTEGER | nullable (0 for non-payment) |
| days_added | INTEGER | how many days were added |
| payment_provider | VARCHAR | cryptomus / manual / null |
| external_payment_id | VARCHAR | Cryptomus invoice ID — **UNIQUE** constraint for idempotency |
| status | ENUM | pending / completed / failed |
| description | VARCHAR | human-readable, e.g. "Оплата тарифа 3 месяца" |
| created_at | TIMESTAMPTZ | not null, default now() |
| completed_at | TIMESTAMPTZ | nullable — set when status transitions to completed or failed |
| updated_at | TIMESTAMPTZ | not null, default now(), auto-updated via trigger on every row change |

### `promo_codes`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| code | VARCHAR UNIQUE | case-insensitive, normalized to uppercase on save |
| type | ENUM | discount_percent / bonus_days |
| value | INTEGER | percent (0–100) or days |
| max_uses | INTEGER | null = unlimited |
| used_count | INTEGER | |
| valid_until | TIMESTAMPTZ | nullable |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

### `promo_code_usages`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| promo_code_id | UUID FK | |
| user_id | UUID FK | |
| used_at | TIMESTAMPTZ | |

**Unique constraint:** `(promo_code_id, user_id)` — one use per user

### `articles`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| slug | VARCHAR UNIQUE | URL-friendly |
| title | VARCHAR | |
| content | TEXT | Markdown |
| preview_image_url | VARCHAR | nullable |
| is_published | BOOLEAN | |
| sort_order | INTEGER | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `settings`
| Column | Type | Notes |
|---|---|---|
| key | VARCHAR PK | |
| value | JSONB | |
| is_sensitive | BOOLEAN | sensitive values stored AES-256 encrypted within the JSONB value |
| updated_at | TIMESTAMPTZ | |

Initial settings keys:
- `remnawave_url` — Remnawave API base URL
- `remnawave_token` — API token (sensitive, encrypted)
- `remnawave_squad_uuids` — squad UUID(s) for new users
- `remnawave_external_squad_uuid` — external squad UUID
- `remnawave_traffic_limit` — paid users traffic limit in bytes (0 = unlimited)
- `remnawave_trial_traffic_limit_bytes` — trial traffic limit (30 * 1024^3)
- `remnawave_trial_days` — trial duration (3)
- `telegram_bot_token` — (sensitive, encrypted) for support notifications only
- `telegram_support_chat_id` — where to send support messages
- `cryptomus_merchant_id` — (sensitive, encrypted)
- `cryptomus_api_key` — (sensitive, encrypted)
- `support_telegram_url` — public Telegram link for support
- `support_email` — support email address

**Note on Telegram bot token:** The token is stored **only** in the encrypted `settings` table (not in `.env`). The `.env` file contains only infrastructure secrets (DB URL, encryption key, OAuth credentials). This prevents duplication and ensures the admin panel is the single source of truth for bot configuration.

---

## Authentication

### Providers
- **Telegram OAuth** — primary, large button. Uses Telegram Login Widget.
- **Google OAuth 2.0** — secondary.
- **VK OAuth 2.0** — secondary.
- **Email + password** — tertiary. Registration sends email verification link (token stored in Redis, 24h TTL).

### Session Management
- JWT access token (15 min) + refresh token (30 days) stored as **httpOnly, SameSite=Strict cookies**.
- **Refresh token rotation:** Each use of a refresh token issues a new refresh token and invalidates the old one (stored in Redis as `refresh:{token_hash} → user_id`). This prevents session fixation.
- On logout: access token hash added to Redis blacklist (TTL = remaining token lifetime). Refresh token deleted from Redis.
- Rate limiting on auth endpoints: 10 requests/minute per IP (Redis-backed).

### Multiple Auth Methods per Account
Users can link multiple providers to a single account (e.g. register via Telegram, then link Google). Managed on the Profile page. At least one provider must remain linked at all times.

### User Sync from Telegram Bot
Existing bot users have Remnawave usernames like `10_515172616` (where `515172616` is the Telegram ID). When a user logs in via Telegram OAuth:
1. Check `auth_providers` for existing row with this Telegram ID. If found → normal login.
2. If not found: call `GET /users/by-telegram-id/{telegram_id}` (confirmed endpoint in Remnawave API). Returns the Remnawave user whose `telegramId` field matches.
3. If found in Remnawave: create local user, link `auth_providers`, set `remnawave_uuid`, sync subscription data (type, status, `expireAt`, `trafficLimitBytes`).
4. If not found in Remnawave: new user, no prior subscription.

### Conflict Resolution (linking Telegram to an existing email account)
When a user with an email account links their Telegram, and that Telegram has a Remnawave subscription:
- **If Telegram subscription expires later** → switch `remnawave_uuid` to the Telegram user's UUID, sync subscription.
- **If current account subscription expires later** → keep current UUID, no change.
- **If both are paid and active (neither has expired)** → flag conflict: set a `subscription_conflict = true` flag on the user record. Show a warning banner on the Profile page. In the admin panel, the admin can choose which Remnawave UUID to keep (the other user in Remnawave is left untouched — it's the admin's responsibility to clean it up manually).

---

## Subscription Logic

### Subscription State Representation
The `subscriptions` table has a `UNIQUE(user_id)` constraint. **A missing row means `no_subscription`** — no sentinel row is created on registration. Every query that reads subscription state must handle the case where no row exists for a user. Helper function `get_user_subscription(user_id) → Subscription | None` is used everywhere; `None` means `no_subscription`.

### States
`no_subscription` (no row) → `trial` → `paid` → `expired`

Transitions:
- `no_subscription → trial`: trial activation creates the row
- `trial → paid`: payment or bonus_days promo code updates the row
- `paid → paid`: renewal updates `expires_at` in place
- `expired → paid`: payment updates status and `expires_at`
- Any state with `remnawave_uuid` set: sync can update the row at any time

### Trial Activation
- Available only to users with `remnawave_uuid IS NULL` (never activated a trial).
- One trial per account. Additionally, if a Telegram ID is linked, Remnawave is queried to ensure no prior trial exists for that Telegram ID.
- **Check order:** (1) check `remnawave_uuid IS NULL` on the user, (2) if Telegram linked, check Remnawave for prior trial, (3) check IP rate limit (max 3 per IP per 24h, Redis-backed). Checks 1 and 2 run first to avoid consuming IP rate-limit slots for already-rejected requests.
- Creates user in Remnawave: `username = "ws_" + str(user.id)[:8]` (first 8 chars of UUID, giving a short alphanumeric suffix like `ws_4a1b2c3d`). Remnawave usernames must be unique; the backend verifies uniqueness before creation and retries with a longer suffix if needed.
- Stores `remnawave_uuid` on the user record.
- Records a `trial_activation` transaction.

### Remnawave Username Format
`ws_{user_id[:8]}` — "ws" prefix (website) + first 8 hex characters of the user's UUID. Example: `ws_4a1b2c3d`. If collision detected (unlikely), use first 12 characters.

### Payment Flow
1. **Prerequisite:** User must have `remnawave_uuid` set (trial activated at some point). An **expired** trial is acceptable — the user can still pay to reactivate. The check is `remnawave_uuid IS NOT NULL`, not `status = active`.
2. User selects a plan, optionally applies a `discount_percent` promo code.
3. **New user discount:** Applied if `has_made_payment = false` AND `plan.name = "1_month"` AND `plan.new_user_price_rub IS NOT NULL`.
4. **Concurrent payment guard:** Before creating a Cryptomus invoice, check for any `pending` transaction for this user. If one exists and was created less than 30 minutes ago, return its existing payment URL (no new invoice). If a `pending` transaction is 30+ minutes old, mark it `failed` (set `completed_at = now()`) and proceed to create a new invoice. This handles abandoned sessions without orphaned transactions accumulating.
5. Backend creates a Cryptomus invoice:
   - Amount: calculated in USDT using a cached exchange rate (fetched from a public rate API, cached in Redis for 5 minutes). RUB amount is shown to the user for clarity; the actual charge is in USDT equivalent.
   - `order_id`: transaction UUID.
   - `url_callback`: `https://my.example.com/api/payments/webhook`.
6. `transactions` row created with `status = pending`, `external_payment_id` = Cryptomus invoice UUID.
7. User redirected to Cryptomus payment URL.
8. **Webhook processing** (`POST /api/payments/webhook`):
   a. Verify Cryptomus HMAC signature. Reject if invalid.
   b. Check source IP against Cryptomus published IP allowlist. Reject if not listed.
   c. Check `status = paid` in payload.
   d. Look up transaction by `external_payment_id`. If not found or already `completed`, return 200 immediately (idempotency — `external_payment_id` has a UNIQUE constraint).
   e. Extend subscription in Remnawave: `PATCH /users/{remnawave_uuid}` with `trafficLimitBytes = 0`, `expireAt = max(current_expire, now) + duration_days`.
   f. If Remnawave call fails: mark transaction as `failed`, send alert to admin via Telegram bot, return 500 so Cryptomus retries later.
   g. If Remnawave call succeeds: update local subscription, set `has_made_payment = true`, mark transaction `completed`, set `completed_at`.
9. User sees updated subscription on next page load.

### Promo Codes
- **Type 1 — discount_percent:** Applied at checkout page only. Reduces final price. Cannot be combined with new user discount (whichever gives lower price wins).
- **Type 1 — discount_percent + new user discount stacking:** Both discounts are calculated from `price_rub` independently. `discount_percent` gives `price_rub * (1 - value/100)`. New user discount gives `new_user_price_rub`. The **lower of the two** is used as the final price. `amount_rub` in the transaction stores that final amount. Example: 1-month plan 200₽, new user price 100₽, 20% promo → promo gives 160₽, new user gives 100₽ → final price 100₽.
- **Type 2 — bonus_days:**
  - **With payment:** when user enters a `bonus_days` code at checkout, the code's ID is stored in the `transactions.promo_code_id` column at invoice creation time (before redirecting to Cryptomus). When the webhook fires and the payment succeeds, the handler reads `transaction.promo_code_id`, applies the bonus via a second Remnawave PATCH after the subscription extension PATCH. Base date for bonus: fresh `expireAt` from the first PATCH response.
  - **Standalone (no payment):** endpoint `POST /api/promo/apply` — applies the code to the user's current subscription. Requires `remnawave_uuid IS NOT NULL`. **If the subscription is expired:** bonus days are added on top of the current (past) `expireAt` from Remnawave, effectively re-activating the subscription. This is intentional — bonus codes act as gifts even for lapsed users. Base date: fresh `GET /users/{remnawave_uuid}` to avoid using a stale local value. Records a `promo_bonus` transaction. Accessible on the Subscription page.
- **Atomic use check:** Promo code application uses a DB transaction with `SELECT FOR UPDATE` on the `promo_codes` row. Inserts `promo_code_usages` and increments `used_count` atomically before calling Remnawave, to prevent race conditions on `max_uses`.

### Manual Sync (Admin)
- Admin presses "Sync" button for one user or all users.
- Backend calls `GET /users/{remnawave_uuid}` for each user.
- **Traffic limit mapping:** Remnawave returns `trafficLimitBytes`. `0` or absent means unlimited. Any value `> 0` means limited. Maps to local `traffic_limit_gb`: `0 → null` (unlimited), `> 0 → value / 1024^3`.
- **Type inference:** only updated if `user.has_made_payment = false`. If `has_made_payment = true`, the local `type` is **never** downgraded back to `trial` during sync — an admin manually setting a traffic cap in Remnawave on a paying user does not reclassify them as trial. For users with `has_made_payment = false`: `traffic_limit_gb IS NULL → paid`, `traffic_limit_gb IS NOT NULL → trial`.
- Updates: `expires_at`, `traffic_limit_gb`, `status` (active/expired based on `expireAt` vs now), `type`, `synced_at`.

---

## Remnawave Integration

### Fetching the Subscription Link (for Installation page)
```
GET /users/{remnawave_uuid}
```
The response includes the field **`subscriptionUrl`** (confirmed from Remnawave API schema). This URL is the user's personal subscription link used in deep links on the Installation page.

The subscription URL is cached in Redis per user (`sub_url:{user_id}`) with a 1-hour TTL to avoid redundant API calls on every page load.

### Creating a Trial User
```
POST /users
{
  "username": "ws_{user_id[:8]}",
  "trafficLimitBytes": 30 * 1024 * 1024 * 1024,
  "expireAt": "<now + 3 days in ISO 8601>",
  "squadIds": ["<remnawave_squad_uuids setting>"],
  "telegramId": <integer, if Telegram auth provider linked>,
  "description": "<telegram @username if available>"
}
```

### Extending a Subscription (on payment)
```
PATCH /users/{remnawave_uuid}
{
  "trafficLimitBytes": 0,
  "expireAt": "<max(current_expire, now) + duration_days in ISO 8601>"
}
```

### Adding Bonus Days (promo code type 2)
```
PATCH /users/{remnawave_uuid}
{
  "expireAt": "<current_expire + bonus_days in ISO 8601>"
}
```

### Syncing a User
```
GET /users/{remnawave_uuid}
```
Response field mapping (confirmed against `UserItemInfo` schema):
- `expireAt` (time.Time) → `subscriptions.expires_at`
- `trafficLimitBytes` (OptInt): `0` or absent → `traffic_limit_gb = null`; `> 0` → `traffic_limit_gb = ceil(value / 1024^3)`
- `status` (`ACTIVE` / `DISABLED`) → `subscriptions.status`; `expired` determined locally as `expires_at < now()`
- `subscriptionUrl` (string) → cached in Redis as `sub_url:{user_id}` (TTL 1h)

---

## Payment Integration (Cryptomus)

- **Currency:** Invoices are created in USDT. The RUB price is converted to USDT at invoice creation time using CoinGecko's public rate API (`GET /simple/price?ids=tether&vs_currencies=rub`), cached in Redis for 5 minutes. **Failure behavior:** If the rate API is unavailable and the cache is empty, the payment creation endpoint returns HTTP 503 with a user-facing message "Сервис оплаты временно недоступен, попробуйте через несколько минут." If the cache is stale (older than 5 min but available), the stale value is used for up to 30 minutes before failing. This avoids blocking payments for brief rate API outages.
- **Invoice creation:** `POST https://api.cryptomus.com/v1/payment` — merchant ID + HMAC-signed request + amount in USDT + `order_id` (transaction UUID) + `url_callback`.
- **Webhook verification:** HMAC signature + source IP allowlist check (Cryptomus published IPs).
- **Idempotency:** `external_payment_id` has UNIQUE constraint. Duplicate webhooks are detected and ignored.
- **Failure handling:** If Remnawave call fails after payment confirmation, transaction stays `failed`, Telegram alert sent to admin, Cryptomus receives 500 to trigger retry. Admin can manually trigger sync to recover.
- **Payment provider abstraction:** All Cryptomus calls go through a `PaymentProvider` abstract interface in `app/services/payments/`. This allows adding YooKassa, Robokassa, etc. later.

---

## Security

- **SQL injection:** SQLAlchemy ORM with parameterized queries. No raw SQL strings.
- **XSS:** React escapes output. `Content-Security-Policy` header set via Nginx.
- **CSRF:** `SameSite=Strict` httpOnly cookies. CSRF token header (`X-CSRF-Token`) required on all state-changing requests.
- **Auth tokens:** httpOnly cookies (no JS access). JWT blacklist in Redis. Refresh token rotation on every use.
- **Rate limiting:** Redis-backed on all auth endpoints (10 req/min), payment creation (5 req/min), trial activation (3 per IP per 24h), support form (5 per user per hour).
- **Webhook security:** Cryptomus HMAC signature verification + IP allowlist check. The `/api/payments/webhook` endpoint is explicitly **exempt from CSRF token enforcement** (added to the CSRF middleware exclusion list), since Cryptomus cannot supply a CSRF token.
- **Sensitive settings:** AES-256-GCM encryption. A random 96-bit nonce is generated per encryption and prepended to the ciphertext. The AES key (256-bit) is stored in `.env` as `SETTINGS_ENCRYPTION_KEY` (never in DB). **Key rotation procedure:** Generate new 256-bit key → call admin endpoint "Re-encrypt all settings" (decrypts with old key, re-encrypts with new key, saves) → update `SETTINGS_ENCRYPTION_KEY` in `.env` and restart the backend container. Documented in `README.md`.
- **Admin routes:** `is_admin` check in both middleware (request-level) and at the service/router layer for each admin endpoint (defense in depth — middleware misconfiguration cannot bypass per-endpoint checks).
- **Input validation:** Pydantic schemas on all API inputs, including webhook payloads.
- **HTTPS:** Enforced via Nginx. HTTP redirected to HTTPS. HSTS header enabled.
- **Dependencies:** `uv.lock` committed. Docker images pinned to specific digest versions.

---

## Pages

### 1. Home (`/`)
- **New user (no subscription):** Large CTA card "Активировать пробный период" with description (30 ГБ, 3 дня). Note that traffic limits only apply to trial; paid plans are unlimited.
- **Trial active:** Subscription card: type="Пробный период", expiry date, days remaining. Traffic progress bar (used/30GB). "Оформить подписку" button. Note about no limits after payment.
- **Paid active:** Subscription card: plan name, expiry, days remaining, traffic = "Безлимит". "Продлить заранее" + "Страница установки" buttons.
- **Expired:** Red status badge. "Продлить подписку" button.
- Stats row: traffic status, server status.
- Quick links: Installation, Plans, Support.

### 2. Installation (`/install`)
- **Subscription link access:** The `GET /api/install/subscription-link` endpoint checks subscription status server-side. Active users (trial or paid) receive their personal link. **Expired users receive HTTP 403** — the link is withheld at the API level, not just hidden in UI. The page shows a "Подписка истекла — продлите для доступа" prompt with a link to the Subscription page.
- Detects user OS via `navigator.userAgent`. Manual platform switcher available.
- Platforms: Android, iOS, Windows, macOS, Linux.
- Each platform has a featured app shown by default; secondary app selectable via tabs.
- Steps shown as vertical timeline.
- Deep links inject user's real `SUBSCRIPTION_LINK` and `USERNAME` (subscription URL cached from Remnawave, 1h TTL).
- Deep links per app:
  - FlClash: `flclash://install-config?url={SUB_LINK}`
  - Clash Mi (iOS): `clash://install-config?overwrite=no&name={USERNAME}&url={SUB_LINK}`
  - Clash Meta (Android): `clashmeta://install-config?name={USERNAME}&url={SUB_LINK}`
  - Clash Verge: `clash://install-config?url={SUB_LINK}`
- Manual fallback instructions shown below deep link step.

### 3. Subscription (`/subscription`)
- Current subscription banner.
- New user discount notice (shown only if eligible).
- 4 plan cards (selectable): price, price-per-month, savings vs monthly rate.
- Promo code field (applies `discount_percent` at checkout, or queues `bonus_days` to be applied after payment).
- Order summary: selected plan, current expiry, projected new expiry, final price after discount.
- "Оплатить криптовалютой" → Cryptomus redirect.
- "Применить промокод" standalone section for `bonus_days` codes without payment.
- Note: "Подписка продлится, а не начнётся заново".

### 4. Profile (`/profile`)
- Account info: User ID (#XXXX), display name, email (if set).
- Linked accounts: connected providers with icons. Link/Unlink buttons. Warning if conflict.
- Transaction history: type icon, description, date, amount. Chronological, paginated.
- Conflict warning banner if `subscription_conflict = true`.

### 5. Support (`/support`)
- Telegram button (link from `support_telegram_url` setting).
- Email address (click to copy).
- Contact form: name (pre-filled), email (pre-filled), message textarea, Send button.
- `POST /api/support/message` → backend sends Telegram message to `telegram_support_chat_id` with: user display name, user ID, linked providers, message text. Bot token never sent to frontend.

### 6. Documentation (`/docs`)
- Article list: published articles sorted by `sort_order`, as cards with title and preview.
- Article detail: `/docs/{slug}` — rendered Markdown.

### 7. Terms of Use (`/terms`) & Privacy Policy (`/privacy`)
- Static pages with full Russian-language legal text appropriate for a subscription digital service (covering: data collection, data use, payment terms, refund policy, user obligations, service availability disclaimers).
- Linked from auth page footer and admin editable via Settings.

---

## Admin Panel (`/admin`)

Admin access: `is_admin = true`. Per-endpoint authorization check in addition to middleware.

### Users
- Table: ID, display name, providers, subscription status, expiry, `remnawave_uuid`, created at. Searchable and sortable.
- User detail page: full info, subscription record, transaction history, conflict flag, individual sync button.
- Conflict resolution: choose which `remnawave_uuid` to keep → updates user record and triggers sync.

### Subscriptions / Sync
- "Sync all users" button: runs as a **background task** (FastAPI `BackgroundTasks`) so the admin's HTTP request returns immediately with a task ID. The frontend polls `GET /api/admin/sync/status/{task_id}` every 2 seconds to show progress (current user count / total).
- Per-user: fetches one user's Remnawave data, updates local subscription row. Timeout per user: 10 seconds. If a single user's sync fails, that user is skipped and logged — the batch continues.
- Full batch timeout: 10 minutes. If exceeded, the task is marked as timed out and the admin is notified.
- Per-user sync button on user detail page (synchronous, result shown inline).
- Last sync timestamps displayed on both the sync overview page and individual user records.

### Plans & Pricing
- Edit `price_rub`, `new_user_price_rub`, `duration_days`, `label`, `is_active` for each plan.
- Changes take effect immediately for new purchases.

### Promo Codes
- Create: code, type, value, max_uses, valid_until.
- Table: code, type, value, used/max, valid until, active toggle, delete.
- Atomic `used_count` display.

### Articles
- Create / edit / delete articles.
- Markdown editor with live preview.
- Publish / unpublish toggle.
- Sort order management.

### Settings
- All `settings` entries editable via form, grouped by category.
- Sensitive fields shown masked (reveal button). Changes encrypted before save.
- **Key rotation:** Documented button "Re-encrypt all settings" that reads all sensitive values, decrypts with current key, re-encrypts with new key (new key entered in a modal). Admin must manually update `.env` afterward.

### Support Messages Log
- Log of contact form submissions: user, timestamp, message, status (new/seen).

---

## Deployment

### `docker-compose.yml` services
```
nginx          — port 80/443, reverse proxy, serves built frontend static files
backend        — FastAPI, port 8000 (internal only)
frontend       — React build (dev server in development only)
postgres       — PostgreSQL 16, persistent volume
redis          — Redis 7, persistent volume
```

### Environment Variables (`.env`)
```
# Infrastructure (never in settings table)
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/skavellion
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<random 64 bytes — used for JWT signing>
SETTINGS_ENCRYPTION_KEY=<random 32 bytes — AES-256-GCM key for sensitive settings>

# OAuth — infrastructure secrets, rarely change
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
VK_CLIENT_ID=...
VK_CLIENT_SECRET=...

ENVIRONMENT=production
```

**OAuth credentials** (Google, VK) are stored in `.env` only — they are infrastructure-level and require a redeploy to change anyway (since OAuth callback URLs must match). They are **not** in the `settings` table.

**Operational secrets** (Telegram bot token, Cryptomus keys, Remnawave token) are stored AES-256-GCM encrypted in the `settings` table and configurable via admin panel without redeployment.

### Git Hygiene
`.venv/`, `*.env`, `node_modules/`, `__pycache__/`, `dist/`, `.superpowers/` in `.gitignore`. Commits follow conventional commits style. `uv.lock` and `package-lock.json` committed.

### Project Structure
```
custom_sub_pages/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models/
│       ├── schemas/
│       ├── routers/        # auth, users, subscriptions, payments, admin, support, articles, install
│       ├── services/       # remnawave.py, payments/, telegram.py, oauth/
│       └── middleware/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       └── types/
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Out of Scope (this version)

- Telegram Mini App integration (future)
- Custom Telegram bot replacement (future)
- Multi-language support (ru only)
- Email notifications (only Telegram bot notifications for admin support)
- Mobile native apps
- Affiliate/referral system
- Light mode
