# Auth & Profile Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add forgot-password flow, change-password in profile, inline name editing, fix Telegram button, replace Telegram icon, fix email banner spacing.

**Architecture:** Backend changes come first (schemas → jwt_service → auth router → users router), then frontend. Session invalidation uses a Redis version counter (`user_pwd_version:{user_id}`) embedded as `pwd_v` in JWTs — no DB migration needed. Password reset tokens use `secrets.token_urlsafe(32)` stored in Redis with 1-hour TTL.

**Tech Stack:** FastAPI + SQLAlchemy async + Redis + Pydantic v2 + jose JWT (backend); React + TypeScript + TanStack Query + Tailwind + lucide-react (frontend).

**Spec:** `docs/superpowers/specs/2026-04-17-auth-profile-improvements-design.md`

---

## File Map

### Created
- `backend/app/schemas/auth.py` — add `validate_password_strength`, `ResetPasswordRequestSchema`, `ResetPasswordConfirmSchema`
- `backend/app/schemas/user.py` — add `ChangePasswordRequest`, `UpdateDisplayNameRequest`
- `backend/tests/schemas/test_auth_schemas.py` — password validator unit tests
- `backend/tests/routers/test_reset_password.py` — reset-password endpoint tests
- `frontend/src/pages/ResetPasswordPage.tsx` — new public reset-password page

### Modified
- `backend/app/services/auth/jwt_service.py` — add `pwd_v` param to token creators
- `backend/app/routers/auth.py` — update `_set_auth_cookies`, add pwd_v check in `/refresh`, add 2 reset-password endpoints
- `backend/app/deps.py` — add pwd_v version check in `get_current_user`
- `backend/app/services/email_service.py` — add `send_reset_email`
- `backend/app/routers/users.py` — add `PATCH /me/password`, `PATCH /me`
- `backend/tests/services/test_jwt_service.py` — add pwd_v tests
- `backend/tests/test_deps.py` — add pwd_v mismatch test
- `backend/tests/routers/test_auth_email.py` — update for new password strength rules
- `backend/tests/routers/test_users.py` — add change-password and update-name tests
- `frontend/src/components/EmailVerificationBanner.tsx` — add `mb-4` to root div
- `frontend/src/pages/LoginPage.tsx` — forgot-password inline flow + new Telegram icon
- `frontend/src/pages/ProfilePage.tsx` — edit name, change password, TelegramLinkButton, new icon
- `frontend/src/App.tsx` — register `/reset-password` public route

---

## Task 1: Strengthen password validator in schemas

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Create: `backend/tests/schemas/test_auth_schemas.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/schemas/test_auth_schemas.py
import pytest
from pydantic import ValidationError
from app.schemas.auth import EmailRegisterRequest, LinkEmailRequest


@pytest.mark.parametrize("password,error_fragment", [
    ("short1A", "8 символов"),          # too short
    ("alllowercase1", "заглавную"),     # no uppercase
    ("ALLUPPERCASE1", "строчную"),      # no lowercase
    ("NoDigitsHere", "цифру"),          # no digit
])
def test_weak_passwords_rejected_in_register(password, error_fragment):
    with pytest.raises(ValidationError) as exc:
        EmailRegisterRequest(email="a@b.com", password=password, display_name="Name")
    assert error_fragment in str(exc.value)


def test_strong_password_accepted():
    req = EmailRegisterRequest(email="a@b.com", password="Secure1Pass", display_name="Name")
    assert req.password == "Secure1Pass"


def test_weak_password_rejected_in_link_email():
    with pytest.raises(ValidationError):
        LinkEmailRequest(email="a@b.com", password="weakpass")
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python -m pytest tests/schemas/test_auth_schemas.py -v
```
Expected: FAIL — weak passwords currently accepted (only len >= 8 checked).

- [ ] **Step 3: Update `backend/app/schemas/auth.py`**

Add `validate_password_strength` above the existing classes, then replace the validators in `EmailRegisterRequest` and `LinkEmailRequest`:

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

In `EmailRegisterRequest`, replace the existing `validate_password` validator body with `return validate_password_strength(v)`.

In `LinkEmailRequest`, do the same — replace the body of `validate_password`.

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/schemas/test_auth_schemas.py -v
```

- [ ] **Step 5: Run existing auth tests to check for regressions**

```bash
cd backend && python -m pytest tests/routers/test_auth_email.py -v
```

Any test that sends `"password": "SecurePass123!"` will pass (it has upper, lower, digit). If any test sends a password like `"password123"` (no uppercase), update it to `"Password123"`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/auth.py backend/tests/schemas/test_auth_schemas.py
git commit -m "feat: strengthen password validator (uppercase, lowercase, digit required)"
```

---

## Task 2: Add `pwd_v` claim to JWT tokens

**Files:**
- Modify: `backend/app/services/auth/jwt_service.py`
- Modify: `backend/tests/services/test_jwt_service.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/services/test_jwt_service.py`:

```python
def test_access_token_contains_pwd_v():
    token = create_access_token("some-user-id", pwd_v=3)
    payload = verify_token(token, TokenType.ACCESS)
    assert payload["pwd_v"] == 3


def test_access_token_pwd_v_defaults_to_zero():
    token = create_access_token("some-user-id")
    payload = verify_token(token, TokenType.ACCESS)
    assert payload.get("pwd_v", 0) == 0


def test_refresh_token_contains_pwd_v():
    token, _ = create_refresh_token("some-user-id", pwd_v=7)
    payload = verify_token(token, TokenType.REFRESH)
    assert payload["pwd_v"] == 7
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python -m pytest tests/services/test_jwt_service.py::test_access_token_contains_pwd_v -v
```

- [ ] **Step 3: Update `backend/app/services/auth/jwt_service.py`**

Add `pwd_v: int = 0` parameter to both functions and include it in the payload:

```python
def create_access_token(user_id: str, pwd_v: int = 0, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {"sub": user_id, "type": TokenType.ACCESS, "exp": expire, "pwd_v": pwd_v},
        settings.secret_key,
        algorithm="HS256",
    )


def create_refresh_token(user_id: str, pwd_v: int = 0, expires_delta: timedelta | None = None) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    token = jwt.encode(
        {"sub": user_id, "type": TokenType.REFRESH, "exp": expire, "jti": jti, "pwd_v": pwd_v},
        settings.secret_key,
        algorithm="HS256",
    )
    return token, jti
```

- [ ] **Step 4: Run all jwt_service tests**

```bash
cd backend && python -m pytest tests/services/test_jwt_service.py -v
```

All 7 tests should pass. The existing tests don't pass `pwd_v`, so they get default 0 — backward compatible.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/auth/jwt_service.py backend/tests/services/test_jwt_service.py
git commit -m "feat: add pwd_v claim to JWT tokens for session invalidation"
```

---

## Task 3: Session invalidation — `_set_auth_cookies` + `/refresh` + `get_current_user`

**Files:**
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/app/deps.py`
- Modify: `backend/tests/test_deps.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_deps.py`:

```python
@pytest.mark.asyncio
async def test_get_current_user_invalidated_session_raises_401():
    """Token with stale pwd_v is rejected."""
    user_id = str(uuid.uuid4())
    # Token issued with pwd_v=1
    token = create_access_token(user_id, pwd_v=1)

    user = MagicMock(spec=User)
    user.id = uuid.UUID(user_id)
    user.is_banned = False

    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)  # not blacklisted
    redis.get = AsyncMock(return_value=b"2")  # stored version is 2 — mismatch

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)

    request = MagicMock(spec=Request)
    request.cookies = {"access_token": token}

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=request, db=db, redis=redis)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_matching_pwd_v_succeeds():
    """Token with matching pwd_v is accepted."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, pwd_v=2)

    user = MagicMock(spec=User)
    user.id = uuid.UUID(user_id)
    user.is_banned = False

    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)  # not blacklisted
    redis.get = AsyncMock(return_value=b"2")  # matching version

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)

    request = MagicMock(spec=Request)
    request.cookies = {"access_token": token}

    result_user = await get_current_user(request=request, db=db, redis=redis)
    assert result_user is user
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backend && python -m pytest tests/test_deps.py::test_get_current_user_invalidated_session_raises_401 -v
```

- [ ] **Step 3: Update `backend/app/deps.py` — add pwd_v check**

After the blacklist check and before the DB execute, insert:

```python
# Session version check
token_pwd_v = int(payload.get("pwd_v", 0))
stored_raw = await redis.get(f"user_pwd_version:{payload['sub']}")
stored_pwd_v = int(stored_raw) if stored_raw else 0
if token_pwd_v != stored_pwd_v:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalidated", headers=_401)
```

- [ ] **Step 4: Update `backend/app/routers/auth.py` — `_set_auth_cookies` reads pwd_v**

Replace the current `_set_auth_cookies` body:

```python
async def _set_auth_cookies(response: Response, user_id: str, redis: Redis) -> None:
    raw = await redis.get(f"user_pwd_version:{user_id}")
    pwd_v = int(raw) if raw else 0
    access = create_access_token(user_id, pwd_v=pwd_v)
    refresh, jti = create_refresh_token(user_id, pwd_v=pwd_v)
    await redis.setex(
        f"refresh_jti:{jti}",
        settings.refresh_token_expire_days * 86400,
        user_id,
    )
    response.set_cookie("access_token", access, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)
```

- [ ] **Step 5: Update `/refresh` endpoint in `backend/app/routers/auth.py` — add pwd_v check**

In the `refresh` endpoint, after fetching the user from DB and checking `is_banned`, and before calling `_set_auth_cookies`, insert:

```python
# Reject if password was changed after this refresh token was issued
token_pwd_v = int(payload.get("pwd_v", 0))
stored_raw = await redis.get(f"user_pwd_version:{str(user.id)}")
stored_pwd_v = int(stored_raw) if stored_raw else 0
if token_pwd_v != stored_pwd_v:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalidated")
```

- [ ] **Step 6: Run all deps and related tests**

```bash
cd backend && python -m pytest tests/test_deps.py -v
```

**Backward-compatibility:** The check `int(payload.get("pwd_v", 0))` treats tokens without the claim as version 0. The check `int(stored_raw) if stored_raw else 0` treats a missing Redis key as version 0. So `0 == 0` → passes. All existing authenticated users with old tokens (no `pwd_v` claim) will continue to work because their version is 0 and the Redis key doesn't exist yet (also 0). **This is the critical invariant — do not remove the default-0 fallbacks.**

The existing test `test_refresh_endpoint_banned_user_returns_403` uses `AsyncMock` for redis which returns `None` from `.get()` by default — treated as version 0, no mismatch, test still passes. The existing `test_get_current_user_banned_raises_403` and `test_get_current_user_no_cookie_raises` will also continue to pass because they either don't reach the pwd_v check (no cookie) or the token has no `pwd_v` claim (treated as 0) and redis.get returns None (treated as 0).

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
cd backend && python -m pytest -x -q
```

Fix any failures before continuing.

- [ ] **Step 8: Commit**

```bash
git add backend/app/deps.py backend/app/routers/auth.py backend/tests/test_deps.py
git commit -m "feat: add session invalidation via Redis pwd_v version counter"
```

---

## Task 4: `send_reset_email` in email service

**Files:**
- Modify: `backend/app/services/email_service.py`
- Modify: `backend/tests/services/test_email_service.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/services/test_email_service.py`:

```python
@pytest.mark.asyncio
async def test_send_reset_email_calls_resend():
    from app.services.email_service import send_reset_email

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await send_reset_email(
            api_key="re_test",
            from_address="noreply@test.com",
            from_name="Test VPN",
            to_email="user@gmail.com",
            reset_url="https://example.com/reset-password?token=xyz123",
        )

    mock_client.post.assert_called_once()
    payload = mock_client.post.call_args[1]["json"]
    assert payload["to"] == ["user@gmail.com"]
    assert payload["subject"] == "Сброс пароля"
    assert "xyz123" in payload["html"]
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && python -m pytest tests/services/test_email_service.py::test_send_reset_email_calls_resend -v
```

- [ ] **Step 3: Add `send_reset_email` to `backend/app/services/email_service.py`**

```python
async def send_reset_email(
    api_key: str,
    from_address: str,
    from_name: str,
    to_email: str,
    reset_url: str,
) -> None:
    """Send password reset link via Resend REST API."""
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Сброс пароля</h2>
      <p>Нажмите кнопку ниже, чтобы сбросить пароль. Ссылка действительна 1 час.</p>
      <a href="{reset_url}"
         style="display:inline-block;padding:12px 24px;background:#06b6d4;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Сбросить пароль
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Если вы не запрашивали сброс пароля — проигнорируйте это письмо.
      </p>
    </div>
    """
    payload = {
        "from": f"{from_name} <{from_address}>",
        "to": [to_email],
        "subject": "Сброс пароля",
        "html": html,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd backend && python -m pytest tests/services/test_email_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/services/test_email_service.py
git commit -m "feat: add send_reset_email function"
```

---

## Task 5: Password reset schemas + backend endpoints

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/routers/auth.py`
- Create: `backend/tests/routers/test_reset_password.py`

- [ ] **Step 1: Add schemas to `backend/app/schemas/auth.py`**

At the bottom of the file, add:

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

Also add `from pydantic import Field` to the imports at the top.

- [ ] **Step 2: Write failing tests**

Create `backend/tests/routers/test_reset_password.py`:

```python
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from app.redis_client import get_redis
from app.models.auth_provider import AuthProvider, ProviderType


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_reset_request_email_not_found_returns_404():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # email not in DB
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # not rate limited

    with patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=True)):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/request", json={"email": "notfound@example.com"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert "не найден" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_request_rate_limited_returns_429():
    db = AsyncMock()
    redis = AsyncMock()

    with patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=False)):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/request", json={"email": "user@example.com"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_reset_request_found_sends_email_and_returns_200():
    provider = MagicMock(spec=AuthProvider)
    provider.provider = ProviderType.email
    provider.provider_user_id = "user@example.com"
    provider.user_id = uuid.uuid4()

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.setex = AsyncMock()

    with (
        patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=True)),
        patch("app.routers.auth.get_setting", new=AsyncMock(return_value="noreply@test.com")),
        patch("app.routers.auth.send_reset_email", new=AsyncMock()),
    ):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/request", json={"email": "user@example.com"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_reset_confirm_invalid_token_returns_400():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # token not in Redis

    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/auth/reset-password/confirm", json={
                "token": "nonexistent-token",
                "new_password": "NewPass1"
            })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "недействительна" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_confirm_weak_password_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/reset-password/confirm", json={
            "token": "sometoken",
            "new_password": "weakpassword"  # no uppercase, no digit
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_confirm_valid_token_updates_password():
    user_id = str(uuid.uuid4())

    provider = MagicMock(spec=AuthProvider)
    provider.password_hash = "old_hash"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=user_id.encode())
    redis.delete = AsyncMock()
    redis.incr = AsyncMock()

    with patch("app.routers.auth.hash_password", return_value="new_hash"):
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/auth/reset-password/confirm", json={
                    "token": "validtoken123",
                    "new_password": "NewPass1"
                })
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert provider.password_hash == "new_hash"
    redis.incr.assert_called_once()
    redis.delete.assert_called_once()
```

- [ ] **Step 3: Run tests — expect FAIL (endpoints don't exist yet)**

```bash
cd backend && python -m pytest tests/routers/test_reset_password.py -v
```

- [ ] **Step 4: Add endpoints to `backend/app/routers/auth.py`**

Add the following imports at the top if not already present:
```python
import secrets
from app.schemas.auth import ResetPasswordRequestSchema, ResetPasswordConfirmSchema
from app.services.auth.password_service import hash_password
from app.services.email_service import send_reset_email
```

Add the two new endpoints after the existing `/verify-email/confirm` endpoint:

```python
@router.post("/reset-password/request")
async def reset_password_request(
    data: ResetPasswordRequestSchema,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    email_lower = data.email.lower()
    rate_key = f"reset_pwd_rate:{email_lower}"
    if not await check_rate_limit(redis, rate_key, 3, 3600):
        raise HTTPException(status_code=429, detail="Слишком много попыток. Попробуйте позже.")

    result = await db.execute(
        _select(AuthProvider).where(
            AuthProvider.provider == ProviderType.email,
            AuthProvider.provider_user_id == email_lower,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=404, detail="Email не найден")

    token = secrets.token_urlsafe(32)
    await redis.setex(f"reset_pwd:{token}", 3600, str(provider.user_id))

    api_key = await get_setting_decrypted(db, "resend_api_key")
    if not api_key:
        raise HTTPException(status_code=503, detail="Email-сервис не настроен")
    from_address = await get_setting(db, "email_from_address") or "noreply@example.com"
    from_name = await get_setting(db, "email_from_name") or "VPN Service"
    site_url = settings.site_url.rstrip("/")
    reset_url = f"{site_url}/reset-password?token={token}"

    try:
        await send_reset_email(
            api_key=api_key,
            from_address=from_address,
            from_name=from_name,
            to_email=email_lower,
            reset_url=reset_url,
        )
    except Exception as exc:
        logger.exception("Failed to send reset email: %s", exc)
        raise HTTPException(status_code=503, detail="Ошибка отправки письма")

    return {"ok": True}


@router.post("/reset-password/confirm")
async def reset_password_confirm(
    data: ResetPasswordConfirmSchema,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user_id_raw = await redis.get(f"reset_pwd:{data.token}")
    if not user_id_raw:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или истекла")

    user_id_str = user_id_raw if isinstance(user_id_raw, str) else user_id_raw.decode()
    try:
        user_uuid = _uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или истекла")

    result = await db.execute(
        _select(AuthProvider).where(
            AuthProvider.user_id == user_uuid,
            AuthProvider.provider == ProviderType.email,
        )
    )
    provider = result.scalar_one_or_none()
    if provider:
        provider.password_hash = hash_password(data.new_password)
        await db.commit()

    await redis.delete(f"reset_pwd:{data.token}")
    await redis.incr(f"user_pwd_version:{user_id_str}")

    return {"ok": True}
```

Note: `hash_password` is already imported in `auth.py`? Check — if not, add `from app.services.auth.password_service import hash_password`.

- [ ] **Step 5: Run reset-password tests — expect PASS**

```bash
cd backend && python -m pytest tests/routers/test_reset_password.py -v
```

- [ ] **Step 6: Run full backend tests**

```bash
cd backend && python -m pytest -x -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/routers/auth.py backend/tests/routers/test_reset_password.py
git commit -m "feat: add password reset endpoints (request + confirm)"
```

---

## Task 6: Change password + edit display name — backend

**Files:**
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/routers/users.py`
- Modify: `backend/tests/routers/test_users.py`

- [ ] **Step 1: Update `backend/app/schemas/user.py`**

```python
from pydantic import BaseModel, field_validator
from datetime import datetime
from app.schemas.auth import validate_password_strength


class ProviderInfo(BaseModel):
    type: str
    username: str | None
    identifier: str | None = None


class UserProfileResponse(BaseModel):
    id: str
    display_name: str
    is_admin: bool
    has_made_payment: bool
    created_at: datetime
    providers: list[ProviderInfo]
    email_verified: bool | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


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

- [ ] **Step 2: Write failing tests**

Add the following imports to `backend/tests/routers/test_users.py` (alongside existing imports):

```python
from app.redis_client import get_redis
```

Add to `backend/tests/routers/test_users.py` (after existing helpers, before or after existing tests):

```python
# --- helpers (add if not already present) ---
def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep

def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep

# --- change password tests ---

@pytest.mark.asyncio
async def test_change_password_no_email_provider_returns_400():
    user = _make_user()
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # no email provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")  # pwd_v check

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/users/me/password", json={
                "old_password": "OldPass1",
                "new_password": "NewPass1"
            })
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_wrong_old_password_returns_400():
    user = _make_user()
    provider = _make_provider(user.id, ProviderType.email, provider_user_id="u@test.com")
    provider.password_hash = "some_hash"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")

    with patch("app.routers.users.verify_password", return_value=False):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch("/api/users/me/password", json={
                    "old_password": "WrongPass1",
                    "new_password": "NewPass1"
                })
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 400
    assert "Неверный" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_change_password_success():
    user = _make_user()
    provider = _make_provider(user.id, ProviderType.email, provider_user_id="u@test.com")
    provider.password_hash = "old_hash"

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = provider
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"0")
    redis.incr = AsyncMock()

    with (
        patch("app.routers.users.verify_password", return_value=True),
        patch("app.routers.users.hash_password", return_value="new_hash"),
    ):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = _override_db(db)
        app.dependency_overrides[get_redis] = _override_redis(redis)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch("/api/users/me/password", json={
                    "old_password": "OldPass1",
                    "new_password": "NewPass1"
                })
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert provider.password_hash == "new_hash"
    redis.incr.assert_called_once()


# --- update display name tests ---

@pytest.mark.asyncio
async def test_update_display_name_success():
    user = _make_user(display_name="OldName")
    db = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/users/me", json={"display_name": "  NewName  "})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.display_name == "NewName"  # stripped


@pytest.mark.asyncio
async def test_update_display_name_empty_returns_422():
    user = _make_user()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/api/users/me", json={"display_name": "   "})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
cd backend && python -m pytest tests/routers/test_users.py::test_change_password_success tests/routers/test_users.py::test_update_display_name_success -v
```

- [ ] **Step 4: Add endpoints to `backend/app/routers/users.py`**

Add imports at the top:
```python
from redis.asyncio import Redis
from app.deps import get_current_user, get_redis  # add get_redis
from app.schemas.user import UserProfileResponse, ProviderInfo, ChangePasswordRequest, UpdateDisplayNameRequest
from app.services.auth.password_service import hash_password, verify_password
```

Add at the end of the file:

```python
@router.patch("/me/password", status_code=200)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.user_id == current_user.id,
            AuthProvider.provider == ProviderType.email,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email-провайдер не привязан")
    if not provider.password_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пароль не установлен для этого провайдера")
    if not verify_password(data.old_password, provider.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль")

    provider.password_hash = hash_password(data.new_password)
    await db.commit()
    await redis.incr(f"user_pwd_version:{str(current_user.id)}")
    return {"ok": True}


@router.patch("/me", status_code=200)
async def update_display_name(
    data: UpdateDisplayNameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    current_user.display_name = data.display_name
    await db.commit()
    return {"ok": True}
```

Note: `get_redis` needs to be imported in `users.py`. Check if it's already imported — if not, add `from app.redis_client import get_redis` and adjust the import of `get_redis` from `deps.py` if needed. The `get_redis` function lives in `app.redis_client`, not `app.deps`. Look at how other routers import it.

- [ ] **Step 5: Run all user tests**

```bash
cd backend && python -m pytest tests/routers/test_users.py -v
```

- [ ] **Step 6: Run full backend test suite**

```bash
cd backend && python -m pytest -x -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/user.py backend/app/routers/users.py backend/tests/routers/test_users.py
git commit -m "feat: add change-password and update-display-name endpoints"
```

---

## Task 7: Banner spacing fix

**Files:**
- Modify: `frontend/src/components/EmailVerificationBanner.tsx`

This is a one-line change. No test needed.

- [ ] **Step 1: Add `mb-4` to root div**

In `frontend/src/components/EmailVerificationBanner.tsx` line 49, find:
```jsx
<div className="rounded-card border border-yellow-500/30 bg-yellow-500/5 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
```
Replace with:
```jsx
<div className="mb-4 rounded-card border border-yellow-500/30 bg-yellow-500/5 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EmailVerificationBanner.tsx
git commit -m "fix: add bottom margin to email verification banner"
```

---

## Task 8: Telegram icon + `TelegramLinkButton` component

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/pages/ProfilePage.tsx`

The new SVG (bi-telegram, fill="#2AABEE") replaces the old path in both files. `TelegramLinkButton` is extracted in ProfilePage to fix the ref timing bug.

- [ ] **Step 1: Replace Telegram SVG in `LoginPage.tsx`**

In `LoginPage.tsx` inside `TelegramLoginButton`'s styled div (around line 89-91), replace the existing `<svg>` element with:

```jsx
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 16 16">
  <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M8.287 5.906q-1.168.486-4.666 2.01-.567.225-.595.442c-.03.243.275.339.69.47l.175.055c.408.133.958.288 1.243.294q.39.01.868-.32 3.269-2.206 3.374-2.23c.05-.012.12-.026.166.016s.042.12.037.141c-.03.129-1.227 1.241-1.846 1.817-.193.18-.33.307-.358.336a8 8 0 0 1-.188.186c-.38.366-.664.64.015 1.088.327.216.589.393.85.571.284.194.568.387.936.629q.14.092.27.187c.331.236.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.4 1.4 0 0 0-.013-.315.34.34 0 0 0-.114-.217.53.53 0 0 0-.31-.093c-.3.005-.763.166-2.984 1.09" fill="#2AABEE"/>
</svg>
```

- [ ] **Step 2: Extract `TelegramLinkButton` in `ProfilePage.tsx`**

At the top of `ProfilePage.tsx`, remove `telegramLinkRef` from the component and the associated `useEffect` (lines 122 and 132-181). Remove the `useRef` import if it becomes unused elsewhere (check: `telegramLinkRef` is the only ref).

Add a new `TelegramLinkButton` component before `ProfilePage`:

```tsx
function TelegramLinkButton({
  botUsername,
  onAuth,
}: {
  botUsername: string
  onAuth: (user: Record<string, unknown>) => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !botUsername) return
    ;(window as unknown as Record<string, unknown>).__onTelegramLink = onAuth

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', '__onTelegramLink(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    ref.current.appendChild(script)

    const observer = new MutationObserver(() => {
      const iframe = ref.current?.querySelector('iframe')
      if (!iframe) return
      observer.disconnect()
      const applyScale = () => {
        const containerWidth = ref.current?.offsetWidth
        const iframeWidth = iframe.offsetWidth
        if (!containerWidth || !iframeWidth) { requestAnimationFrame(applyScale); return }
        iframe.style.opacity = '0'
        iframe.style.position = 'absolute'
        iframe.style.top = '0'
        iframe.style.left = '0'
        iframe.style.transformOrigin = 'left top'
        iframe.style.transform = `scaleX(${containerWidth / iframeWidth})`
        iframe.style.cursor = 'pointer'
      }
      applyScale()
    })
    observer.observe(ref.current, { childList: true, subtree: true })

    return () => {
      observer.disconnect()
      delete (window as unknown as Record<string, unknown>).__onTelegramLink
    }
  }, [botUsername, onAuth])

  return (
    <div className="group relative h-[42px]">
      <div className="absolute inset-0 flex items-center gap-2.5 rounded-input bg-white/5 px-3 text-sm text-text-secondary group-hover:text-text-primary pointer-events-none select-none transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
          <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M8.287 5.906q-1.168.486-4.666 2.01-.567.225-.595.442c-.03.243.275.339.69.47l.175.055c.408.133.958.288 1.243.294q.39.01.868-.32 3.269-2.206 3.374-2.23c.05-.012.12-.026.166.016s.042.12.037.141c-.03.129-1.227 1.241-1.846 1.817-.193.18-.33.307-.358.336a8 8 0 0 1-.188.186c-.38.366-.664.64.015 1.088.327.216.589.393.85.571.284.194.568.387.936.629q.14.092.27.187c.331.236.63.448.997.414.214-.02.435-.22.547-.82.265-1.417.786-4.486.906-5.751a1.4 1.4 0 0 0-.013-.315.34.34 0 0 0-.114-.217.53.53 0 0 0-.31-.093c-.3.005-.763.166-2.984 1.09" fill="#2AABEE"/>
        </svg>
        Telegram
      </div>
      <div ref={ref} className="absolute inset-0 overflow-hidden" />
    </div>
  )
}
```

In the JSX where Telegram was rendered (around line 311-329), replace the entire `{canAddTelegram && (<div>...</div>)}` block with:

```tsx
{canAddTelegram && oauthConfig?.telegram_bot_username && (
  <div>
    <TelegramLinkButton
      botUsername={oauthConfig.telegram_bot_username}
      onAuth={async (tgUser) => {
        try {
          const res = await api.post<{ ok: boolean; notification?: string | null }>(
            '/api/users/me/providers/telegram',
            tgUser,
          )
          queryClient.invalidateQueries({ queryKey: ['me'] })
          setLinkTelegramError(null)
          setLinkTelegramNotification(res.notification ?? null)
        } catch (e) {
          setLinkTelegramError(e instanceof ApiError ? e.detail : 'Ошибка Telegram')
        }
      }}
    />
    {linkTelegramError && <p className="mt-1 text-xs text-red-400">{linkTelegramError}</p>}
    {linkTelegramNotification && (
      <div className="mt-2 flex items-start gap-2 rounded-input bg-amber-500/10 border border-amber-500/20 px-3 py-2">
        <AlertCircle size={14} className="text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-200 leading-relaxed">{linkTelegramNotification}</p>
      </div>
    )}
  </div>
)}
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Fix any type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/pages/ProfilePage.tsx
git commit -m "feat: replace Telegram icon and fix profile TelegramLinkButton"
```

---

## Task 9: Forgot password inline flow in `LoginPage.tsx`

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`

- [ ] **Step 1: Update mode type and add forgot-password state**

Change the `Mode` type (line 100):
```tsx
type Mode = 'login' | 'register' | 'forgot' | 'reset-sent'
```

Add `forgotEmail` state alongside existing state:
```tsx
const [forgotEmail, setForgotEmail] = useState('')
```

- [ ] **Step 2: Add password strength validator helper**

Add a client-side validator near the top of the file (outside the component):

```tsx
function isStrongPassword(p: string) {
  return p.length >= 8 && /[A-Z]/.test(p) && /[a-z]/.test(p) && /[0-9]/.test(p)
}
```

- [ ] **Step 3: Add forgot-password submit handler**

Inside `LoginPage`, add:

```tsx
async function handleForgotSubmit(e: React.FormEvent) {
  e.preventDefault()
  setError(null)
  setLoading(true)
  try {
    await api.post('/api/auth/reset-password/request', { email: forgotEmail })
    setMode('reset-sent')
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      setError('Email не найден')
    } else if (err instanceof ApiError && err.status === 429) {
      setError('Слишком много попыток. Попробуйте позже.')
    } else {
      setError('Ошибка сети')
    }
  } finally {
    setLoading(false)
  }
}
```

Check how `ApiError` exposes the HTTP status — look at `frontend/src/lib/api.ts` and use the correct property (likely `err.status` or `err.statusCode`).

- [ ] **Step 4: Add "Забыли пароль?" link in login mode**

In the email form (`oauthConfig?.email_enabled !== false && <form...>`), after the password field `<div>` and before the error paragraph, add:

```tsx
{mode === 'login' && (
  <div className="text-right">
    <button
      type="button"
      onClick={() => { setMode('forgot'); setError(null); setForgotEmail(email) }}
      className="text-xs text-text-muted hover:text-accent transition-colors"
    >
      Забыли пароль?
    </button>
  </div>
)}
```

- [ ] **Step 5: Add `forgot` and `reset-sent` mode UI**

Replace the form render block (currently only renders when `oauthConfig?.email_enabled !== false`) to handle all modes. Below the existing form, add:

```tsx
{mode === 'forgot' && (
  <form onSubmit={handleForgotSubmit} className="space-y-4">
    <div>
      <label className="block text-sm text-text-secondary mb-1">Email</label>
      <input
        type="email"
        value={forgotEmail}
        onChange={e => setForgotEmail(e.target.value)}
        required
        className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
        placeholder="you@example.com"
      />
    </div>
    {error && <p className="text-sm text-red-400">{error}</p>}
    <button
      type="submit"
      disabled={loading}
      className="w-full py-2 rounded-input bg-accent text-background font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
    >
      {loading ? 'Отправка...' : 'Отправить письмо'}
    </button>
    <button
      type="button"
      onClick={() => { setMode('login'); setError(null) }}
      className="w-full text-sm text-text-muted hover:text-text-primary transition-colors"
    >
      ← Назад к входу
    </button>
  </form>
)}

{mode === 'reset-sent' && (
  <div className="space-y-4">
    <p className="text-sm text-text-secondary">
      Если адрес <span className="text-text-primary font-medium">{forgotEmail}</span> зарегистрирован, письмо со ссылкой для сброса пароля было отправлено.
    </p>
    <button
      type="button"
      onClick={() => { setMode('login'); setError(null) }}
      className="w-full py-2 rounded-input bg-surface border border-border-neutral text-sm text-text-primary hover:border-accent transition-colors"
    >
      ← Назад к входу
    </button>
  </div>
)}
```

Also ensure the email/password form (`<form onSubmit={handleSubmit}>`) only renders when `mode === 'login' || mode === 'register'`. Wrap the existing form render with `{(mode === 'login' || mode === 'register') && oauthConfig?.email_enabled !== false && <form...>}`.

The tabs (Войти / Регистрация) should also only show in `login` or `register` mode — wrap `<div className="flex gap-2 mb-6">` similarly.

- [ ] **Step 6: Add password strength hint on register**

In the password field in the registration form, add a small hint below when in register mode:

```tsx
{mode === 'register' && password && !isStrongPassword(password) && (
  <p className="mt-1 text-xs text-text-muted">Мин. 8 символов, заглавная буква, строчная буква, цифра</p>
)}
```

- [ ] **Step 7: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat: add forgot-password inline flow to LoginPage"
```

---

## Task 10: `ResetPasswordPage` + register public route

**Files:**
- Create: `frontend/src/pages/ResetPasswordPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/pages/ResetPasswordPage.tsx`**

```tsx
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '@/lib/api'
import { AlertCircle, CheckCircle } from 'lucide-react'

function isStrongPassword(p: string) {
  return p.length >= 8 && /[A-Z]/.test(p) && /[a-z]/.test(p) && /[0-9]/.test(p)
}

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token')

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral text-center space-y-4">
          <AlertCircle className="mx-auto text-red-400" size={40} />
          <p className="text-text-primary font-semibold">Неверная ссылка</p>
          <Link to="/login" className="block text-sm text-accent hover:underline">Войти</Link>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral text-center space-y-4">
          <CheckCircle className="mx-auto text-green-400" size={40} />
          <p className="text-text-primary font-semibold">Пароль успешно изменён</p>
          <Link
            to="/login"
            className="block w-full py-2 rounded-input bg-accent text-background font-medium text-sm text-center hover:opacity-90 transition-opacity"
          >
            Войти
          </Link>
        </div>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!isStrongPassword(newPassword)) {
      setError('Пароль должен содержать не менее 8 символов, заглавную букву, строчную букву и цифру')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают')
      return
    }

    setLoading(true)
    try {
      await api.post('/api/auth/reset-password/confirm', { token, new_password: newPassword })
      setSuccess(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral">
        <h1 className="text-xl font-bold text-text-primary mb-6">Новый пароль</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Новый пароль</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="Минимум 8 символов"
            />
            {newPassword && !isStrongPassword(newPassword) && (
              <p className="mt-1 text-xs text-text-muted">Мин. 8 символов, заглавная буква, строчная буква, цифра</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Повторите пароль</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="Повторите новый пароль"
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <p className="mt-1 text-xs text-red-400">Пароли не совпадают</p>
            )}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-input bg-accent text-background font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'Сохранение...' : 'Сохранить пароль'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Register route in `frontend/src/App.tsx`**

Add import at the top:
```tsx
import ResetPasswordPage from '@/pages/ResetPasswordPage'
```

Add route at **top-level inside `<Routes>`**, after the `/verify-email` route and **before** the `ProtectedRoute` and `AdminRoute` wrappers. It must also appear **before** the catch-all `<Route path="*" element={<Navigate to="/" replace />}` at line 69. The correct placement is alongside `/login`, `/auth/google/callback`, and `/verify-email`:

```tsx
<Route path="/login" element={<LoginPage />} />
<Route path="/auth/google/callback" element={<GoogleCallbackPage />} />
<Route path="/auth/vk/callback" element={<VKCallbackPage />} />
<Route path="/verify-email" element={<VerifyEmailPage />} />
<Route path="/reset-password" element={<ResetPasswordPage />} />  {/* ← add here */}

{/* Admin routes */}
<Route element={<AdminRoute />}>
  ...
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ResetPasswordPage.tsx frontend/src/App.tsx
git commit -m "feat: add ResetPasswordPage and public /reset-password route"
```

---

## Task 11: Inline display name editing in `ProfilePage.tsx`

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Add state and imports**

Add `Pencil, Check, X` to the lucide-react import line.

Add state inside `ProfilePage`:
```tsx
const [isEditingName, setIsEditingName] = useState(false)
const [nameInput, setNameInput] = useState('')
const [nameError, setNameError] = useState<string | null>(null)
```

Add mutation:
```tsx
const updateNameMutation = useMutation({
  mutationFn: (display_name: string) => api.patch('/api/users/me', { display_name }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['me'] })
    setIsEditingName(false)
    setNameError(null)
  },
  onError: (e) => setNameError(e instanceof ApiError ? e.detail : 'Ошибка'),
})
```

- [ ] **Step 2: Replace static name display with inline-editable version**

In the account info block (around line 206-208), find:
```tsx
<p className="font-semibold text-text-primary">{user.display_name}</p>
```

Replace with:
```tsx
{isEditingName ? (
  <div className="flex items-center gap-1.5">
    <input
      type="text"
      value={nameInput}
      onChange={e => setNameInput(e.target.value)}
      onKeyDown={e => {
        if (e.key === 'Enter') {
          e.preventDefault()
          const trimmed = nameInput.trim()
          if (!trimmed) { setNameError('Имя не может быть пустым'); return }
          if (trimmed.length > 64) { setNameError('Не более 64 символов'); return }
          updateNameMutation.mutate(trimmed)
        }
        if (e.key === 'Escape') { setIsEditingName(false); setNameError(null) }
      }}
      autoFocus
      maxLength={64}
      className="bg-background border border-border-neutral rounded-input px-2 py-0.5 text-sm text-text-primary focus:outline-none focus:border-accent font-semibold"
    />
    <button
      onClick={() => {
        const trimmed = nameInput.trim()
        if (!trimmed) { setNameError('Имя не может быть пустым'); return }
        if (trimmed.length > 64) { setNameError('Не более 64 символов'); return }
        updateNameMutation.mutate(trimmed)
      }}
      disabled={updateNameMutation.isPending}
      className="text-accent hover:text-accent/80 transition-colors disabled:opacity-50"
    >
      {updateNameMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
    </button>
    <button
      onClick={() => { setIsEditingName(false); setNameError(null) }}
      className="text-text-muted hover:text-text-primary transition-colors"
    >
      <X size={14} />
    </button>
  </div>
) : (
  <div className="flex items-center gap-1.5">
    <p className="font-semibold text-text-primary">{user.display_name}</p>
    <button
      onClick={() => { setNameInput(user.display_name); setIsEditingName(true); setNameError(null) }}
      className="text-text-muted hover:text-text-primary transition-colors"
    >
      <Pencil size={13} />
    </button>
  </div>
)}
{nameError && <p className="text-xs text-red-400 mt-0.5">{nameError}</p>}
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat: add inline display name editing in profile"
```

---

## Task 12: Change password UI in `ProfilePage.tsx`

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Add state**

Add `KeyRound` to the lucide-react import.

Add state:
```tsx
const [changePasswordOpen, setChangePasswordOpen] = useState(false)
const [oldPassword, setOldPassword] = useState('')
const [newPassword, setNewPassword] = useState('')
const [confirmNewPassword, setConfirmNewPassword] = useState('')
const [changePasswordError, setChangePasswordError] = useState<string | null>(null)
```

Add a shared helper near the top of the file (or reuse from Task 9 — keep it consistent, define once):
```tsx
function isStrongPassword(p: string) {
  return p.length >= 8 && /[A-Z]/.test(p) && /[a-z]/.test(p) && /[0-9]/.test(p)
}
```

Add mutation:
```tsx
const changePasswordMutation = useMutation({
  mutationFn: ({ old_password, new_password }: { old_password: string; new_password: string }) =>
    api.patch('/api/users/me/password', { old_password, new_password }),
  onSuccess: () => {
    setChangePasswordOpen(false)
    setOldPassword('')
    setNewPassword('')
    setConfirmNewPassword('')
    setChangePasswordError(null)
  },
  onError: (e) => setChangePasswordError(e instanceof ApiError ? e.detail : 'Ошибка'),
})
```

- [ ] **Step 2: Update email provider row in "Привязанные аккаунты"**

Find the provider row rendering (around line 244-270). Inside the `flex items-center justify-between` row, add a `KeyRound` button for email providers. The right-side action area currently has just the trash button — change it to:

```tsx
<div className="flex items-center gap-1.5 shrink-0">
  {p.type === 'email' && (
    <button
      onClick={() => { setChangePasswordOpen(v => !v); setChangePasswordError(null) }}
      className="text-text-muted hover:text-accent transition-colors"
      title="Изменить пароль"
    >
      <KeyRound size={14} />
    </button>
  )}
  {canUnlink && (
    <button
      onClick={() => unlinkMutation.mutate(p.type)}
      disabled={unlinkMutation.isPending}
      className="text-text-muted hover:text-red-400 transition-colors disabled:opacity-50"
      title="Отвязать"
    >
      {unlinkMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
    </button>
  )}
</div>
```

After the provider row `div` (but still inside the `map`), for email providers add the inline form:

```tsx
{p.type === 'email' && changePasswordOpen && (
  <div className="mt-2 space-y-2">
    <input
      type="password"
      value={oldPassword}
      onChange={e => setOldPassword(e.target.value)}
      placeholder="Текущий пароль"
      className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
    />
    <input
      type="password"
      value={newPassword}
      onChange={e => setNewPassword(e.target.value)}
      placeholder="Новый пароль"
      className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
    />
    {newPassword && !isStrongPassword(newPassword) && (
      <p className="text-xs text-text-muted">Мин. 8 символов, заглавная, строчная, цифра</p>
    )}
    <input
      type="password"
      value={confirmNewPassword}
      onChange={e => setConfirmNewPassword(e.target.value)}
      placeholder="Повторите новый пароль"
      className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
    />
    {confirmNewPassword && newPassword !== confirmNewPassword && (
      <p className="text-xs text-red-400">Пароли не совпадают</p>
    )}
    {changePasswordError && <p className="text-xs text-red-400">{changePasswordError}</p>}
    <div className="flex gap-2">
      <button
        onClick={() => {
          if (!isStrongPassword(newPassword)) {
            setChangePasswordError('Пароль должен содержать не менее 8 символов, заглавную букву, строчную букву и цифру')
            return
          }
          if (newPassword !== confirmNewPassword) {
            setChangePasswordError('Пароли не совпадают')
            return
          }
          changePasswordMutation.mutate({ old_password: oldPassword, new_password: newPassword })
        }}
        disabled={changePasswordMutation.isPending || !oldPassword || !newPassword || !confirmNewPassword}
        className="flex-1 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50"
      >
        {changePasswordMutation.isPending ? 'Сохранение…' : 'Сохранить'}
      </button>
      <button
        onClick={() => { setChangePasswordOpen(false); setChangePasswordError(null); setOldPassword(''); setNewPassword(''); setConfirmNewPassword('') }}
        className="px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs"
      >
        Отмена
      </button>
    </div>
  </div>
)}
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Run full backend tests to confirm no regressions**

```bash
cd backend && python -m pytest -x -q
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat: add change-password UI to profile email provider row"
```

---

## Final verification

- [ ] Start dev server and verify all five features visually:
  1. Login page → "Забыли пароль?" visible, leads to email input; back button works
  2. `/reset-password?token=test` → shows "Неверная ссылка" for invalid token
  3. Profile → pencil icon next to name; clicking enables edit; Enter saves, Escape cancels
  4. Profile → key icon on email row; clicking expands change-password form
  5. Profile → Telegram button (if enabled) is clickable; new icon visible in both login and profile
  6. Home page → email verification banner has spacing below it

- [ ] Run complete backend test suite one final time:

```bash
cd backend && python -m pytest -q
```

- [ ] Run TypeScript check:

```bash
cd frontend && npx tsc --noEmit
```
