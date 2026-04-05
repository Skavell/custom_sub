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

Two new columns added via Alembic migrations (extending existing chain ending at `1e776950ed0d`).

**Critical:** The `User` model and `AuthProvider` model must have the new columns added before the application restarts. Migrations must run before the new application code starts (Alembic auto-runs on startup per existing Dockerfile CMD).

### Migration A — `auth_providers.email_verified`
```sql
ALTER TABLE auth_providers ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
```
Semantics: only meaningful for `email` provider rows. OAuth providers (google, vk, telegram) are always considered verified — email identity is confirmed by the OAuth provider.

When a user links email via `POST /api/users/me/providers/email`, the new `AuthProvider` row is also created with `email_verified=False`. The same verification flow applies to this path.

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
2. **Email domain whitelist:** read `allowed_email_domains` setting; split by comma; trim whitespace on each part; filter empty strings.
   - If the setting is absent or results in an empty list → **skip check** (open to all domains).
   - If non-empty → check email domain against the list → HTTP 400 `"Регистрация с этим email-адресом недоступна"` if not found.

### 3.2 Email verification service (`app/services/email_service.py`)

Sends transactional email via Resend REST API (`POST https://api.resend.com/emails`). Uses `httpx.AsyncClient`. Reads `resend_api_key` via `get_setting_decrypted`, `email_from_address` and `email_from_name` via `get_setting`.

If `resend_api_key` is not configured → raises `RuntimeError` (caller handles as 503).

### 3.3 Verification endpoints (added to `app/routers/auth.py`)

**`POST /api/auth/verify-email/send`** (requires auth via `get_current_user`)
- Check user has an email provider with `email_verified=False`; if already verified → 200 no-op `{"ok": true}`
- Check `resend_api_key` configured → 503 if not
- Rate limit: 3 sends per hour per user. Redis key: `verify_email_rate:{user_id}`, TTL 3600s. Uses existing `check_rate_limit` pattern.
- Generate `uuid4()` token → store in Redis: `verify_email:{token}` = `str(user_id)`, TTL 86400s (24h)
- Send email with link `{FRONTEND_URL}/verify-email?token={token}`
- Return `{"ok": true}`

**`GET /api/auth/verify-email/confirm`** (public, query param `token`)
- Look up `verify_email:{token}` in Redis
  - If not found or expired → HTTP 302 redirect to `{FRONTEND_URL}/verify-email?error=expired`
  - If found → set `auth_providers.email_verified = True` for this user's email provider, delete Redis key → HTTP 302 redirect to `{FRONTEND_URL}/verify-email?verified=1`
- Note: if the user clicks the link a second time after the token has already been consumed, the token no longer exists in Redis → they receive `?error=expired`. This is acceptable — the user is already verified.

### 3.4 Trial activation guard (update `POST /api/subscriptions/trial`)

After existing guards, add:
- Read `email_verification_enabled` setting
- If `"true"`: query whether the user has an `AuthProvider` with `provider == email` AND `email_verified == False` → if yes, HTTP 403 `"Подтвердите email для активации пробного периода"`
- Users with no email provider at all (OAuth-only: Telegram, Google, VK) are **exempt** — verification is not required for them. The guard only applies to users who registered or linked an email address.

### 3.5 Trial squad fallback (update `POST /api/subscriptions/trial`)

Replace `remnawave_squad_uuids` lookup with:
```python
squad_uuids_str = (
    await get_setting(db, "remnawave_trial_squad_uuids")
    or await get_setting(db, "remnawave_squad_uuids")
    or ""
)
```

### 3.6 Ban enforcement — two places

1. **`app/deps.py` — `get_current_user`:** after loading user from DB, check `user.is_banned` → raise HTTP 403 `"Аккаунт заблокирован"` if True.
2. **`POST /api/auth/refresh` handler:** after loading user from DB (the handler already does `select(User)` explicitly), check `user.is_banned` → raise HTTP 403 `"Аккаунт заблокирован"` if True. This prevents a banned user with a valid refresh token from obtaining a new access token.

### 3.7 OAuthConfigResponse extension (`app/schemas/auth.py` + `get_oauth_config` handler)

Add `email_verification_required: bool` to the `OAuthConfigResponse` Pydantic model.

In the `get_oauth_config` handler (`app/routers/auth.py`), add:
```python
email_verification_required = await get_setting(db, "email_verification_enabled") == "true"
```
Include in the returned `OAuthConfigResponse`. Field is always present — no optional.

### 3.8 UserProfileResponse extension (`app/schemas/user.py` + `/api/users/me` handler)

Add `email_verified: bool | None` to `UserProfileResponse`.

Derivation rule:
- Load `AuthProvider` rows for the user (already done in the handler)
- Find the row where `provider == ProviderType.email`
- If found: `email_verified = provider.email_verified`
- If not found (no email provider): `email_verified = None`

`None` semantics: user has no email address linked → verification is not applicable → banner should not show → trial is not blocked.

### 3.9 Admin schema extensions

All changes to `app/schemas/admin.py`:

**`ProviderInfo`** (detail view only) gains:
- `provider_user_id: str` — raw provider user ID (telegram numeric ID, Google subject, email address). Populated from `AuthProvider.provider_user_id`.
- `email_verified: bool | None` — `AuthProvider.email_verified` for email provider; `None` for OAuth providers.

**`UserAdminDetail`** gains:
- `is_banned: bool`
- `email: str | None` — `provider_user_id` from the email-type `AuthProvider`, or `None` if no email provider
- `email_verified: bool | None` — `email_verified` from the email-type `AuthProvider`, or `None` if no email provider

**`UserAdminListItem`** gains:
- `is_banned: bool`
- `email: str | None` — same derivation as above (top-level field, `providers` stays as `list[str]`)
- `email_verified: bool | None` — same derivation as above (top-level field)

`_build_list_item` helper in `app/routers/admin.py` must be updated to populate these three new fields. Requires `selectinload(User.auth_providers)` (already present in the list query).

### 3.10 New admin endpoints (`app/routers/admin.py`)

All require `require_admin` dependency.

**`PATCH /api/admin/users/{user_id}/ban`**
- Load user → 404 if not found
- Cannot ban yourself → 403
- Toggle `user.is_banned`
- Commit + refresh
- Return updated `UserAdminDetail` (build with full selectinload)

**`PATCH /api/admin/users/{user_id}/admin`**
- Load user → 404 if not found
- Cannot remove own admin → 403
- Toggle `user.is_admin`
- Commit + refresh
- Return updated `UserAdminDetail`

**`POST /api/admin/users/{user_id}/reset-subscription`**
- Load subscription → 404 if none
- Set `sub.status = SubscriptionStatus.expired`, `sub.expires_at = now()`
- Commit
- Does NOT call Remnawave API. Local emergency action. Admin uses existing "Sync" button afterward to reconcile.
- Return `{"ok": true}`

---

## 4. Frontend — Plan 12

### 4.1 New page: `/verify-email`

Standalone page (no Layout, no auth required). Reads `?verified` or `?error` from URL:

- `?verified=1` → show "Email подтверждён ✓" + button "Перейти к подписке" → `/subscription`
- `?error=expired` → show "Ссылка устарела или недействительна" + button "На главную" → `/`
- Neither → show "Неверная ссылка"

Note: this page only displays server redirect results. It does not POST anything. Sending verification email is done via the `EmailVerificationBanner` on authenticated pages.

### 4.2 Verification banner (shared component `EmailVerificationBanner`)

Shown on `/` (HomePage) and `/subscription` (SubscriptionPage).

Display condition: `user.email_verified === false` AND `oauthConfig.email_verification_required === true`.

- `user.email_verified` comes from `['me']` TanStack Query key (`UserProfileResponse.email_verified`)
- `oauthConfig.email_verification_required` comes from a new `['oauthConfig']` TanStack Query key (`GET /api/auth/oauth-config`)
- `user.email_verified === null` (no email provider, OAuth-only user) → banner does NOT show

Banner content:
```
⚠ Подтвердите email чтобы активировать пробный период  [Отправить письмо]
```

Resend button: `POST /api/auth/verify-email/send`, spinner during request. On success: show "Письмо отправлено" flash, disable button for 60s (client-side timer — resets on reload, backend rate limit is the actual enforcement). On error: show error message.

### 4.3 Trial button guard (update `SubscriptionPage`)

If banner is visible: disable "Активировать пробный период" button with tooltip "Сначала подтвердите email".

### 4.4 Admin user detail page (`/admin/users/:id`) — full redesign

Update `UserAdminDetail` type in `src/types/api.ts` to include `is_banned`, `email`, `email_verified`, and updated `ProviderInfo` with `provider_user_id` and `email_verified`.

**Info section** (read-only grid):

| Field | Value |
|-------|-------|
| ID | UUID |
| Имя | display_name |
| Email | email or "—" + ✓/✗ verified badge |
| Провайдеры | icon + identifier + provider_user_id (raw, for telegram_id) |
| Статус | Active / Banned badge |
| Права | Admin / User badge |
| Создан | created_at |
| Последний вход | last_seen_at |
| Подписка | type + status + expires_at + traffic_limit_gb |
| Remnawave UUID | uuid or "—" |

**Actions section** (with confirmation dialogs):

| Action | Confirm text |
|--------|-------------|
| Заблокировать / Разблокировать | "Заблокировать пользователя {name}?" |
| Выдать / Забрать права админа | "Сделать {name} администратором?" / "Забрать права админа у {name}?" |
| Сбросить подписку | "Локальный сброс подписки — Remnawave не затронут. Продолжить?" |
| Синхронизировать с Remnawave | (already exists) |
| Разрешить конфликт UUID | (already exists) |

Mutations:
- Ban/admin: server returns updated `UserAdminDetail` → update `['admin-user', id]` query cache directly (matches the existing `queryKey` used by the detail page query)
- Reset-subscription: server returns `{"ok": true}` → invalidate `['admin-user', id]` query key to trigger refetch
- Also invalidate `['sync', 'users']` and existing sync mutation keys if present, for consistency

### 4.5 Admin settings page (`/admin/settings`) — new sections

The existing `AdminSettingsPage.tsx` groups settings by explicit key sets (e.g. `OAUTH_KEYS`). Keys not in any explicit set fall through to the generic "Основные" bucket which renders plain `<input type="text">` — all new keys must be explicitly assigned to avoid this fallback.

Add the following new named key sets (alongside the existing `OAUTH_KEYS`):

```ts
const REMNAWAVE_KEYS = new Set(['remnawave_url', 'remnawave_token', 'remnawave_trial_squad_uuids', 'remnawave_paid_squad_uuids']);
const TRIAL_KEYS = new Set(['remnawave_trial_days', 'remnawave_trial_traffic_limit_bytes']);
const EMAIL_SERVICE_KEYS = new Set(['resend_api_key', 'email_from_address', 'email_from_name']);
const REGISTRATION_KEYS = new Set(['registration_enabled', 'email_verification_enabled', 'allowed_email_domains']);
```

`REGISTRATION_KEYS` entries use dedicated UI components: `registration_enabled` and `email_verification_enabled` render as toggle switches; `allowed_email_domains` renders as a textarea.

**Section layout:**

| Section | Keys |
|---------|------|
| **Remnawave** | `remnawave_url`, `remnawave_token`, `remnawave_trial_squad_uuids` (hint: fallback to legacy key if empty), `remnawave_paid_squad_uuids` |
| **Пробный период** | `remnawave_trial_days`, `remnawave_trial_traffic_limit_bytes` |
| **Email-сервис (Resend)** | `resend_api_key`, `email_from_address`, `email_from_name` |
| **Регистрация** | `registration_enabled`, `email_verification_enabled`, `allowed_email_domains` |
| **OAuth** | existing, no changes |
| **Прочее** | existing, no changes |

**Special UI for specific keys:**
- `registration_enabled`, `email_verification_enabled` → toggle switch (value `"true"`/`"false"`)
- `allowed_email_domains` → textarea; UI displays one domain per line; on save, join lines with `,` (strip whitespace, filter empty lines) before sending to API; on load, split by `,` and join with `\n` for display
- `remnawave_trial_traffic_limit_bytes` → number input showing GB; on load divide by `1024³` (round to nearest integer); on save multiply by `1024³`
- `remnawave_token`, `resend_api_key` → masked secret inputs (already handled by `is_sensitive` flag)

---

## 5. Data Flow Summary

```
Registration (email):
  POST /register
    → check registration_enabled (503 if false)
    → check domain whitelist (skip if setting empty; 400 if domain not in list)
    → create user, create AuthProvider(email_verified=False)

Link email via profile:
  POST /users/me/providers/email
    → create AuthProvider(email_verified=False)
    → verification banner appears on next page load

Email verification:
  POST /verify-email/send (auth)
    → rate limit 3/hr (Redis verify_email_rate:{user_id})
    → store token in Redis verify_email:{token} TTL 24h
    → send email via Resend
  GET /verify-email/confirm?token=
    → found → email_verified=True, delete token → 302 /verify-email?verified=1
    → not found → 302 /verify-email?error=expired

Trial activation:
  POST /subscriptions/trial
    → existing guards (already activated, rate limit, Remnawave not configured)
    → if email_verification_enabled=true AND user has email provider with email_verified=False → 403
    → create Remnawave user with remnawave_trial_squad_uuids (fallback to remnawave_squad_uuids)
    → create local subscription

Ban:
  PATCH /admin/users/:id/ban → toggle is_banned
  → get_current_user dep: 403 for banned users on all protected endpoints
  → POST /auth/refresh: 403 for banned users (prevents token refresh)

Admin actions:
  PATCH /admin/users/:id/admin → toggle is_admin (returns UserAdminDetail)
  POST /admin/users/:id/reset-subscription → local sub expired (returns {"ok":true})
```

---

## 6. Error Cases

| Scenario | HTTP | Message |
|----------|------|---------|
| Email domain not in whitelist | 400 | "Регистрация с этим email-адресом недоступна" |
| Registration disabled | 503 | "Регистрация временно закрыта" |
| Verify send: resend_api_key not set | 503 | — |
| Verify send: rate limit exceeded | 429 | — |
| Verify confirm: token expired/not found | 302 | → `/verify-email?error=expired` |
| Verify confirm: success | 302 | → `/verify-email?verified=1` |
| Trial: email not verified | 403 | "Подтвердите email для активации пробного периода" |
| Login/any endpoint: banned user (access token) | 403 | "Аккаунт заблокирован" |
| Refresh: banned user | 403 | "Аккаунт заблокирован" |
| Admin removes own admin | 403 | — |
| Admin bans self | 403 | — |
| Reset subscription: no subscription | 404 | — |

---

## 7. Deployment Checklist (first deploy)

1. **Run migrations first** — `alembic upgrade head` (adds `email_verified`, `is_banned`, seeds new settings). Happens automatically on container start before app code runs.
2. Start application — new columns exist before any code reads `user.is_banned` or `provider.email_verified`.
3. Set `remnawave_url` and `remnawave_token` in admin settings.
4. Set `remnawave_trial_squad_uuids` (or leave empty to fall back to existing `remnawave_squad_uuids`).
5. Register first user → `UPDATE users SET is_admin=true WHERE ...` via psql → manage everything else from admin panel.
6. Configure `resend_api_key`, `email_from_address`, `email_from_name` when ready. Only then enable `email_verification_enabled` in admin settings.
7. `registration_enabled=true` is the default — no action needed to open registration.

---

## 8. Files to Modify

**Backend:**
- `app/models/user.py` — add `is_banned` column
- `app/models/auth_provider.py` — add `email_verified` column
- `app/schemas/auth.py` — add `email_verification_required` to `OAuthConfigResponse`
- `app/schemas/user.py` — add `email_verified` to `UserProfileResponse`
- `app/schemas/admin.py` — add fields to `ProviderInfo`, `UserAdminDetail`, `UserAdminListItem`
- `app/routers/auth.py` — update `get_oauth_config`, add verify-email endpoints, update `register_email`, update `refresh` ban check
- `app/routers/users.py` — update `get_me`, update `link_email`
- `app/routers/subscriptions.py` — update `activate_trial` (email guard + squad fallback)
- `app/routers/admin.py` — update `_build_list_item`, `get_user_detail`, add ban/admin/reset endpoints
- `app/deps.py` — add ban check in `get_current_user`
- `app/services/email_service.py` — **new file**
- `alembic/versions/` — **3 new migrations**

**Frontend:**
- `src/types/api.ts` — add fields to `OAuthConfigResponse`, `UserProfileResponse`, `UserAdminListItem`, `UserAdminDetail`, `ProviderInfo`
- `src/pages/VerifyEmailPage.tsx` — **new file**
- `src/components/EmailVerificationBanner.tsx` — **new file**
- `src/pages/HomePage.tsx` — add banner
- `src/pages/SubscriptionPage.tsx` — add banner + trial button guard
- `src/pages/admin/AdminUserDetailPage.tsx` — full redesign
- `src/pages/admin/AdminSettingsPage.tsx` — new sections
- `src/App.tsx` (or router file) — add `/verify-email` route
