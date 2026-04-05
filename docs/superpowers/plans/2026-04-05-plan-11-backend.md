# Plan 11: Email Verification & Admin Enhancements — Backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add email verification, user ban, admin user actions, and new admin settings to the backend.

**Architecture:** Three Alembic migrations add `email_verified` and `is_banned` columns and seed new settings keys. New endpoints handle email verification flow via Resend. Existing auth deps gain ban checks. Admin router gets ban/admin/reset-subscription endpoints.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, Redis, httpx (Resend API), pytest-asyncio, pytest-httpx, uv

**Run all tests:** `cd backend && uv run pytest -x -q`
**Run single test:** `cd backend && uv run pytest tests/path/to/test.py::test_name -v`
**Alembic:** `cd backend && uv run alembic upgrade head`

---

## File Map

**New files:**
- `backend/alembic/versions/a1b2c3d4e5f6_add_email_verified.py` — Migration A
- `backend/alembic/versions/b2c3d4e5f6a7_add_is_banned.py` — Migration B
- `backend/alembic/versions/c3d4e5f6a7b8_seed_auth_settings.py` — Migration C (seed)
- `backend/app/services/email_service.py` — Resend email sender
- `backend/tests/services/test_email_service.py`
- `backend/tests/routers/test_verify_email.py`
- `backend/tests/routers/test_admin_user_actions.py`

**Modified files:**
- `backend/app/models/auth_provider.py` — add `email_verified` column
- `backend/app/models/user.py` — add `is_banned` column
- `backend/app/deps.py` — ban check in `get_current_user`
- `backend/app/routers/auth.py` — ban check in `refresh`, registration guards, verify-email endpoints, `get_oauth_config` update
- `backend/app/routers/users.py` — `get_me` returns `email_verified`, `link_email` sets `email_verified=False`
- `backend/app/routers/subscriptions.py` — email guard in `activate_trial`, squad fallback
- `backend/app/routers/admin.py` — `_build_list_item` update, `get_user_detail` update, new ban/admin/reset endpoints
- `backend/app/schemas/auth.py` — `OAuthConfigResponse` + `email_verification_required`
- `backend/app/schemas/user.py` — `UserProfileResponse` + `email_verified`
- `backend/app/schemas/admin.py` — `ProviderInfo` + `email_verified`, `UserAdminListItem` + 3 fields, `UserAdminDetail` + 3 fields
- `backend/tests/routers/test_auth_oauth_config.py` — add test for new field
- `backend/tests/routers/test_auth_email.py` — add domain whitelist tests
- `backend/tests/routers/test_subscriptions.py` — add email guard test
- `backend/tests/test_deps.py` — add ban test

---

## Task 1: Migration A — add `email_verified` to `auth_providers`

**Files:**
- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_email_verified.py`
- Modify: `backend/app/models/auth_provider.py`

- [ ] **Step 1: Add `email_verified` column to `AuthProvider` model**

In `backend/app/models/auth_provider.py`, add import for `Boolean` (already imported) and add the column after `password_hash`:

```python
email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 2: Create migration file**

Create `backend/alembic/versions/a1b2c3d4e5f6_add_email_verified.py`:

```python
"""add email_verified to auth_providers

Revision ID: a1b2c3d4e5f6
Revises: b3c4d5e6f7a8
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'auth_providers',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('auth_providers', 'email_verified')
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/auth_provider.py backend/alembic/versions/a1b2c3d4e5f6_add_email_verified.py
git commit -m "feat: add email_verified column to auth_providers"
```

---

## Task 2: Migration B — add `is_banned` to `users`

**Files:**
- Create: `backend/alembic/versions/b2c3d4e5f6a7_add_is_banned.py`
- Modify: `backend/app/models/user.py`

- [ ] **Step 1: Add `is_banned` column to `User` model**

In `backend/app/models/user.py`, add after `has_made_payment`:

```python
is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 2: Create migration file**

Create `backend/alembic/versions/b2c3d4e5f6a7_add_is_banned.py`:

```python
"""add is_banned to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_banned')
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/b2c3d4e5f6a7_add_is_banned.py
git commit -m "feat: add is_banned column to users"
```

---

## Task 3: Migration C — seed new settings

**Files:**
- Create: `backend/alembic/versions/c3d4e5f6a7b8_seed_auth_settings.py`

- [ ] **Step 1: Create seed migration**

Create `backend/alembic/versions/c3d4e5f6a7b8_seed_auth_settings.py`:

```python
"""seed auth and remnawave settings

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-05 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [
    ("registration_enabled", "true", False),
    ("email_verification_enabled", "false", False),
    (
        "allowed_email_domains",
        "gmail.com,mail.ru,yandex.ru,yahoo.com,outlook.com,hotmail.com,icloud.com,rambler.ru,bk.ru,list.ru,inbox.ru,proton.me,protonmail.com,me.com,live.com",
        False,
    ),
    ("resend_api_key", "", True),
    ("email_from_address", "", False),
    ("email_from_name", "", False),
    ("remnawave_trial_squad_uuids", "", False),
    ("remnawave_paid_squad_uuids", "", False),
]


def upgrade() -> None:
    conn = op.get_bind()
    for key, value, is_sensitive in _SETTINGS:
        conn.execute(
            sa.text(
                "INSERT INTO settings (key, value, is_sensitive) "
                "VALUES (:key, :value, :is_sensitive) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"key": key, "value": json.dumps({"value": value}), "is_sensitive": is_sensitive},
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [k for k, _, _ in _SETTINGS]
    for key in keys:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )
```

- [ ] **Step 2: Commit**

```bash
git add backend/alembic/versions/c3d4e5f6a7b8_seed_auth_settings.py
git commit -m "feat: seed registration, email-verification, and Resend settings"
```

---

## Task 4: Ban enforcement

**Files:**
- Modify: `backend/app/deps.py`
- Modify: `backend/app/routers/auth.py` (refresh handler)
- Modify: `backend/tests/test_deps.py`

- [ ] **Step 1: Write failing test for banned user in `get_current_user`**

In `backend/tests/test_deps.py`, add these imports at the top:
```python
import uuid
from unittest.mock import MagicMock, AsyncMock
from app.services.auth.jwt_service import create_access_token
from app.models.user import User
```

Then add the test:

```python
@pytest.mark.asyncio
async def test_get_current_user_banned_raises_403():
    """Banned user gets 403 even with valid access token."""
    banned_user = MagicMock(spec=User)
    banned_user.id = uuid.uuid4()
    banned_user.is_banned = True

    token = create_access_token(str(banned_user.id))
    request = MagicMock(spec=Request)
    request.cookies = {"access_token": token}

    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)  # not blacklisted

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = banned_user
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=request, db=db, redis=redis)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "заблокирован" in exc_info.value.detail.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_deps.py -v -k "banned"
```
Expected: FAIL (is_banned check not implemented yet)

- [ ] **Step 3: Add ban check to `get_current_user` in `backend/app/deps.py`**

After `if not user:` check, add:

```python
if user.is_banned:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_deps.py -v -k "banned"
```
Expected: PASS

- [ ] **Step 5: Add ban check to the `refresh` endpoint in `backend/app/routers/auth.py`**

In the `refresh` handler, after:
```python
user = result.scalar_one_or_none()
if not user:
    raise HTTPException(status_code=401, detail="User not found")
```
Add:
```python
if user.is_banned:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/deps.py backend/app/routers/auth.py backend/tests/test_deps.py
git commit -m "feat: enforce is_banned in get_current_user and refresh endpoint"
```

---

## Task 5: Registration guards

**Files:**
- Modify: `backend/app/routers/auth.py` (`register_email` handler)
- Modify: `backend/tests/routers/test_auth_email.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/routers/test_auth_email.py`:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_register_blocked_when_registration_disabled():
    """Returns 503 when registration_enabled=false."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.routers.auth.get_setting", new=AsyncMock(return_value="false")):
            resp = await client.post("/api/auth/register", json={
                "email": "user@gmail.com",
                "password": "SecurePass123!",
                "display_name": "User"
            })
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_register_blocked_by_domain_whitelist():
    """Returns 400 when email domain not in allowed_email_domains."""
    async def mock_get_setting(db, key):
        if key == "registration_enabled":
            return "true"
        if key == "allowed_email_domains":
            return "gmail.com,mail.ru"
        return None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.routers.auth.get_setting", new=AsyncMock(side_effect=mock_get_setting)):
            resp = await client.post("/api/auth/register", json={
                "email": "user@tempmail.org",
                "password": "SecurePass123!",
                "display_name": "User"
            })
    assert resp.status_code == 400
    assert "недоступна" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_allowed_when_domain_list_empty():
    """Any domain allowed when allowed_email_domains is empty."""
    async def mock_get_setting(db, key):
        if key == "registration_enabled":
            return "true"
        if key == "allowed_email_domains":
            return ""
        return None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.routers.auth.get_setting", new=AsyncMock(side_effect=mock_get_setting)):
            with patch("app.routers.auth.create_user_with_provider", new=AsyncMock()) as mock_create:
                with patch("app.routers.auth._set_auth_cookies", new=AsyncMock()):
                    mock_user = MagicMock()
                    mock_user.id = uuid.uuid4()
                    mock_user.display_name = "User"
                    mock_create.return_value = mock_user
                    resp = await client.post("/api/auth/register", json={
                        "email": "user@anydomain.xyz",
                        "password": "SecurePass123!",
                        "display_name": "User"
                    })
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/routers/test_auth_email.py -v -k "registration_disabled or domain_whitelist or domain_list_empty"
```
Expected: FAIL

- [ ] **Step 3: Add guards to `register_email` in `backend/app/routers/auth.py`**

At the top of the `register_email` handler, before the `get_user_by_email` call, add:

```python
# Guard 1: registration enabled
registration_enabled = await get_setting(db, "registration_enabled")
if registration_enabled == "false":
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Регистрация временно закрыта")

# Guard 2: domain whitelist
allowed_domains_str = await get_setting(db, "allowed_email_domains") or ""
allowed_domains = [d.strip().lower() for d in allowed_domains_str.split(",") if d.strip()]
if allowed_domains:
    email_domain = data.email.lower().split("@")[-1]
    if email_domain not in allowed_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Регистрация с этим email-адресом недоступна")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/routers/test_auth_email.py -v -k "registration_disabled or domain_whitelist or domain_list_empty"
```
Expected: PASS

- [ ] **Step 5: Run all tests**

```bash
cd backend && uv run pytest -x -q
```
Expected: all 157+ tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/routers/test_auth_email.py
git commit -m "feat: add registration_enabled and domain whitelist guards to /register"
```

---

## Task 6: Email service (Resend)

**Files:**
- Create: `backend/app/services/email_service.py`
- Create: `backend/tests/services/test_email_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_email_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


@pytest.mark.asyncio
async def test_send_verification_email_calls_resend():
    """Calls Resend API with correct payload."""
    from app.services.email_service import send_verification_email

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await send_verification_email(
            api_key="re_test_key",
            from_address="noreply@test.com",
            from_name="Test VPN",
            to_email="user@gmail.com",
            verify_url="https://example.com/verify-email?token=abc123",
        )

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[0][0] == "https://api.resend.com/emails"
    payload = call_kwargs[1]["json"]
    assert payload["to"] == ["user@gmail.com"]
    assert "abc123" in payload["html"]


@pytest.mark.asyncio
async def test_send_verification_email_raises_on_http_error():
    """Propagates HTTPStatusError on Resend API failure."""
    from app.services.email_service import send_verification_email

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await send_verification_email(
                api_key="re_bad_key",
                from_address="noreply@test.com",
                from_name="VPN",
                to_email="user@gmail.com",
                verify_url="https://example.com/verify-email?token=xyz",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/services/test_email_service.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Create `backend/app/services/email_service.py`**

```python
from __future__ import annotations
import httpx

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT = httpx.Timeout(10.0)


async def send_verification_email(
    api_key: str,
    from_address: str,
    from_name: str,
    to_email: str,
    verify_url: str,
) -> None:
    """Send email verification link via Resend REST API."""
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2>Подтверждение email</h2>
      <p>Нажмите кнопку ниже, чтобы подтвердить ваш email-адрес.</p>
      <a href="{verify_url}"
         style="display:inline-block;padding:12px 24px;background:#06b6d4;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Подтвердить email
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Ссылка действительна 24 часа. Если вы не запрашивали подтверждение — проигнорируйте это письмо.
      </p>
    </div>
    """
    payload = {
        "from": f"{from_name} <{from_address}>",
        "to": [to_email],
        "subject": "Подтвердите ваш email",
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/services/test_email_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/services/test_email_service.py
git commit -m "feat: add email_service with Resend integration"
```

---

## Task 7: Verify-email endpoints

**Files:**
- Modify: `backend/app/routers/auth.py` (add two new routes)
- Create: `backend/tests/routers/test_verify_email.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/routers/test_verify_email.py`:

```python
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.deps import get_current_user
from app.redis_client import get_redis
from app.database import get_db
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType


def _make_user_with_email(email_verified=False):
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.is_banned = False
    provider = MagicMock(spec=AuthProvider)
    provider.provider = ProviderType.email
    provider.provider_user_id = "user@gmail.com"
    provider.email_verified = email_verified
    user.auth_providers = [provider]
    return user, provider


@pytest.mark.asyncio
async def test_send_verify_already_verified_returns_200():
    """Returns 200 no-op if email already verified."""
    user, _ = _make_user_with_email(email_verified=True)
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = user.auth_providers
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: (x for x in [db])
    app.dependency_overrides[get_redis] = lambda: (x for x in [redis])

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/auth/verify-email/send")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_verify_rate_limited_returns_429():
    """Returns 429 when rate limit exceeded."""
    user, _ = _make_user_with_email(email_verified=False)
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = user.auth_providers
    db.execute = AsyncMock(return_value=result)
    redis = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: (x for x in [db])
    app.dependency_overrides[get_redis] = lambda: (x for x in [redis])

    try:
        with patch("app.routers.auth.check_rate_limit", new=AsyncMock(return_value=False)):
            with patch("app.routers.auth.get_setting_decrypted", new=AsyncMock(return_value="re_key")):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/api/auth/verify-email/send")
        assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_confirm_invalid_token_redirects_to_error():
    """Redirects to ?error=expired when token not in Redis."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)

    app.dependency_overrides[get_redis] = lambda: (x for x in [redis])

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.get("/api/auth/verify-email/confirm?token=badtoken")
        assert resp.status_code == 302
        assert "error=expired" in resp.headers["location"]
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/routers/test_verify_email.py -v
```
Expected: FAIL (routes don't exist)

- [ ] **Step 3: Add verify-email endpoints to `backend/app/routers/auth.py`**

Add these imports at the top of `auth.py` — **all four are new to this file**:
```python
from app.services.email_service import send_verification_email
from app.services.rate_limiter import check_rate_limit   # NEW — not currently imported in auth.py
from app.models.auth_provider import AuthProvider, ProviderType  # NEW — not currently imported in auth.py
from fastapi.responses import RedirectResponse           # NEW
```

`settings.frontend_url` already exists in `app/config.py` (confirmed: `frontend_url: str = "http://localhost:5173"`), so no config changes needed.

Add the two new routes (place after the existing `oauth_config` route):

```python
@router.post("/verify-email/send")
async def send_verify_email(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    from sqlalchemy import select as _sel
    result = await db.execute(
        _sel(AuthProvider).where(
            AuthProvider.user_id == current_user.id,
            AuthProvider.provider == ProviderType.email,
        )
    )
    email_provider = result.scalar_one_or_none()

    # Already verified or no email provider
    if email_provider is None or email_provider.email_verified:
        return {"ok": True}

    # Check resend API key
    api_key = await get_setting_decrypted(db, "resend_api_key")
    if not api_key:
        raise HTTPException(status_code=503, detail="Email-сервис не настроен")

    # Rate limit: 3 sends per hour per user
    rate_key = f"verify_email_rate:{current_user.id}"
    if not await check_rate_limit(redis, rate_key, 3, 3600):
        raise HTTPException(status_code=429, detail="Слишком много попыток. Попробуйте через час.")

    # Generate token and store in Redis
    import uuid as _uuid2
    token = str(_uuid2.uuid4())
    await redis.setex(f"verify_email:{token}", 86400, str(current_user.id))

    # Send email
    from_address = await get_setting(db, "email_from_address") or "noreply@example.com"
    from_name = await get_setting(db, "email_from_name") or "VPN Service"
    frontend_url = settings.frontend_url.rstrip("/")
    verify_url = f"{frontend_url}/verify-email?token={token}"

    try:
        await send_verification_email(
            api_key=api_key,
            from_address=from_address,
            from_name=from_name,
            to_email=email_provider.provider_user_id,
            verify_url=verify_url,
        )
    except Exception as exc:
        logger.exception("Failed to send verification email: %s", exc)
        raise HTTPException(status_code=503, detail="Ошибка отправки письма")

    return {"ok": True}


@router.get("/verify-email/confirm")
async def confirm_verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    frontend_url = settings.frontend_url.rstrip("/")
    user_id_str = await redis.get(f"verify_email:{token}")
    if not user_id_str:
        return RedirectResponse(url=f"{frontend_url}/verify-email?error=expired", status_code=302)

    try:
        import uuid as _uuid3
        user_uuid = _uuid3.UUID(user_id_str if isinstance(user_id_str, str) else user_id_str.decode())
    except ValueError:
        return RedirectResponse(url=f"{frontend_url}/verify-email?error=expired", status_code=302)

    from sqlalchemy import select as _sel2
    result = await db.execute(
        _sel2(AuthProvider).where(
            AuthProvider.user_id == user_uuid,
            AuthProvider.provider == ProviderType.email,
        )
    )
    email_provider = result.scalar_one_or_none()
    if email_provider:
        email_provider.email_verified = True
        await db.commit()

    await redis.delete(f"verify_email:{token}")
    return RedirectResponse(url=f"{frontend_url}/verify-email?verified=1", status_code=302)
```

Note: check that `settings.frontend_url` exists in `app/config.py`. If not, use `await get_setting(db, "frontend_url")` or add `FRONTEND_URL` to the config.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/routers/test_verify_email.py -v
```
Expected: PASS

- [ ] **Step 5: Run all tests**

```bash
cd backend && uv run pytest -x -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/routers/test_verify_email.py
git commit -m "feat: add verify-email send and confirm endpoints"
```

---

## Task 8: Trial activation guard + squad fallback

**Files:**
- Modify: `backend/app/routers/subscriptions.py`
- Modify: `backend/tests/routers/test_subscriptions.py`

- [ ] **Step 1: Write failing test for email guard**

Add to `backend/tests/routers/test_subscriptions.py`:

```python
@pytest.mark.asyncio
async def test_trial_blocked_when_email_not_verified():
    """Returns 403 when email_verification_enabled=true and email not verified."""
    from app.models.auth_provider import AuthProvider, ProviderType

    user = _make_user()
    user.is_banned = False

    email_provider = MagicMock(spec=AuthProvider)
    email_provider.provider = ProviderType.email
    email_provider.email_verified = False

    db = AsyncMock(spec=AsyncSession)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # not rate limited

    async def mock_check_rate(r, key, limit, window):
        return True

    async def mock_get_setting(d, key):
        if key == "email_verification_enabled":
            return "true"
        if key == "remnawave_url":
            return "http://remnawave"
        if key == "remnawave_token":
            return "token"
        return None

    async def mock_get_setting_decrypted(d, key):
        return "token"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = email_provider
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: (x for x in [db])
    app.dependency_overrides[get_redis] = lambda: (x for x in [redis])

    try:
        with patch("app.routers.subscriptions.get_setting", new=AsyncMock(side_effect=mock_get_setting)):
            with patch("app.routers.subscriptions.get_setting_decrypted", new=AsyncMock(side_effect=mock_get_setting_decrypted)):
                with patch("app.routers.subscriptions.check_rate_limit", new=AsyncMock(return_value=True)):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        resp = await client.post("/api/subscriptions/trial")
        assert resp.status_code == 403
        assert "Подтвердите email" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/routers/test_subscriptions.py -v -k "email_not_verified"
```
Expected: FAIL

- [ ] **Step 3: Update `activate_trial` in `backend/app/routers/subscriptions.py`**

Add the email verification guard after the existing guard 3 (Remnawave not configured). Also update the squad lookup:

Add import at top of file:
```python
from app.models.auth_provider import AuthProvider, ProviderType
```

After the Remnawave URL/token check, add:
```python
# Guard 4: email verification
email_verification_enabled = await get_setting(db, "email_verification_enabled")
if email_verification_enabled == "true":
    from sqlalchemy import select as _sel
    ev_result = await db.execute(
        _sel(AuthProvider).where(
            AuthProvider.user_id == current_user.id,
            AuthProvider.provider == ProviderType.email,
        )
    )
    email_provider = ev_result.scalar_one_or_none()
    if email_provider is not None and not email_provider.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подтвердите email для активации пробного периода",
        )
```

Replace the squad lookup (line ~93):
```python
squad_uuids_str = (
    await get_setting(db, "remnawave_trial_squad_uuids")
    or await get_setting(db, "remnawave_squad_uuids")
    or ""
)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/routers/test_subscriptions.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/subscriptions.py backend/tests/routers/test_subscriptions.py
git commit -m "feat: add email verification guard and trial squad fallback to trial activation"
```

---

## Task 9: OAuthConfigResponse + UserProfileResponse extensions

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/routers/auth.py` (`get_oauth_config` handler)
- Modify: `backend/app/routers/users.py` (`get_me` handler, `link_email` handler)
- Modify: `backend/tests/routers/test_auth_oauth_config.py`

- [ ] **Step 1: Add `email_verification_required` to `OAuthConfigResponse`**

In `backend/app/schemas/auth.py`, add field to `OAuthConfigResponse`:
```python
email_verification_required: bool = False
```

In `backend/app/routers/auth.py`, update `get_oauth_config` handler to include:
```python
email_verification_required = await get_setting(db, "email_verification_enabled") == "true"
```
And include in the returned `OAuthConfigResponse(...)`.

- [ ] **Step 2: Add `email_verified` to `UserProfileResponse`**

In `backend/app/schemas/user.py`, add field to `UserProfileResponse`:
```python
email_verified: bool | None = None
```

In `backend/app/routers/users.py`, update `get_me` to derive `email_verified`:
```python
email_provider = next((p for p in providers if p.provider == ProviderType.email), None)
email_verified = email_provider.email_verified if email_provider else None
```
Include `email_verified=email_verified` in returned `UserProfileResponse(...)`.

- [ ] **Step 3: Update `link_email` to explicitly set `email_verified=False`**

In `backend/app/routers/users.py`, in `link_email`, update the `AuthProvider(...)` construction:
```python
db.add(AuthProvider(
    user_id=current_user.id,
    provider=ProviderType.email,
    provider_user_id=data.email.lower(),
    password_hash=hash_password(data.password),
    email_verified=False,  # explicit, default is already False
))
```

- [ ] **Step 4: Add test for new OAuthConfigResponse field**

In `backend/tests/routers/test_auth_oauth_config.py`, add:
```python
@pytest.mark.asyncio
async def test_oauth_config_has_email_verification_required():
    """Response includes email_verification_required field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/auth/oauth-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "email_verification_required" in data
    assert isinstance(data["email_verification_required"], bool)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/routers/test_auth_oauth_config.py tests/routers/test_users.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/schemas/user.py backend/app/routers/auth.py backend/app/routers/users.py backend/tests/routers/test_auth_oauth_config.py
git commit -m "feat: add email_verification_required to OAuthConfigResponse, email_verified to UserProfileResponse"
```

---

## Task 10: Admin schema extensions

**Files:**
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/routers/admin.py` (`_build_list_item`, `get_user_detail`)

- [ ] **Step 1: Update schemas in `backend/app/schemas/admin.py`**

`ProviderInfo` already has `provider_user_id` (confirmed: it's at line 10 of the existing file). Only add `email_verified`:
```python
class ProviderInfo(BaseModel):
    provider: str
    provider_user_id: str
    provider_username: str | None
    email_verified: bool | None = None   # add this
    created_at: datetime
    model_config = {"from_attributes": True}
```

`UserAdminListItem` — add three fields:
```python
is_banned: bool = False
email: str | None = None
email_verified: bool | None = None
```

`UserAdminDetail` — add three fields:
```python
is_banned: bool = False
email: str | None = None
email_verified: bool | None = None
```

- [ ] **Step 2: Update `_build_list_item` in `backend/app/routers/admin.py`**

```python
def _build_list_item(u: User) -> UserAdminListItem:
    sub = u.subscription
    email_provider = next((p for p in u.auth_providers if p.provider.value == "email"), None)
    return UserAdminListItem(
        id=u.id,
        display_name=u.display_name,
        avatar_url=u.avatar_url,
        is_admin=u.is_admin,
        is_banned=u.is_banned,
        remnawave_uuid=u.remnawave_uuid,
        has_made_payment=u.has_made_payment,
        subscription_conflict=u.subscription_conflict,
        created_at=u.created_at,
        last_seen_at=u.last_seen_at,
        subscription_status=sub.status.value if sub else None,
        subscription_type=sub.type.value if sub else None,
        subscription_expires_at=sub.expires_at if sub else None,
        providers=[p.provider.value for p in u.auth_providers],
        email=email_provider.provider_user_id if email_provider else None,
        email_verified=email_provider.email_verified if email_provider else None,
    )
```

- [ ] **Step 3: Update `get_user_detail` in `backend/app/routers/admin.py`**

In the `UserAdminDetail(...)` construction, add:
```python
is_banned=user.is_banned,
email=next((p.provider_user_id for p in user.auth_providers if p.provider.value == "email"), None),
email_verified=next((p.email_verified for p in user.auth_providers if p.provider.value == "email"), None),
```

For `ProviderInfo`, update the list comprehension to also pass `email_verified`:
```python
providers=[
    ProviderInfo(
        provider=p.provider.value,
        provider_user_id=p.provider_user_id,
        provider_username=p.provider_username,
        email_verified=p.email_verified if p.provider.value == "email" else None,
        created_at=p.created_at,
    )
    for p in user.auth_providers
],
```

- [ ] **Step 4: Run all tests**

```bash
cd backend && uv run pytest -x -q
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/routers/admin.py
git commit -m "feat: add is_banned, email, email_verified to admin user schemas and handlers"
```

---

## Task 11: Admin ban/admin/reset-subscription endpoints

**Files:**
- Modify: `backend/app/routers/admin.py`
- Create: `backend/tests/routers/test_admin_user_actions.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/routers/test_admin_user_actions.py`:

```python
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus


def _make_admin():
    admin = MagicMock(spec=User)
    admin.id = uuid.uuid4()
    admin.is_admin = True
    admin.is_banned = False
    return admin


def _make_target_user(is_banned=False, is_admin=False):
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.is_banned = is_banned
    user.is_admin = is_admin
    user.display_name = "Test User"
    user.avatar_url = None
    user.remnawave_uuid = None
    user.has_made_payment = False
    user.subscription_conflict = False
    from datetime import datetime, timezone
    user.created_at = datetime.now(tz=timezone.utc)
    user.last_seen_at = datetime.now(tz=timezone.utc)
    user.subscription = None
    user.auth_providers = []
    return user


@pytest.mark.asyncio
async def test_ban_user_toggles_is_banned():
    """PATCH /ban toggles is_banned on target user."""
    admin = _make_admin()
    target = _make_target_user(is_banned=False)
    db = AsyncMock(spec=AsyncSession)

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = target
    db.execute = AsyncMock(return_value=user_result)
    db.commit = AsyncMock()

    # _build_user_detail makes multiple DB queries internally — patch it directly
    expected_detail = _make_target_user(is_banned=True)
    expected_detail.is_admin = False
    expected_detail.email = None
    expected_detail.email_verified = None
    expected_detail.subscription = None
    expected_detail.providers = []
    expected_detail.recent_transactions = []

    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = lambda: (x for x in [db])

    try:
        with patch("app.routers.admin._build_user_detail", new=AsyncMock(return_value=expected_detail)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(f"/api/admin/users/{target.id}/ban")
        assert resp.status_code == 200
        assert target.is_banned is True  # toggled by endpoint
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ban_self_returns_403():
    """Cannot ban yourself."""
    admin = _make_admin()
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = lambda: (x for x in [AsyncMock()])

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(f"/api/admin/users/{admin.id}/ban")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reset_subscription_marks_expired():
    """POST /reset-subscription sets status=expired and expires_at=now."""
    from datetime import datetime, timezone
    admin = _make_admin()
    target = _make_target_user()
    sub = MagicMock(spec=Subscription)
    sub.status = SubscriptionStatus.active

    db = AsyncMock(spec=AsyncSession)
    target_result = MagicMock()
    target_result.scalar_one_or_none.return_value = target
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = sub

    call_count = [0]
    async def mock_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return target_result
        return sub_result

    db.execute = AsyncMock(side_effect=mock_execute)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_db] = lambda: (x for x in [db])

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/admin/users/{target.id}/reset-subscription")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert sub.status == SubscriptionStatus.expired
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/routers/test_admin_user_actions.py -v
```
Expected: FAIL (routes don't exist)

- [ ] **Step 3: Add new endpoints to `backend/app/routers/admin.py`**

Add a helper to build `UserAdminDetail` for a user (to avoid code duplication):

```python
async def _build_user_detail(user_id: uuid.UUID, db: AsyncSession) -> UserAdminDetail:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.auth_providers), selectinload(User.subscription))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    tx_result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(10)
    )
    transactions = tx_result.scalars().all()
    email_provider = next((p for p in user.auth_providers if p.provider.value == "email"), None)
    return UserAdminDetail(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
        remnawave_uuid=user.remnawave_uuid,
        has_made_payment=user.has_made_payment,
        subscription_conflict=user.subscription_conflict,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        email=email_provider.provider_user_id if email_provider else None,
        email_verified=email_provider.email_verified if email_provider else None,
        subscription=SubscriptionAdminInfo.model_validate(user.subscription) if user.subscription else None,
        providers=[
            ProviderInfo(
                provider=p.provider.value,
                provider_user_id=p.provider_user_id,
                provider_username=p.provider_username,
                email_verified=p.email_verified if p.provider.value == "email" else None,
                created_at=p.created_at,
            )
            for p in user.auth_providers
        ],
        recent_transactions=[TransactionAdminItem.model_validate(tx) for tx in transactions],
    )
```

Refactor existing `get_user_detail` to use `_build_user_detail`.

Add three new endpoints:

```python
@router.patch("/users/{user_id}/ban", response_model=UserAdminDetail)
async def ban_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminDetail:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя заблокировать себя")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    user.is_banned = not user.is_banned
    await db.commit()
    return await _build_user_detail(user_id, db)


@router.patch("/users/{user_id}/admin", response_model=UserAdminDetail)
async def toggle_admin(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminDetail:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя изменить собственные права администратора")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    user.is_admin = not user.is_admin
    await db.commit()
    return await _build_user_detail(user_id, db)


@router.post("/users/{user_id}/reset-subscription")
async def reset_subscription(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import datetime, timezone
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подписка не найдена")
    from app.models.subscription import SubscriptionStatus
    sub.status = SubscriptionStatus.expired
    sub.expires_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/routers/test_admin_user_actions.py -v
```
Expected: PASS

- [ ] **Step 5: Run all tests**

```bash
cd backend && uv run pytest -x -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/admin.py backend/tests/routers/test_admin_user_actions.py
git commit -m "feat: add ban, toggle-admin, reset-subscription admin endpoints"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd backend && uv run pytest -q
```
Expected: all tests pass, no failures

- [ ] **Step 2: Verify migration chain**

```bash
cd backend && uv run alembic history
```
Expected: chain shows `b3c4d5e6f7a8` → `a1b2c3d4e5f6` → `b2c3d4e5f6a7` → `c3d4e5f6a7b8`

- [ ] **Step 3: Final commit**

```bash
git add backend/app/models/auth_provider.py \
        backend/app/models/user.py \
        backend/app/deps.py \
        backend/app/routers/auth.py \
        backend/app/routers/users.py \
        backend/app/routers/subscriptions.py \
        backend/app/routers/admin.py \
        backend/app/schemas/auth.py \
        backend/app/schemas/user.py \
        backend/app/schemas/admin.py \
        backend/app/services/email_service.py \
        backend/alembic/versions/
git commit -m "feat: Plan 11 complete — email verification, ban, admin actions backend"
```
