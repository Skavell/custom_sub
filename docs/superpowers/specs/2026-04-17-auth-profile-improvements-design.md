# Design: Auth & Profile Improvements

**Date:** 2026-04-17  
**Status:** Approved by user

---

## Scope

Five independent improvements to the authentication and profile pages:

1. Forgot password flow (inline in LoginPage + new ResetPasswordPage)
2. Change password in profile (for email provider)
3. Edit display name (inline in profile)
4. Email verification banner spacing fix
5. Telegram icon replacement + fix non-clickable Telegram button in profile

---

## 1. Forgot Password Flow

### Backend (`backend/app/routers/auth.py`)

**`POST /api/auth/reset-password/request`** (public)
- Body: `ResetPasswordRequestSchema` → `{ email: EmailStr }`
- `email_lower = email.lower()`
- Rate limit key: `reset_pwd_rate:{email_lower}` — 3 req/hour via `check_rate_limit` → HTTP 429 if exceeded
- Lookup `AuthProvider` where `provider == email` and `provider_user_id == email_lower`
- If not found → HTTP 404 `"Email не найден"` _(deliberate UX choice per user requirement; email enumeration accepted as a known trade-off)_
- Generate token: `secrets.token_urlsafe(32)` (256 bits entropy)
- Store in Redis: `reset_pwd:{token}` → `str(user_id)`, TTL 3600 seconds
- Resolve `api_key`, `from_address`, `from_name` from DB settings (same as `verify-email/send`)
- Call `await send_reset_email(api_key, from_address, from_name, to_email=email_lower, reset_url=f"{site_url}/reset-password?token={token}")`
- Returns `{ ok: true }`

**`POST /api/auth/reset-password/confirm`** (public)
- Body: `ResetPasswordConfirmSchema` → `{ token: str, new_password: str }` (strength-validated)
- Lookup `reset_pwd:{token}` in Redis → if missing → HTTP 400 `"Ссылка недействительна или истекла"`
- Parse `user_id` from stored value
- Find `AuthProvider` (email) for that `user_id`
- Updates `provider.password_hash = hash_password(new_password)`
- Deletes Redis token: `await redis.delete(f"reset_pwd:{token}")`
- Increments session version: `await redis.incr(f"user_pwd_version:{user_id}")`
- Does NOT set auth cookies (user must log in manually after reset)
- Returns `{ ok: true }`

---

### Session invalidation via Redis version counter

To revoke all active sessions without a DB migration:

**`user_pwd_version:{user_id}`** — Redis integer key, default 0 when absent.

**Changes to `backend/app/services/auth/jwt_service.py`:**

```python
def create_access_token(user_id: str, pwd_v: int = 0, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {"sub": user_id, "type": TokenType.ACCESS, "exp": expire, "pwd_v": pwd_v},
        settings.secret_key, algorithm="HS256",
    )

def create_refresh_token(user_id: str, pwd_v: int = 0, expires_delta: timedelta | None = None) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    token = jwt.encode(
        {"sub": user_id, "type": TokenType.REFRESH, "exp": expire, "jti": jti, "pwd_v": pwd_v},
        settings.secret_key, algorithm="HS256",
    )
    return token, jti
```

**Changes to `backend/app/routers/auth.py` — `_set_auth_cookies`:**

```python
async def _set_auth_cookies(response: Response, user_id: str, redis: Redis) -> None:
    raw = await redis.get(f"user_pwd_version:{user_id}")
    pwd_v = int(raw) if raw else 0
    access = create_access_token(str(user_id), pwd_v=pwd_v)
    refresh, jti = create_refresh_token(str(user_id), pwd_v=pwd_v)
    # ... rest unchanged
```

**Changes to `backend/app/deps.py` — `get_current_user`:**

After the blacklist check, add:
```python
token_pwd_v = int(payload.get("pwd_v", 0))
stored = await redis.get(f"user_pwd_version:{user_id_str}")
stored_pwd_v = int(stored) if stored else 0
if token_pwd_v != stored_pwd_v:
    raise HTTPException(status_code=401, detail="Session invalidated", headers=_401)
```

**Changes to `backend/app/routers/auth.py` — `/refresh` endpoint:**

After verifying the refresh token and before calling `_set_auth_cookies`, add version check:
```python
token_pwd_v = int(payload.get("pwd_v", 0))
stored = await redis.get(f"user_pwd_version:{str(user_uuid)}")
stored_pwd_v = int(stored) if stored else 0
if token_pwd_v != stored_pwd_v:
    raise HTTPException(status_code=401, detail="Session invalidated")
```

---

### New function: `send_reset_email` in `backend/app/services/email_service.py`

```python
async def send_reset_email(
    api_key: str,
    from_address: str,
    from_name: str,
    to_email: str,
    reset_url: str,
) -> None:
```

- Same Resend REST API pattern as existing `send_verification_email` (must be `async def`)
- Subject: `"Сброс пароля"`
- HTML body: "Нажмите кнопку ниже, чтобы сбросить пароль" + styled button linking to `reset_url`
- Footer note: "Ссылка действительна 1 час. Если вы не запрашивали сброс — проигнорируйте письмо."

---

### New Pydantic schemas (`backend/app/schemas/auth.py`)

**Shared password validator** (module-level function, reused by all password fields):

```python
def validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Пароль должен содержать не менее 8 символов")
    if not any(c.isupper() for c in v):
        raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
    if not any(c.islower() for c in v):
        raise ValueError("Пароль должен содержать хотя бы одну строчную букву")
    if not any(c.isdigit() for c in v):
        raise ValueError("Пароль должен содержать хотя бы одну цифру")
    return v
```

Applied via `@field_validator` (Pydantic v2 pattern):

```python
@field_validator("password")  # or "new_password"
@classmethod
def _validate_password(cls, v: str) -> str:
    return validate_password_strength(v)
```

Note: `EmailStr` normalisation runs before the validator because Pydantic v2 applies type coercion before validators by default. For `str` fields, the validator receives the raw string.

**New schemas:**

```python
class ResetPasswordRequestSchema(BaseModel):
    email: EmailStr

class ResetPasswordConfirmSchema(BaseModel):
    token: str = Field(min_length=1)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)
```

**Updated schemas** — `EmailRegisterRequest.password` and `LinkEmailRequest.password` validators replaced with calls to `validate_password_strength`.

---

### Frontend: LoginPage (`frontend/src/pages/LoginPage.tsx`)

Mode extended: `'login' | 'register' | 'forgot' | 'reset-sent'`

- In `login` mode: small text button "Забыли пароль?" appears below the password field, switches to `'forgot'`
- In `forgot` mode: card shows only email input + "Отправить" button + "← Назад" button
  - Reuses existing `loading` state for the submit button disabled state
  - On submit: `POST /api/auth/reset-password/request`
  - 200 → switch to `'reset-sent'`, show "Письмо отправлено на {email}"
  - 404 → inline error "Email не найден" (stay in `forgot` mode)
  - 429 → inline error "Слишком много попыток. Попробуйте позже."
- In `reset-sent` mode: "Письмо отправлено на {email}" + "← Назад к входу" button

---

### New page: `ResetPasswordPage` (`frontend/src/pages/ResetPasswordPage.tsx`)

**Registration in `App.tsx`:** Add `<Route path="/reset-password" element={<ResetPasswordPage />} />` as a **public route outside the `ProtectedRoute` wrapper**, same level as `/login` and `/verify-email`.

- Reads `token` from `useSearchParams()`
- If `token` is absent → show "Неверная ссылка" + link to `/login`
- Form: "Новый пароль" (type=password) + "Повторите новый пароль" (type=password)
- Client-side validation before submit: passwords match + password strength (min 8, uppercase, lowercase, digit)
- On submit: `POST /api/auth/reset-password/confirm` with `{ token, new_password }`
- 200 → "Пароль успешно изменён" + button/link "Войти" → `/login`
- 400 → "Ссылка недействительна или истекла" + link to `/login`

---

## 2. Change Password in Profile

### Backend (`backend/app/routers/users.py`)

**`PATCH /api/users/me/password`** (authenticated, `PATCH` for consistency with other partial updates)
- Body: `ChangePasswordRequest`

**New Pydantic schema (`backend/app/schemas/user.py`):**

```python
from app.schemas.auth import validate_password_strength

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)
```

**Endpoint logic:**
1. Find `AuthProvider` with `provider == email` for `current_user` → if not found → HTTP 400 `"Email-провайдер не привязан"`
2. Guard: `if not provider.password_hash:` → HTTP 400 `"Пароль не установлен для этого провайдера"` (covers OAuth-linked email providers without password)
3. `verify_password(old_password, provider.password_hash)` → if fails → HTTP 400 `"Неверный текущий пароль"`
4. `provider.password_hash = hash_password(new_password)`
5. `await redis.incr(f"user_pwd_version:{str(current_user.id)}")` — invalidates all sessions
6. Commit, return `{ ok: true }`

Note: The `redis` dependency must be added to this endpoint.

### Frontend: ProfilePage (`frontend/src/pages/ProfilePage.tsx`)

In the "Привязанные аккаунты" section, for each provider row where `p.type === 'email'`:
- Add a `KeyRound` icon button (lucide-react, 14px) to the left of the trash icon
- **Always visible on the email row — not gated by `canUnlink`**
- State: `changePasswordOpen: boolean`
- When `changePasswordOpen = true`: inline form appears below the email row:
  - "Текущий пароль" (type=password)
  - "Новый пароль" (type=password)
  - "Повторите новый пароль" (type=password)
  - Client validation before submit: new passwords match + strength (no trim on passwords — spaces are valid)
  - Error state shown inline
  - Buttons: "Сохранить" / "Отмена"
  - On success: close form, clear all three fields

---

## 3. Edit Display Name

### Backend (`backend/app/routers/users.py`)

**`PATCH /api/users/me`** (authenticated)
- Body: `UpdateDisplayNameRequest`

**New Pydantic schema (`backend/app/schemas/user.py`):**

```python
class UpdateDisplayNameRequest(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Имя не может быть пустым")
        if len(v) > 64:
            raise ValueError("Имя не может быть длиннее 64 символов")
        return v
```

**Endpoint logic:**
- `current_user.display_name = data.display_name` (already stripped by validator)
- Commit, return `{ ok: true }`

### Frontend: ProfilePage

In the account info block:
- `Pencil` icon (lucide-react, 14px, `text-text-muted hover:text-text-primary cursor-pointer`) to the right of `user.display_name`
- State: `isEditingName: boolean`, `nameInput: string`
- When `isEditingName = true`: name text replaced with `<input type="text">` pre-filled with current name + `Check` (save) and `X` (cancel) icon buttons inline
- Enter key → save, Escape key → cancel
- Frontend trims before submit, validates `trim().length > 0` and `≤ 64` chars (backend is authoritative, frontend check is courtesy)
- `PATCH /api/users/me` with `{ display_name: nameInput.trim() }`
- On success: invalidate `['me']` query, exit edit mode
- On error: show inline error

---

## 4. Email Verification Banner Spacing

**`frontend/src/components/EmailVerificationBanner.tsx`**

Add `mb-4` to the root `div` of the component (the `rounded-card border border-yellow-500/30 ...` div). This applies the spacing consistently everywhere the banner is used (HomePage and SubscriptionPage).

---

## 5. Telegram Icon & Profile Button Fix

### New Telegram SVG icon

Replaces the existing SVG path in both files. Color `fill="#2AABEE"`:

```jsx
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 16 16">
  <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M8.287 5.906q-1.168.486-4.666 2.01-.567.225-.595.442c-.03.243.275.339.69.47l.175.055c.408.133.958.288 1.243.294q.39.01.868-.32 3.269-2.206 3.374-2.23c.05-.012.12-.026.166.016s.042.12.037.141c-.03.129-1.227 1.241-1.846 1.817-.193.18-.33.307-.358.336a8 8 0 0 1-.188.186c-.38.366-.664.64.015 1.088.327.216.589.393.85.571.284.194.568.387.936.629q.14.092.27.187c.331.236.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.4 1.4 0 0 0-.013-.315.34.34 0 0 0-.114-.217.53.53 0 0 0-.31-.093c-.3.005-.763.166-2.984 1.09" fill="#2AABEE"/>
</svg>
```

- `LoginPage.tsx` → `width="18" height="18"` (matches existing icon size)
- `ProfilePage.tsx` `TelegramLinkButton` → `width="16" height="16"`

### `TelegramLinkButton` component (extracted into `ProfilePage.tsx` or a shared file)

```tsx
function TelegramLinkButton({
  botUsername,
  onAuth,
}: {
  botUsername: string
  onAuth: (user: Record<string, unknown>) => void  // matches TelegramLoginButton pattern
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !botUsername) return
    // same script injection + MutationObserver + scaleX logic as TelegramLoginButton
    // assigns window.__onTelegramLink = onAuth
    // cleanup: observer.disconnect() + delete window.__onTelegramLink
  }, [botUsername, onAuth])

  return (
    <div className="group relative h-[42px]">
      {/* styled visible button with new icon, pointer-events-none */}
      <div ref={ref} className="absolute inset-0 overflow-hidden" />
    </div>
  )
}
```

Parent in `ProfilePage` renders `<TelegramLinkButton>` only when `canAddTelegram === true`. The `useEffect` always runs with `ref.current` populated because the component only mounts when the element is in the DOM.

The `ProfilePage` `useEffect` for Telegram widget injection and `telegramLinkRef` are removed.

---

## Validation Summary

| Field | Backend rule |
|---|---|
| Password (all new/change fields) | ≥8 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit |
| Email | Pydantic `EmailStr` (format + normalisation) |
| Display name | non-empty after strip, max 64 chars |
| Reset token | `secrets.token_urlsafe(32)`, TTL 1h, single-use |

- **SQL injection:** SQLAlchemy ORM parameterized queries throughout
- **XSS:** React JSX escaping by default
- **Frontend:** mirrors all rules above for immediate feedback

---

## Files Changed

| File | Change |
|---|---|
| `backend/app/schemas/auth.py` | Add `validate_password_strength`, `ResetPasswordRequestSchema`, `ResetPasswordConfirmSchema`; update existing validators |
| `backend/app/schemas/user.py` | Add `ChangePasswordRequest`, `UpdateDisplayNameRequest` |
| `backend/app/services/auth/jwt_service.py` | Add `pwd_v: int = 0` param to `create_access_token` and `create_refresh_token`; include in JWT payload |
| `backend/app/routers/auth.py` | Add 2 reset-password endpoints; update `_set_auth_cookies` to read and embed `pwd_v`; add version check in `/refresh` endpoint |
| `backend/app/routers/users.py` | Add `PATCH /me/password`, `PATCH /me` |
| `backend/app/deps.py` | Add `pwd_v` version check in `get_current_user` after blacklist check |
| `backend/app/services/email_service.py` | Add `async def send_reset_email(...)` |
| `frontend/src/pages/LoginPage.tsx` | Forgot password inline flow; new Telegram icon |
| `frontend/src/pages/ResetPasswordPage.tsx` | New file |
| `frontend/src/pages/ProfilePage.tsx` | Inline name edit; change password form; `TelegramLinkButton` component; new Telegram icon |
| `frontend/src/components/EmailVerificationBanner.tsx` | Add `mb-4` to root div |
| `frontend/src/App.tsx` | Register `/reset-password` as public route outside `ProtectedRoute` |
