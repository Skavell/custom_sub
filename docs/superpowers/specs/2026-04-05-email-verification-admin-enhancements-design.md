# Design: Email Verification, Admin User Detail, Admin Settings Enhancements

**Date:** 2026-04-05
**Plans:** 11 (Backend), 12 (Frontend)
**Approach:** All backend changes in one plan, all frontend in one plan.

---

## 1. Overview

Three features are added together because they share schema changes and are needed before production deployment:

1. **Soft email verification** — users can register and log in, but must verify email to activate trial subscription
2. **Admin user detail enhancements** — full user info + ban/admin/reset-subscription actions
3. **Admin settings additions** — Remnawave config, email service, registration controls

---

## 2. Database Migrations

Two new columns added via Alembic migrations (extending existing chain ending at `1e776950ed0d`):

### Migration A — `auth_providers.email_verified`
```sql
ALTER TABLE auth_providers ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
```
Semantics: only meaningful for `email` provider rows. OAuth providers (google, vk, telegram) are always considered verified (email identity confirmed by the OAuth provider).

### Migration B — `users.is_banned`
```sql
ALTER TABLE users ADD COLUMN is_banned BOOLEAN NOT NULL DEFAULT FALSE;
```

### Migration C — Seed default settings
INSERT INTO settings (key, value, is_sensitive) for new keys if they don't already exist:

| Key | Default value | Sensitive |
|-----|---------------|-----------|
| `email_verification_enabled` | `false` | No |
| `allowed_email_domains` | `gmail.com,mail.ru,yandex.ru,yahoo.com,outlook.com,hotmail.com,icloud.com,rambler.ru,bk.ru,list.ru,inbox.ru,proton.me,protonmail.com,me.com,live.com` | No |
| `registration_enabled` | `true` | No |
| `resend_api_key` | `` (empty) | **Yes** |
| `email_from_address` | `` (empty) | No |
| `email_from_name` | `` (empty) | No |
| `remnawave_trial_squad_uuids` | `` (empty) | No |
| `remnawave_paid_squad_uuids` | `` (empty) | No |

The existing `remnawave_squad_uuids` key is left untouched. The trial activation code falls back to it if `remnawave_trial_squad_uuids` is empty (backward compatibility during first deploy).

---

## 3. Backend — Plan 11

### 3.1 Registration guards (`POST /api/auth/register`)

Two new checks before user creation:

1. **Registration enabled:** read `registration_enabled` setting; if `"false"` → HTTP 503 `"Регистрация временно закрыта"`
2. **Email domain whitelist:** read `allowed_email_domains` setting; split by comma; if email domain not in list → HTTP 400 `"Регистрация с этим email-адресом недоступна"`

Both settings default to permissive values so existing behavior is unchanged until admin configures them.

### 3.2 Email verification service (`app/services/email_service.py`)

Sends transactional email via Resend REST API (`POST https://api.resend.com/emails`). Uses `httpx.AsyncClient`. Settings read: `resend_api_key`, `email_from_address`, `email_from_name`.

If `resend_api_key` is not configured → raises `RuntimeError` (caller handles as 503).

### 3.3 Verification endpoints (added to `app/routers/auth.py`)

**`POST /api/auth/verify-email/send`** (requires auth)
- Check user has an email provider with `email_verified=False`; if already verified → 200 no-op
- Check `resend_api_key` configured → 503 if not
- Rate limit: 3 sends per hour per user (Redis key `verify_email_rate:{user_id}`)
- Generate `uuid4()` token → store in Redis: `verify_email:{token}` = `user_id`, TTL 86400s (24h)
- Send email with link `{FRONTEND_URL}/verify-email?token={token}`
- Return `{"ok": true}`

**`GET /api/auth/verify-email/confirm`** (public, query param `token`)
- Look up `verify_email:{token}` in Redis → 400 if not found/expired
- Set `auth_providers.email_verified = True` for this user's email provider
- Delete Redis key
- Redirect (HTTP 302) to `{FRONTEND_URL}/verify-email?verified=1`

### 3.4 Trial activation guard (update `POST /api/subscriptions/trial`)

After existing guards, add:
- Read `email_verification_enabled` setting
- If `"true"`: check if user has email provider with `email_verified=False` → HTTP 403 `"Подтвердите email для активации пробного периода"`

### 3.5 Trial squad fallback (update `POST /api/subscriptions/trial`)

Replace `remnawave_squad_uuids` lookup with:
```python
squad_uuids_str = (
    await get_setting(db, "remnawave_trial_squad_uuids")
    or await get_setting(db, "remnawave_squad_uuids")
    or ""
)
```

### 3.6 Ban enforcement (update `app/deps.py` — `get_current_user`)

After loading user from DB, check `user.is_banned` → raise HTTP 403 `"Аккаунт заблокирован"` if True.

### 3.7 Admin schema extensions

**`UserAdminDetail`** gains:
- `is_banned: bool`
- `email: str | None` — provider_user_id of email provider (for quick display)
- `email_verified: bool | None` — email_verified from email provider
- `providers` items gain: `provider_user_id: str` (so telegram_id is visible)

**`UserAdminListItem`** gains:
- `is_banned: bool`
- `email: str | None`

### 3.8 New admin endpoints

All require `require_admin` dependency.

**`PATCH /api/admin/users/{user_id}/ban`**
- Toggle `user.is_banned`
- Cannot ban yourself (403)
- Returns updated `UserAdminDetail`

**`PATCH /api/admin/users/{user_id}/admin`**
- Toggle `user.is_admin`
- Cannot remove own admin (403)
- Returns updated `UserAdminDetail`

**`POST /api/admin/users/{user_id}/reset-subscription`**
- Load subscription; if none → 404
- Set `sub.status = expired`, `sub.expires_at = now()`
- Does NOT touch Remnawave (admin should manually sync after if needed)
- Returns `{"ok": true}`

### 3.9 OAuthConfigResponse extension

Add `email_verification_required: bool` field so frontend knows whether to show the verification banner. Computed as: `email_verification_enabled == "true"`.

---

## 4. Frontend — Plan 12

### 4.1 New page: `/verify-email`

Standalone page (no Layout, no auth required). Reads `?token` or `?verified` from URL:

- If `?token=...`: on mount, POST `/api/auth/verify-email/confirm?token=...`
  - Success: show "Email подтверждён ✓" + button "Перейти к подписке" → `/subscription`
  - Error: show "Ссылка устарела или недействительна" + button "Войти"
- If `?verified=1`: show success state immediately (server already confirmed via redirect)
- If neither: show "Неверная ссылка"

### 4.2 Verification banner (shared component)

New component `EmailVerificationBanner` — shown on `/` (HomePage) and `/subscription` pages.

Display condition: user has email provider AND `email_verification_required=true` from OAuthConfig AND email is not verified (needs new field `email_verified` in `UserProfileResponse`).

Add `email_verified: bool | None` to `UserProfileResponse` (from `/api/users/me`). Backend: derived from email provider's `email_verified` field.

Banner content:
```
⚠ Подтвердите email — [resend button]  "Письмо отправлено!" flash on success
```

Resend button: POST `/api/auth/verify-email/send`, shows spinner, then success/error message. Disabled for 60s after send to prevent spam clicking.

### 4.3 Trial button guard (update `SubscriptionPage`)

If banner is visible (email not verified + verification required): disable "Активировать пробный период" button with tooltip "Сначала подтвердите email".

### 4.4 Admin user detail page (`/admin/users/:id`) — full redesign

**Info section** (read-only grid):

| Field | Value |
|-------|-------|
| ID | UUID |
| Имя | display_name |
| Email | email or "—" + ✓/✗ verified badge |
| Провайдеры | icon + identifier + provider_user_id (telegram_id visible) |
| Статус | Active / Banned badge |
| Права | Admin / User badge |
| Создан | created_at |
| Последний вход | last_seen_at |
| Подписка | type + status + expires_at + traffic |
| Remnawave UUID | uuid or "—" |

**Actions section** (with confirmation dialogs):

| Action | Confirm text |
|--------|-------------|
| Заблокировать / Разблокировать | "Заблокировать пользователя {name}?" |
| Выдать / Забрать права админа | "Сделать {name} администратором?" |
| Сбросить подписку | "Сброс подписки пользователя {name}. Это действие необратимо." |
| Синхронизировать с Remnawave | (already exists) |
| Разрешить конфликт UUID | (already exists) |

All action mutations invalidate `['admin', 'user', id]` query key.

### 4.5 Admin settings page (`/admin/settings`) — new sections

Replace current generic key-value list with grouped sections. Each section has a header and human-readable field labels. Existing save-per-key mechanic is kept.

**Sections:**

**Remnawave**
- URL сервера (`remnawave_url`) — text input
- API токен (`remnawave_token`) — masked secret input
- Squad UUID для триала (`remnawave_trial_squad_uuids`) — text input, hint: "UUID через запятую"
- Squad UUID для платной подписки (`remnawave_paid_squad_uuids`) — text input

**Пробный период**
- Длительность (дней) (`remnawave_trial_days`) — number input
- Лимит трафика (ГБ) (`remnawave_trial_traffic_limit_bytes`) — number input showing GB (stored as bytes: value × 1024³)

**Email-сервис (Resend)**
- API ключ (`resend_api_key`) — masked secret input
- Адрес отправителя (`email_from_address`) — text input, e.g. `noreply@yourdomain.com`
- Имя отправителя (`email_from_name`) — text input, e.g. `VPN Service`

**Регистрация**
- Регистрация открыта (`registration_enabled`) — toggle switch (stored as `"true"`/`"false"`)
- Подтверждение email (`email_verification_enabled`) — toggle switch
- Разрешённые домены (`allowed_email_domains`) — textarea, one domain per line in UI (stored as comma-separated)

**OAuth** — already exists, no changes

**Прочее** — already exists, no changes

---

## 5. Data Flow Summary

```
Registration:
  POST /register → check registration_enabled → check domain whitelist → create user (email_verified=false)

Verification:
  POST /verify-email/send → Redis token → Resend email → link → GET /verify-email/confirm → email_verified=true

Trial activation:
  POST /subscriptions/trial → check email_verified (if required) → create Remnawave user with trial squad → create local sub

Admin actions:
  PATCH /admin/users/:id/ban → toggle is_banned → get_current_user returns 403 for banned users
  PATCH /admin/users/:id/admin → toggle is_admin
  POST /admin/users/:id/reset-subscription → mark sub expired
```

---

## 6. Error Cases

| Scenario | Response |
|----------|----------|
| Email domain not in whitelist | 400 "Регистрация с этим email-адресом недоступна" |
| Registration disabled | 503 "Регистрация временно закрыта" |
| Verify email: token expired | 400 "Ссылка устарела" |
| Verify email: resend_api_key not set | 503 |
| Trial: email not verified | 403 "Подтвердите email для активации" |
| Banned user login | 403 "Аккаунт заблокирован" |
| Admin removes own admin | 403 |
| Admin bans self | 403 |

---

## 7. Deployment Checklist (first deploy)

1. Set `remnawave_url` and `remnawave_token` in admin settings
2. Set `remnawave_trial_squad_uuids` (copy from old `remnawave_squad_uuids` if set)
3. Set `resend_api_key`, `email_from_address`, `email_from_name` if email verification is needed
4. Register first user → set `is_admin=true` via psql → enable `email_verification_enabled` in admin
5. Set `registration_enabled=true` to open for users
