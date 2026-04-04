# Plan 11: OAuth Providers, Install Config, Promo UX, Plan Create Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VK/Telegram OAuth login buttons, link-provider flow in profile, configurable install page, single promo code field, and plan creation in admin.

**Architecture:** Backend adds 5 new endpoint groups (oauth-config, link-provider, create-plan, install-app-config, settings seed). Frontend consumes these endpoints to conditionally render VK/Telegram buttons on login, add-provider UI in profile, always-visible download buttons on install page, merged promo code field, and create-plan form in admin. OAuth meta-config (which providers are enabled) comes from a single public endpoint so frontend has a single source of truth. Install app config is stored in DB settings (seeded with defaults), editable via existing AdminSettingsPage.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic (migrations), pytest-asyncio, React 18, TanStack Query v5, Tailwind CSS, TypeScript

---

## File Map

**Backend — create:**
- `backend/alembic/versions/b3c4d5e6f7a8_seed_new_settings.py` — seeds telegram_bot_username, site_name, support_telegram_link, install_*_app_name, install_*_store_url
- `backend/tests/routers/test_auth_oauth_config.py` — tests for GET /api/auth/oauth-config
- `backend/tests/routers/test_admin_plans_create.py` — tests for POST /api/admin/plans
- `backend/tests/routers/test_install_app_config.py` — tests for GET /api/install/app-config
- `backend/tests/routers/test_users_link_provider.py` — tests for POST /api/users/me/providers/*
- `frontend/src/pages/VKCallbackPage.tsx` — VK OAuth callback (login + link intent)

**Backend — modify:**
- `backend/app/schemas/auth.py` — add OAuthConfigResponse, LinkEmailRequest
- `backend/app/schemas/admin.py` — add PlanCreateRequest
- `backend/app/routers/auth.py` — add GET /api/auth/oauth-config
- `backend/app/routers/admin.py` — add POST /api/admin/plans
- `backend/app/routers/install.py` — add GET /api/install/app-config
- `backend/app/routers/users.py` — add POST /api/users/me/providers/{google,vk,telegram,email}

**Frontend — modify:**
- `frontend/src/types/api.ts` — add OAuthConfigResponse, OsAppConfig, InstallAppConfig, PlanAdminCreateRequest
- `frontend/src/App.tsx` — add /auth/vk/callback route
- `frontend/src/pages/GoogleCallbackPage.tsx` — handle oauth_intent=link
- `frontend/src/pages/LoginPage.tsx` — VK + Telegram buttons from oauth-config
- `frontend/src/pages/ProfilePage.tsx` — "Add auth method" section
- `frontend/src/pages/SubscriptionPage.tsx` — merge promo code into single field
- `frontend/src/pages/InstallPage.tsx` — remove clash_verge, always show download, fetch app-config
- `frontend/src/pages/admin/AdminPlansPage.tsx` — create plan form

---

## Task 1: Alembic migration — seed new settings

**Files:**
- Create: `backend/alembic/versions/b3c4d5e6f7a8_seed_new_settings.py`

- [ ] **Step 1: Write the migration**

```python
"""seed_new_settings

Revision ID: b3c4d5e6f7a8
Revises: 1e776950ed0d
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = '1e776950ed0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [
    # OAuth / identity
    ("telegram_bot_username", "", False),
    ("site_name", "Skavellion VPN", False),
    ("support_telegram_link", "", False),
    # Install page — Android
    ("install_android_app_name", "FlClash", False),
    ("install_android_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
    # Install page — iOS
    ("install_ios_app_name", "Clash Mi", False),
    ("install_ios_store_url", "https://apps.apple.com/app/clash-mi/id1574653991", False),
    # Install page — Windows
    ("install_windows_app_name", "FlClash", False),
    ("install_windows_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
    # Install page — macOS
    ("install_macos_app_name", "FlClash", False),
    ("install_macos_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
    # Install page — Linux
    ("install_linux_app_name", "FlClash", False),
    ("install_linux_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
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
            {"key": key, "value": value, "is_sensitive": is_sensitive},
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [k for k, _, _ in _SETTINGS]
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = ANY(:keys)"),
        {"keys": keys},
    )
```

- [ ] **Step 2: Run migration**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `Running upgrade 1e776950ed0d -> b3c4d5e6f7a8, seed_new_settings`

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/b3c4d5e6f7a8_seed_new_settings.py
git commit -m "feat: seed new settings for OAuth config and install page"
```

---

## Task 2: Backend — GET /api/auth/oauth-config

Returns which OAuth providers are enabled so the frontend can conditionally render buttons.
Google/VK enabled = env vars `GOOGLE_CLIENT_ID`/`VK_CLIENT_ID` are non-empty. Telegram enabled = `telegram_bot_token` DB setting exists and non-empty.

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/routers/auth.py`
- Create: `backend/tests/routers/test_auth_oauth_config.py`

- [ ] **Step 1: Add response schema to `backend/app/schemas/auth.py`**

Add at the bottom of the file:
```python
class OAuthConfigResponse(BaseModel):
    google: bool
    vk: bool
    telegram: bool
    telegram_bot_username: str | None
```

- [ ] **Step 2: Write failing tests in `backend/tests/routers/test_auth_oauth_config.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.mark.asyncio
async def test_oauth_config_all_disabled():
    """When no env vars and no DB settings, all providers disabled."""
    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
    ):
        mock_settings.google_client_id = ""
        mock_settings.vk_client_id = ""
        mock_get.return_value = None  # no telegram token, no bot_username

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["google"] is False
    assert data["vk"] is False
    assert data["telegram"] is False
    assert data["telegram_bot_username"] is None


@pytest.mark.asyncio
async def test_oauth_config_google_enabled():
    """When GOOGLE_CLIENT_ID is set, google=true."""
    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", new_callable=AsyncMock) as mock_get,
    ):
        mock_settings.google_client_id = "some-client-id"
        mock_settings.vk_client_id = ""
        mock_get.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    assert resp.json()["google"] is True


@pytest.mark.asyncio
async def test_oauth_config_telegram_enabled_with_username():
    """When telegram_bot_token is in DB and bot_username set, telegram=true with username."""
    call_count = 0

    async def mock_get(db, key):
        nonlocal call_count
        call_count += 1
        if key == "telegram_bot_token":
            return "some-token"
        if key == "telegram_bot_username":
            return "mybot"
        return None

    with (
        patch("app.routers.auth.settings") as mock_settings,
        patch("app.routers.auth.get_setting", side_effect=mock_get),
    ):
        mock_settings.google_client_id = ""
        mock_settings.vk_client_id = ""

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/oauth-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram"] is True
    assert data["telegram_bot_username"] == "mybot"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/routers/test_auth_oauth_config.py -v
```

Expected: FAIL — `404 Not Found` (endpoint doesn't exist yet)

- [ ] **Step 4: Implement the endpoint in `backend/app/routers/auth.py`**

Add after the imports, add `OAuthConfigResponse` to the schema import:
```python
from app.schemas.auth import EmailRegisterRequest, EmailLoginRequest, TokenResponse, TelegramOAuthRequest, GoogleOAuthRequest, VKOAuthRequest, OAuthConfigResponse
```

Add the endpoint before the `register_email` route:
```python
@router.get("/oauth-config", response_model=OAuthConfigResponse)
async def get_oauth_config(
    db: AsyncSession = Depends(get_db),
) -> OAuthConfigResponse:
    """Public endpoint — returns which OAuth providers are configured."""
    google_enabled = bool(settings.google_client_id)
    vk_enabled = bool(settings.vk_client_id)
    telegram_token = await get_setting(db, "telegram_bot_token")
    telegram_enabled = bool(telegram_token)
    bot_username: str | None = None
    if telegram_enabled:
        bot_username = await get_setting(db, "telegram_bot_username") or None
    return OAuthConfigResponse(
        google=google_enabled,
        vk=vk_enabled,
        telegram=telegram_enabled,
        telegram_bot_username=bot_username,
    )
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && uv run pytest tests/routers/test_auth_oauth_config.py -v
```

Expected: All 3 PASS

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
cd backend && uv run pytest --tb=short -q
```

Expected: All passing (was 157 before this task)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/routers/auth.py backend/tests/routers/test_auth_oauth_config.py
git commit -m "feat: add GET /api/auth/oauth-config public endpoint"
```

---

## Task 3: Backend — POST /api/admin/plans (create plan)

**Files:**
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/routers/admin.py`
- Create: `backend/tests/routers/test_admin_plans_create.py`

- [ ] **Step 1: Write failing tests in `backend/tests/routers/test_admin_plans_create.py`**

```python
import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.deps import require_admin
from app.models.user import User

NOW = datetime.now(tz=timezone.utc)


def _make_admin():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Admin"
    u.is_admin = True
    return u


@pytest.mark.asyncio
async def test_create_plan_success():
    """POST /api/admin/plans creates a plan and returns 201."""
    admin = _make_admin()
    created_plan_id = uuid.uuid4()

    async def override_require_admin():
        return admin

    async def override_get_db():
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', created_plan_id) or setattr(obj, 'is_active', True) or setattr(obj, 'sort_order', 0) or setattr(obj, 'new_user_price_rub', None))
        yield db

    from app.database import get_db
    app.dependency_overrides[require_admin] = override_require_admin
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/admin/plans", json={
                "name": "custom_plan",
                "label": "Кастомный тариф",
                "duration_days": 60,
                "price_rub": 450,
            })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_plan_requires_admin():
    """POST /api/admin/plans returns 403 without admin."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/admin/plans", json={
            "name": "x", "label": "X", "duration_days": 30, "price_rub": 100
        })
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/routers/test_admin_plans_create.py -v
```

Expected: FAIL — 404 or 405 (endpoint doesn't exist)

- [ ] **Step 3: Add `PlanCreateRequest` to `backend/app/schemas/admin.py`**

After the `PlanUpdateRequest` class (line ~99):
```python
class PlanCreateRequest(BaseModel):
    name: str                          # unique system key e.g. "2_months"
    label: str                         # display name e.g. "2 месяца"
    duration_days: int
    price_rub: int
    new_user_price_rub: int | None = None
    is_active: bool = True
    sort_order: int = 0
```

- [ ] **Step 4: Import `PlanCreateRequest` in `backend/app/routers/admin.py`**

Update the import from `app.schemas.admin`:
```python
from app.schemas.admin import (
    ...
    PlanAdminItem,
    PlanCreateRequest,
    PlanUpdateRequest,
    ...
)
```

- [ ] **Step 5: Add `POST /api/admin/plans` endpoint in `backend/app/routers/admin.py`**

Add after `admin_update_plan` (after the `@router.patch("/plans/{plan_id}")` function):

```python
@router.post("/plans", response_model=PlanAdminItem, status_code=201)
async def admin_create_plan(
    data: PlanCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PlanAdminItem:
    plan = Plan(
        name=data.name,
        label=data.label,
        duration_days=data.duration_days,
        price_rub=data.price_rub,
        new_user_price_rub=data.new_user_price_rub,
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(plan)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Тариф с таким именем уже существует")
    await db.refresh(plan)
    return PlanAdminItem.model_validate(plan)
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd backend && uv run pytest tests/routers/test_admin_plans_create.py -v
```

Expected: Both PASS

- [ ] **Step 7: Run full suite**

```bash
cd backend && uv run pytest --tb=short -q
```

Expected: All passing

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/routers/admin.py backend/tests/routers/test_admin_plans_create.py
git commit -m "feat: add POST /api/admin/plans create plan endpoint"
```

---

## Task 4: Backend — GET /api/install/app-config

Public endpoint. Reads per-OS settings from DB, returns them with fallback to hardcoded defaults.

**Files:**
- Modify: `backend/app/routers/install.py`
- Create: `backend/tests/routers/test_install_app_config.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/routers/test_install_app_config.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.mark.asyncio
async def test_install_app_config_returns_defaults():
    """When no DB settings, returns hardcoded defaults."""
    with patch("app.routers.install.get_setting", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None  # all settings missing → use defaults

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/install/app-config")

    assert resp.status_code == 200
    data = resp.json()
    assert "android" in data
    assert "ios" in data
    assert "windows" in data
    assert "macos" in data
    assert "linux" in data
    assert data["android"]["app_name"] == "FlClash"
    assert data["ios"]["app_name"] == "Clash Mi"


@pytest.mark.asyncio
async def test_install_app_config_overrides_from_db():
    """When DB settings exist, they override defaults."""
    async def mock_get(db, key):
        overrides = {
            "install_ios_app_name": "Streisand",
            "install_ios_store_url": "https://apps.apple.com/app/streisand/id6450534064",
        }
        return overrides.get(key)

    with patch("app.routers.install.get_setting", side_effect=mock_get):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/install/app-config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ios"]["app_name"] == "Streisand"
    assert data["ios"]["store_url"] == "https://apps.apple.com/app/streisand/id6450534064"
    # other OSes still use defaults
    assert data["android"]["app_name"] == "FlClash"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/routers/test_install_app_config.py -v
```

Expected: FAIL — 404

- [ ] **Step 3: Add response schemas to `backend/app/schemas/install.py`** (must be done BEFORE editing the router)

Read the file first, then append:
```python
class OsAppConfigResponse(BaseModel):
    app_name: str
    store_url: str


class InstallAppConfigResponse(BaseModel):
    android: OsAppConfigResponse
    ios: OsAppConfigResponse
    windows: OsAppConfigResponse
    macos: OsAppConfigResponse
    linux: OsAppConfigResponse
```

- [ ] **Step 4: Implement in `backend/app/routers/install.py`**

Update the import from `app.schemas.install`:
```python
from app.schemas.install import SubscriptionLinkResponse, OsAppConfigResponse, InstallAppConfigResponse
```

Add after `_SUB_URL_TTL`:
```python
_INSTALL_DEFAULTS: dict[str, dict[str, str]] = {
    "android": {
        "app_name": "FlClash",
        "store_url": "https://github.com/chen08209/FlClash/releases/latest",
    },
    "ios": {
        "app_name": "Clash Mi",
        "store_url": "https://apps.apple.com/app/clash-mi/id1574653991",
    },
    "windows": {
        "app_name": "FlClash",
        "store_url": "https://github.com/chen08209/FlClash/releases/latest",
    },
    "macos": {
        "app_name": "FlClash",
        "store_url": "https://github.com/chen08209/FlClash/releases/latest",
    },
    "linux": {
        "app_name": "FlClash",
        "store_url": "https://github.com/chen08209/FlClash/releases/latest",
    },
}


@router.get("/app-config", response_model=InstallAppConfigResponse)
async def get_app_config(
    db: AsyncSession = Depends(get_db),
) -> InstallAppConfigResponse:
    """Public endpoint — per-OS install app config with DB overrides."""
    result: dict[str, dict[str, str]] = {}
    for os_key, defaults in _INSTALL_DEFAULTS.items():
        app_name = await get_setting(db, f"install_{os_key}_app_name") or defaults["app_name"]
        store_url = await get_setting(db, f"install_{os_key}_store_url") or defaults["store_url"]
        result[os_key] = {"app_name": app_name, "store_url": store_url}
    return InstallAppConfigResponse(**result)
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && uv run pytest tests/routers/test_install_app_config.py -v
```

Expected: Both PASS

- [ ] **Step 6: Run full suite**

```bash
cd backend && uv run pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/install.py backend/app/schemas/install.py backend/tests/routers/test_install_app_config.py
git commit -m "feat: add GET /api/install/app-config public endpoint with DB overrides"
```

---

## Task 5: Backend — Link provider endpoints

Adds `POST /api/users/me/providers/{google|vk|telegram|email}` — all require auth (existing cookie).
These endpoints add a new auth provider to the currently authenticated user.

**Files:**
- Modify: `backend/app/routers/users.py`
- Modify: `backend/app/schemas/auth.py`
- Create: `backend/tests/routers/test_users_link_provider.py`

- [ ] **Step 1: Add request schemas to `backend/app/schemas/auth.py`**

```python
class LinkEmailRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
```

The existing `GoogleOAuthRequest`, `VKOAuthRequest`, `TelegramOAuthRequest` schemas are reused for link requests.

- [ ] **Step 2: Write failing tests in `backend/tests/routers/test_users_link_provider.py`**

```python
import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import select

from app.main import app
from app.deps import get_current_user
from app.models.user import User
from app.models.auth_provider import AuthProvider, ProviderType

NOW = datetime.now(tz=timezone.utc)


def _make_user(providers: list[str] = None):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Ivan"
    u.is_admin = False
    u.created_at = NOW
    return u


@pytest.mark.asyncio
async def test_link_google_success():
    """POST /api/users/me/providers/google links Google to existing user."""
    user = _make_user()

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        # No existing provider for this user+google
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        yield db

    from app.database import get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    g_user = MagicMock()
    g_user.id = "google-123"
    g_user.name = "Ivan"
    g_user.picture = None

    try:
        with patch("app.routers.users.exchange_google_code", new_callable=AsyncMock, return_value=g_user):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/users/me/providers/google", json={
                    "code": "auth-code",
                    "redirect_uri": "http://localhost/auth/google/callback",
                })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_link_google_already_linked():
    """Returns 409 if Google is already linked to this user."""
    user = _make_user()

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        existing = MagicMock(spec=AuthProvider)
        existing.user_id = user.id  # same user
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result_mock)
        yield db

    from app.database import get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    g_user = MagicMock()
    g_user.id = "google-123"

    try:
        with patch("app.routers.users.exchange_google_code", new_callable=AsyncMock, return_value=g_user):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/users/me/providers/google", json={
                    "code": "auth-code",
                    "redirect_uri": "http://localhost/auth/google/callback",
                })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_link_google_taken_by_other_user():
    """Returns 409 if Google account belongs to a different user."""
    user = _make_user()
    other_user_id = uuid.uuid4()

    async def override_get_current_user():
        return user

    async def override_get_db():
        db = AsyncMock()
        existing = MagicMock(spec=AuthProvider)
        existing.user_id = other_user_id  # different user!
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result_mock)
        yield db

    from app.database import get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    g_user = MagicMock()
    g_user.id = "google-123"

    try:
        with patch("app.routers.users.exchange_google_code", new_callable=AsyncMock, return_value=g_user):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/users/me/providers/google", json={
                    "code": "auth-code",
                    "redirect_uri": "http://localhost/auth/google/callback",
                })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_link_email_requires_auth():
    """Without cookie, returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/users/me/providers/email", json={
            "email": "new@example.com",
            "password": "Password123!"
        })
    assert resp.status_code == 401
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && uv run pytest tests/routers/test_users_link_provider.py -v
```

Expected: FAIL — 404/405

- [ ] **Step 4: Implement link endpoints in `backend/app/routers/users.py`**

Add imports at the top:
```python
from app.schemas.auth import GoogleOAuthRequest, VKOAuthRequest, TelegramOAuthRequest, LinkEmailRequest
from app.services.auth.oauth.google import exchange_google_code
from app.services.auth.oauth.vk import exchange_vk_code
from app.services.auth.oauth.telegram import verify_telegram_data, parse_telegram_user
from app.services.auth.password_service import hash_password
from app.services.setting_service import get_setting
```

Add after the `delete_provider` endpoint:
```python
async def _check_provider_not_taken(
    db: AsyncSession,
    provider: ProviderType,
    provider_user_id: str,
    current_user_id,
) -> None:
    """Raise 409 if provider is already linked (to this user or another)."""
    result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.provider == provider,
            AuthProvider.provider_user_id == provider_user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот аккаунт уже привязан",
        )


@router.post("/me/providers/google", status_code=200)
async def link_google(
    data: GoogleOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        g_user = await exchange_google_code(data.code, data.redirect_uri)
    except Exception:
        raise HTTPException(status_code=400, detail="Google OAuth failed")
    await _check_provider_not_taken(db, ProviderType.google, g_user.id, current_user.id)
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.google,
        provider_user_id=g_user.id,
        avatar_url=g_user.picture,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/me/providers/vk", status_code=200)
async def link_vk(
    data: VKOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        vk_user = await exchange_vk_code(data.code, data.redirect_uri, data.device_id, data.state)
    except Exception:
        raise HTTPException(status_code=400, detail="VK OAuth failed")
    await _check_provider_not_taken(db, ProviderType.vk, vk_user.id, current_user.id)
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.vk,
        provider_user_id=vk_user.id,
        provider_username=None,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/me/providers/telegram", status_code=200)
async def link_telegram(
    data: TelegramOAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bot_token = await get_setting(db, "telegram_bot_token")
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram OAuth not configured")
    try:
        raw = data.model_dump(exclude_none=True)
        verify_telegram_data(raw, bot_token=bot_token)
        tg_user = parse_telegram_user(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _check_provider_not_taken(db, ProviderType.telegram, str(tg_user.id), current_user.id)
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.telegram,
        provider_user_id=str(tg_user.id),
        provider_username=tg_user.username,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/me/providers/email", status_code=200)
async def link_email(
    data: LinkEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Check email not already registered to any user
    result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.provider == ProviderType.email,
            AuthProvider.provider_user_id == data.email.lower(),
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email уже используется")
    from app.services.auth.password_service import hash_password
    db.add(AuthProvider(
        user_id=current_user.id,
        provider=ProviderType.email,
        provider_user_id=data.email.lower(),
        password_hash=hash_password(data.password),
    ))
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && uv run pytest tests/routers/test_users_link_provider.py -v
```

Expected: All 4 PASS

- [ ] **Step 6: Run full suite**

```bash
cd backend && uv run pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/users.py backend/app/schemas/auth.py backend/tests/routers/test_users_link_provider.py
git commit -m "feat: add link-provider endpoints POST /api/users/me/providers/{google,vk,telegram,email}"
```

---

## Task 6: Frontend — New types in api.ts

No tests needed (TypeScript types).

**Files:**
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add types at the bottom of `frontend/src/types/api.ts`**

```typescript
// ─── Plan 11 types ───────────────────────────────────────────────────────────

export interface OAuthConfigResponse {
  google: boolean
  vk: boolean
  telegram: boolean
  telegram_bot_username: string | null
}

export interface OsAppConfig {
  app_name: string
  store_url: string
}

export interface InstallAppConfig {
  android: OsAppConfig
  ios: OsAppConfig
  windows: OsAppConfig
  macos: OsAppConfig
  linux: OsAppConfig
}

export interface PlanAdminCreateRequest {
  name: string
  label: string
  duration_days: number
  price_rub: number
  new_user_price_rub?: number | null
  is_active?: boolean
  sort_order?: number
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat: add OAuthConfigResponse, InstallAppConfig, PlanAdminCreateRequest types"
```

---

## Task 7: Frontend — VKCallbackPage + update GoogleCallbackPage

The `oauth_intent` value is stored in `localStorage` before initiating OAuth. Both callback pages check it: `'link'` → call link endpoint + navigate to `/profile`; otherwise → login flow as before.

**Files:**
- Create: `frontend/src/pages/VKCallbackPage.tsx`
- Modify: `frontend/src/pages/GoogleCallbackPage.tsx`

- [ ] **Step 1: Create `frontend/src/pages/VKCallbackPage.tsx`**

```tsx
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '@/lib/api'

export default function VKCallbackPage() {
  const navigate = useNavigate()
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const error = params.get('error')

    if (error || !code) {
      navigate('/login', { replace: true })
      return
    }

    const redirectUri = `${window.location.origin}/auth/vk/callback`
    const deviceId = localStorage.getItem('vk_device_id') ?? ''
    const state = localStorage.getItem('vk_state') ?? ''
    const intent = localStorage.getItem('oauth_intent')

    localStorage.removeItem('vk_device_id')
    localStorage.removeItem('vk_state')
    localStorage.removeItem('oauth_intent')

    const payload = { code, redirect_uri: redirectUri, device_id: deviceId, state }
    const endpoint = intent === 'link'
      ? '/api/users/me/providers/vk'
      : '/api/auth/oauth/vk'
    const successPath = intent === 'link' ? '/profile' : '/'

    api
      .post(endpoint, payload)
      .then(() => navigate(successPath, { replace: true }))
      .catch((e) => {
        console.error('VK OAuth failed', e instanceof ApiError ? e.detail : e)
        navigate(intent === 'link' ? '/profile' : '/login', { replace: true })
      })
  }, [navigate])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
    </div>
  )
}
```

- [ ] **Step 2: Update `frontend/src/pages/GoogleCallbackPage.tsx`** to handle link intent

Replace the file content with:
```tsx
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '@/lib/api'

export default function GoogleCallbackPage() {
  const navigate = useNavigate()
  const called = useRef(false)

  useEffect(() => {
    if (called.current) return
    called.current = true

    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const error = params.get('error')

    if (error || !code) {
      navigate('/login', { replace: true })
      return
    }

    const intent = localStorage.getItem('oauth_intent')
    localStorage.removeItem('oauth_intent')

    const redirectUri = `${window.location.origin}/auth/google/callback`
    const endpoint = intent === 'link'
      ? '/api/users/me/providers/google'
      : '/api/auth/oauth/google'
    const successPath = intent === 'link' ? '/profile' : '/'

    api
      .post(endpoint, { code, redirect_uri: redirectUri })
      .then(() => navigate(successPath, { replace: true }))
      .catch((e) => {
        console.error('Google OAuth failed', e instanceof ApiError ? e.detail : e)
        navigate(intent === 'link' ? '/profile' : '/login', { replace: true })
      })
  }, [navigate])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
    </div>
  )
}
```

- [ ] **Step 3: Add VK callback route in `frontend/src/App.tsx`**

Add import:
```tsx
import VKCallbackPage from '@/pages/VKCallbackPage'
```

Add route after `<Route path="/auth/google/callback" ...>`:
```tsx
<Route path="/auth/vk/callback" element={<VKCallbackPage />} />
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/VKCallbackPage.tsx frontend/src/pages/GoogleCallbackPage.tsx frontend/src/App.tsx
git commit -m "feat: add VKCallbackPage, update GoogleCallbackPage for link intent"
```

---

## Task 8: Frontend — LoginPage (VK + Telegram OAuth buttons)

Fetch `GET /api/auth/oauth-config` on mount. Show VK button if `vk=true`, Telegram widget if `telegram=true && telegram_bot_username`. Show divider only if at least one OAuth button exists.

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`

- [ ] **Step 1: Replace `frontend/src/pages/LoginPage.tsx`** with updated version

Key changes from current file:
1. Remove `GOOGLE_CLIENT_ID` env var — get it from oauth-config instead (use `settings.google_client_id` on backend, not VITE_)
   - Actually: Google button still needs VITE_GOOGLE_CLIENT_ID for the client-side redirect. The `oauth-config` endpoint just tells us if it's enabled. Keep using VITE_GOOGLE_CLIENT_ID for the redirect URL construction but show/hide based on oauth-config.
2. Add `useQuery` for oauth-config
3. Add VK login button
4. Add Telegram login widget

```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { OAuthConfigResponse } from '@/types/api'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const VK_CLIENT_ID = import.meta.env.VITE_VK_CLIENT_ID as string | undefined

function loginWithGoogle() {
  if (!GOOGLE_CLIENT_ID) return
  const redirectUri = `${window.location.origin}/auth/google/callback`
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth')
  url.searchParams.set('client_id', GOOGLE_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email profile')
  window.location.href = url.toString()
}

function loginWithVK() {
  if (!VK_CLIENT_ID) return
  const deviceId = crypto.randomUUID()
  const state = crypto.randomUUID()
  localStorage.setItem('vk_device_id', deviceId)
  localStorage.setItem('vk_state', state)
  const redirectUri = `${window.location.origin}/auth/vk/callback`
  const url = new URL('https://id.vk.com/authorize')
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', VK_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('state', state)
  url.searchParams.set('device_id', deviceId)
  url.searchParams.set('scope', 'email')
  window.location.href = url.toString()
}

function TelegramLoginButton({
  botUsername,
  onAuth,
}: {
  botUsername: string
  onAuth: (user: Record<string, unknown>) => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !botUsername) return
    ;(window as Record<string, unknown>).__onTelegramAuth = onAuth
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', '__onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    ref.current.appendChild(script)
    return () => {
      delete (window as Record<string, unknown>).__onTelegramAuth
    }
  }, [botUsername, onAuth])

  return <div ref={ref} className="flex justify-center" />
}

type Mode = 'login' | 'register'

export default function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const { data: oauthConfig } = useQuery<OAuthConfigResponse>({
    queryKey: ['oauth-config'],
    queryFn: () => api.get<OAuthConfigResponse>('/api/auth/oauth-config'),
    staleTime: 5 * 60_000,
  })

  const showGoogle = oauthConfig?.google && !!GOOGLE_CLIENT_ID
  const showVK = oauthConfig?.vk && !!VK_CLIENT_ID
  const showTelegram = oauthConfig?.telegram && !!oauthConfig.telegram_bot_username
  const hasOAuth = showGoogle || showVK || showTelegram

  const handleTelegramAuth = useCallback(async (user: Record<string, unknown>) => {
    setError(null)
    setLoading(true)
    try {
      await api.post('/api/auth/oauth/telegram', user)
      navigate('/', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Ошибка входа через Telegram')
    } finally {
      setLoading(false)
    }
  }, [navigate])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'login') {
        await api.post('/api/auth/login', { email, password })
      } else {
        await api.post('/api/auth/register', { email, password, display_name: displayName })
      }
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Ошибка сети')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-card bg-surface p-8 border border-border-neutral">
        <h1 className="text-xl font-bold text-text-primary mb-6">Вход в Skavellion</h1>

        {hasOAuth && (
          <div className="mb-5 flex flex-col gap-2">
            {showGoogle && (
              <button
                type="button"
                onClick={loginWithGoogle}
                className="w-full flex items-center justify-center gap-3 py-2 rounded-input border border-border-neutral bg-background text-sm text-text-primary hover:border-border-accent transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                  <path fill="none" d="M0 0h48v48H0z"/>
                </svg>
                Войти через Google
              </button>
            )}
            {showVK && (
              <button
                type="button"
                onClick={loginWithVK}
                className="w-full flex items-center justify-center gap-3 py-2 rounded-input border border-border-neutral bg-background text-sm text-text-primary hover:border-border-accent transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.48 13.633c.34.332.698.649 1.004.999.135.155.263.316.36.497.138.258.015.544-.222.56l-1.469.002c-.38.031-.682-.12-.933-.375-.2-.205-.387-.425-.58-.637a1.21 1.21 0 00-.261-.228.472.472 0 00-.519.038.957.957 0 00-.228.36 1.948 1.948 0 01-.16.423c-.106.2-.3.256-.507.266-1.122.052-2.185-.123-3.167-.693-1.245-.728-2.173-1.762-2.974-2.927C7.554 9.853 7.019 8.648 6.509 7.432a.396.396 0 01.365-.547l1.476-.003c.218-.003.363.133.443.338.28.71.621 1.392 1.042 2.03.116.175.235.35.38.5.16.164.32.226.487.188.217-.05.337-.224.393-.432.036-.133.05-.269.056-.406.02-.456.025-.91-.067-1.363-.055-.274-.196-.451-.468-.503-.137-.027-.117-.1-.05-.177.11-.13.21-.213.416-.213h1.664c.276.005.367.143.404.42l.002 1.793c-.003.099.047.39.236.454.153.048.253-.068.345-.165.42-.452.717-1.005.986-1.572.118-.253.22-.514.318-.775.072-.193.187-.285.4-.282l1.608-.002c.048 0 .097.002.142.01.27.05.344.17.263.433a5.78 5.78 0 01-.306.742 12.94 12.94 0 01-.913 1.497c-.105.15-.22.292-.326.44-.09.127-.083.254.011.374.14.18.293.348.44.52l.866.965z" fill="#0077FF"/>
                </svg>
                Войти через ВКонтакте
              </button>
            )}
            {showTelegram && oauthConfig?.telegram_bot_username && (
              <TelegramLoginButton
                botUsername={oauthConfig.telegram_bot_username}
                onAuth={handleTelegramAuth}
              />
            )}
          </div>
        )}

        {hasOAuth && (
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-border-neutral" />
            <span className="text-xs text-text-muted">или</span>
            <div className="flex-1 h-px bg-border-neutral" />
          </div>
        )}

        <div className="flex gap-2 mb-6">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(null) }}
            className={`flex-1 py-1.5 rounded-input text-sm font-medium transition-colors ${
              mode === 'login' ? 'bg-accent text-background' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Войти
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(null) }}
            className={`flex-1 py-1.5 rounded-input text-sm font-medium transition-colors ${
              mode === 'register' ? 'bg-accent text-background' : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Регистрация
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="block text-sm text-text-secondary mb-1">Имя</label>
              <input
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                required
                className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
                placeholder="Ваше имя"
              />
            </div>
          )}
          <div>
            <label className="block text-sm text-text-secondary mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-background border border-border-neutral rounded-input px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
              placeholder="Минимум 8 символов"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-input bg-accent text-background font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'Загрузка...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add `VITE_VK_CLIENT_ID` declaration to `frontend/src/vite-env.d.ts`**

Read the file and add `VITE_VK_CLIENT_ID?: string` to `ImportMetaEnv`.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/vite-env.d.ts
git commit -m "feat: add VK and Telegram OAuth buttons on LoginPage, load from oauth-config"
```

---

## Task 9: Frontend — ProfilePage "Add auth method" section

Shows provider add buttons for providers the user doesn't have yet.
- Google: redirects with `oauth_intent=link`
- VK: redirects with `oauth_intent=link` + saves `vk_device_id`/`vk_state`
- Telegram: inline Telegram widget with link endpoint
- Email: inline form (email + password)

Only shows providers that are: (a) enabled in oauth-config, and (b) not already linked to this user.

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Update `frontend/src/pages/ProfilePage.tsx`**

Add imports at top:
```tsx
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import type { OAuthConfigResponse } from '@/types/api'
```

(Replace existing `useQueryClient, useMutation` import since they're already there — just add `useQuery` and `Plus`.)

Add helper functions before the component:
```tsx
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const VK_CLIENT_ID = import.meta.env.VITE_VK_CLIENT_ID as string | undefined

function startGoogleLink() {
  if (!GOOGLE_CLIENT_ID) return
  localStorage.setItem('oauth_intent', 'link')
  const redirectUri = `${window.location.origin}/auth/google/callback`
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth')
  url.searchParams.set('client_id', GOOGLE_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email profile')
  window.location.href = url.toString()
}

function startVKLink() {
  if (!VK_CLIENT_ID) return
  const deviceId = crypto.randomUUID()
  const state = crypto.randomUUID()
  localStorage.setItem('vk_device_id', deviceId)
  localStorage.setItem('vk_state', state)
  localStorage.setItem('oauth_intent', 'link')
  const redirectUri = `${window.location.origin}/auth/vk/callback`
  const url = new URL('https://id.vk.com/authorize')
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', VK_CLIENT_ID)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('state', state)
  url.searchParams.set('device_id', deviceId)
  url.searchParams.set('scope', 'email')
  window.location.href = url.toString()
}
```

Inside `ProfilePage` component, add:
```tsx
const { data: oauthConfig } = useQuery<OAuthConfigResponse>({
  queryKey: ['oauth-config'],
  queryFn: () => api.get<OAuthConfigResponse>('/api/auth/oauth-config'),
  staleTime: 5 * 60_000,
})

const [showEmailForm, setShowEmailForm] = useState(false)
const [linkEmail, setLinkEmail] = useState('')
const [linkPassword, setLinkPassword] = useState('')
const [linkEmailError, setLinkEmailError] = useState<string | null>(null)
const [linkTelegramError, setLinkTelegramError] = useState<string | null>(null)

const linkEmailMutation = useMutation({
  mutationFn: ({ email, password }: { email: string; password: string }) =>
    api.post('/api/users/me/providers/email', { email, password }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['me'] })
    setShowEmailForm(false)
    setLinkEmail('')
    setLinkPassword('')
    setLinkEmailError(null)
  },
  onError: (e) => setLinkEmailError(e instanceof ApiError ? e.detail : 'Ошибка'),
})

const telegramLinkRef = useRef<HTMLDivElement>(null)
const linkedTypes = new Set(user.providers.map((p) => p.type))

const canAddGoogle = oauthConfig?.google && !!GOOGLE_CLIENT_ID && !linkedTypes.has('google')
const canAddVK = oauthConfig?.vk && !!VK_CLIENT_ID && !linkedTypes.has('vk')
const canAddTelegram = oauthConfig?.telegram && !!oauthConfig.telegram_bot_username && !linkedTypes.has('telegram')
const canAddEmail = !linkedTypes.has('email')
const hasAddable = canAddGoogle || canAddVK || canAddTelegram || canAddEmail
```

Add `useRef` import at top.

Add Telegram link widget effect:
```tsx
useEffect(() => {
  if (!canAddTelegram || !oauthConfig?.telegram_bot_username || !telegramLinkRef.current) return
  ;(window as Record<string, unknown>).__onTelegramLink = async (tgUser: Record<string, unknown>) => {
    try {
      await api.post('/api/users/me/providers/telegram', tgUser)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      setLinkTelegramError(null)
    } catch (e) {
      setLinkTelegramError(e instanceof ApiError ? e.detail : 'Ошибка Telegram')
    }
  }
  const script = document.createElement('script')
  script.src = 'https://telegram.org/js/telegram-widget.js?22'
  script.setAttribute('data-telegram-login', oauthConfig.telegram_bot_username)
  script.setAttribute('data-size', 'medium')
  script.setAttribute('data-onauth', '__onTelegramLink(user)')
  script.setAttribute('data-request-access', 'write')
  script.async = true
  telegramLinkRef.current.appendChild(script)
  return () => { delete (window as Record<string, unknown>).__onTelegramLink }
}, [canAddTelegram, oauthConfig?.telegram_bot_username])
```

Add the "Add auth method" UI block after the existing "Привязанные аккаунты" card:
```tsx
{hasAddable && (
  <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
    <h2 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
      <Plus size={14} className="text-accent" /> Добавить способ входа
    </h2>
    <div className="flex flex-col gap-2">
      {canAddGoogle && (
        <button
          onClick={startGoogleLink}
          className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
        >
          Google
        </button>
      )}
      {canAddVK && (
        <button
          onClick={startVKLink}
          className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
        >
          ВКонтакте
        </button>
      )}
      {canAddTelegram && (
        <div>
          <div ref={telegramLinkRef} />
          {linkTelegramError && <p className="mt-1 text-xs text-red-400">{linkTelegramError}</p>}
        </div>
      )}
      {canAddEmail && !showEmailForm && (
        <button
          onClick={() => setShowEmailForm(true)}
          className="flex items-center gap-2.5 rounded-input bg-white/5 px-3 py-2.5 text-sm text-text-secondary hover:text-text-primary transition-colors text-left"
        >
          Email
        </button>
      )}
      {canAddEmail && showEmailForm && (
        <div className="space-y-2">
          <input
            type="email"
            value={linkEmail}
            onChange={e => setLinkEmail(e.target.value)}
            placeholder="Email"
            className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
          <input
            type="password"
            value={linkPassword}
            onChange={e => setLinkPassword(e.target.value)}
            placeholder="Пароль (мин. 8 символов)"
            minLength={8}
            className="w-full rounded-input bg-background border border-border-neutral px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
          {linkEmailError && <p className="text-xs text-red-400">{linkEmailError}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => linkEmailMutation.mutate({ email: linkEmail, password: linkPassword })}
              disabled={linkEmailMutation.isPending || !linkEmail || !linkPassword}
              className="flex-1 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50"
            >
              {linkEmailMutation.isPending ? 'Сохранение…' : 'Добавить Email'}
            </button>
            <button
              onClick={() => { setShowEmailForm(false); setLinkEmailError(null) }}
              className="px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs"
            >
              Отмена
            </button>
          </div>
        </div>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProfilePage.tsx
git commit -m "feat: add 'add auth method' section to ProfilePage"
```

---

## Task 10: Frontend — SubscriptionPage single promo code field

Remove the separate "Активировать промокод без оплаты" block. One promo field: checks the type after validation and shows the right UI. If `bonus_days` and no plan selected, show "Activate without payment" button inline.

**Files:**
- Modify: `frontend/src/pages/SubscriptionPage.tsx`

- [ ] **Step 1: Update SubscriptionPage promo section**

Changes to make in `frontend/src/pages/SubscriptionPage.tsx`:

1. Remove state: `bonusPromoInput`, `bonusResult`, `bonusError`
2. Remove `applyBonusMutation`
3. Remove entire "Standalone bonus apply" section (the second card)
4. In the promo card, after `validatedPromo` success message, add an "Активировать" button that appears only when `validatedPromo.type === 'bonus_days'` AND no plan is selected:

```tsx
{/* Promo code — single unified field */}
<div className="rounded-card bg-surface border border-border-neutral p-4 mb-4">
  <p className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
    <Tag size={14} className="text-accent" /> Промокод
  </p>
  <div className="flex gap-2">
    <input
      value={promoInput}
      onChange={(e) => {
        setPromoInput(e.target.value.toUpperCase())
        setValidatedPromo(null)
        setPromoError(null)
      }}
      placeholder="PROMO2025"
      className="flex-1 rounded-input bg-white/5 border border-border-neutral px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60"
    />
    <button
      onClick={handleValidatePromo}
      disabled={promoValidating || !promoInput.trim()}
      className="rounded-input bg-accent/10 hover:bg-accent/20 text-accent px-4 text-sm font-medium transition-colors disabled:opacity-50"
    >
      {promoValidating ? <Loader2 size={14} className="animate-spin" /> : 'Применить'}
    </button>
  </div>
  {promoError && <p className="mt-2 text-xs text-red-400">{promoError}</p>}
  {validatedPromo && (
    <div className="mt-2">
      <p className="text-xs text-emerald-400">
        {validatedPromo.type === 'discount_percent'
          ? `Скидка ${validatedPromo.value}% — выберите тариф для оплаты`
          : `Бонус ${validatedPromo.value} дн. — выберите тариф или активируйте без оплаты`}
      </p>
      {validatedPromo.type === 'bonus_days' && !selectedPlanId && (
        <button
          onClick={() => applyBonusMutation.mutate({ code: validatedPromo.code })}
          disabled={applyBonusMutation.isPending}
          className="mt-2 rounded-input bg-white/5 hover:bg-white/10 text-text-secondary px-4 py-1.5 text-xs transition-colors disabled:opacity-50"
        >
          {applyBonusMutation.isPending ? <Loader2 size={13} className="animate-spin inline" /> : 'Активировать без оплаты'}
        </button>
      )}
      {applyBonusMutation.isSuccess && (
        <p className="mt-1 text-xs text-emerald-400">
          {(() => {
            const d = applyBonusMutation.data as { days_added: number; new_expires_at: string }
            return `Готово! +${d.days_added} дн. Новый срок: ${formatDate(d.new_expires_at)}`
          })()}
        </p>
      )}
      {applyBonusMutation.isError && (
        <p className="mt-1 text-xs text-red-400">
          {applyBonusMutation.error instanceof ApiError ? applyBonusMutation.error.detail : 'Ошибка'}
        </p>
      )}
    </div>
  )}
</div>
```

Keep `applyBonusMutation` but move it up near other mutations. Remove `bonusPromoInput`, `bonusResult`, `bonusError` state variables.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SubscriptionPage.tsx
git commit -m "feat: merge promo code into single smart field on SubscriptionPage"
```

---

## Task 11: Frontend — InstallPage (remove clash_verge, download btn, load app-config)

Changes:
1. Remove `clash_verge` from `APPS` and `OS_APPS`
2. Always show download button (not just when no subLink)
3. Fetch `GET /api/install/app-config` — use dynamic app name + store URL instead of hardcoded `APPS`
4. Keep deep link templates hardcoded (per-app technical detail)

**Files:**
- Modify: `frontend/src/pages/InstallPage.tsx`

- [ ] **Step 1: Update `frontend/src/pages/InstallPage.tsx`**

Replace the file:

```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Smartphone, Monitor, Download, Terminal, ExternalLink, Copy, Check } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import type { InstallLinkResponse, InstallAppConfig } from '@/types/api'

type OS = 'android' | 'ios' | 'windows' | 'macos' | 'linux'

function detectOS(): OS {
  const ua = navigator.userAgent.toLowerCase()
  if (/android/.test(ua)) return 'android'
  if (/iphone|ipad|ipod/.test(ua)) return 'ios'
  if (/win/.test(ua)) return 'windows'
  if (/mac/.test(ua)) return 'macos'
  return 'linux'
}

const OS_TABS: { id: OS; label: string; icon: React.ComponentType<{ size?: string | number; className?: string }> }[] = [
  { id: 'android', label: 'Android', icon: Smartphone },
  { id: 'ios', label: 'iOS', icon: Smartphone },
  { id: 'windows', label: 'Windows', icon: Monitor },
  { id: 'macos', label: 'macOS', icon: Monitor },
  { id: 'linux', label: 'Linux', icon: Terminal },
]

// Deep link templates per app key (technical, not configurable)
const DEEP_LINK_TEMPLATES: Record<string, (sub: string, name: string) => string> = {
  flclash: (sub) => `flclash://install-config?url=${encodeURIComponent(sub)}`,
  clash_mi: (sub, name) =>
    `clash://install-config?overwrite=no&name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
  clash_meta: (sub, name) =>
    `clashmeta://install-config?name=${encodeURIComponent(name)}&url=${encodeURIComponent(sub)}`,
}

// Steps per OS (generic, same regardless of app name)
const OS_STEPS: Record<OS, string[]> = {
  android: [
    'Установите приложение',
    'Нажмите кнопку ниже для автоматической настройки',
    'Разрешите добавление профиля в приложении',
    'Включите туннель',
  ],
  ios: [
    'Установите приложение из App Store',
    'Нажмите кнопку ниже для автоматической настройки',
    'Подтвердите добавление VPN-профиля',
    'Включите туннель',
  ],
  windows: [
    'Установите приложение',
    'Нажмите кнопку ниже для автоматической настройки',
    'Разрешите добавление профиля',
    'Включите туннель',
  ],
  macos: [
    'Установите приложение',
    'Нажмите кнопку ниже для автоматической настройки',
    'Разрешите добавление профиля',
    'Включите туннель',
  ],
  linux: [
    'Установите приложение',
    'Нажмите кнопку ниже для автоматической настройки',
    'Разрешите добавление профиля',
    'Включите туннель',
  ],
}

// App key per OS for deep link (which deep link template to use)
const OS_APP_KEY: Record<OS, string> = {
  android: 'flclash',
  ios: 'clash_mi',
  windows: 'flclash',
  macos: 'flclash',
  linux: 'flclash',
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors shrink-0"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? 'Скопировано' : 'Скопировать'}
    </button>
  )
}

export default function InstallPage() {
  const { user } = useAuth()
  const [activeOS, setActiveOS] = useState<OS>(detectOS)

  const { data: installData, isLoading, error } = useQuery<InstallLinkResponse>({
    queryKey: ['subscriptionLink'],
    queryFn: () => api.get<InstallLinkResponse>('/api/install/subscription-link'),
    retry: false,
    staleTime: 60_000,
  })

  const { data: appConfig } = useQuery<InstallAppConfig>({
    queryKey: ['installAppConfig'],
    queryFn: () => api.get<InstallAppConfig>('/api/install/app-config'),
    staleTime: 10 * 60_000,
  })

  const is403 = error instanceof ApiError && error.status === 403
  const subLink = installData?.subscription_url ?? ''
  const displayName = user?.display_name ?? 'VPN'

  const osConfig = appConfig?.[activeOS]
  const appName = osConfig?.app_name ?? '…'
  const storeUrl = osConfig?.store_url ?? '#'
  const deepLinkFn = DEEP_LINK_TEMPLATES[OS_APP_KEY[activeOS]]
  const deepLink = subLink && deepLinkFn ? deepLinkFn(subLink, displayName) : null
  const steps = OS_STEPS[activeOS]

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-primary mb-1">Установка</h1>
      <p className="text-sm text-text-muted mb-5">Настройте туннель на вашем устройстве</p>

      {is403 && (
        <div className="rounded-card bg-red-500/10 border border-red-500/20 p-5 mb-5">
          <p className="text-sm text-red-400 mb-3">Подписка истекла. Продлите для доступа к ссылке.</p>
          <Link
            to="/subscription"
            className="inline-block rounded-input bg-accent hover:bg-accent-hover text-white text-sm font-medium px-4 py-2 transition-colors"
          >
            Продлить подписку
          </Link>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 mb-5 text-sm text-text-muted">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Загрузка ссылки…
        </div>
      )}

      {/* OS tabs */}
      <div className="flex gap-1 bg-surface border border-border-neutral rounded-card p-1 mb-5 overflow-x-auto">
        {OS_TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveOS(id)}
            className={cn(
              'flex items-center gap-1.5 rounded-input px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors',
              activeOS === id ? 'bg-accent/15 text-accent' : 'text-text-muted hover:text-text-secondary',
            )}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* Install steps */}
      <div className="rounded-card bg-surface border border-border-neutral p-5 mb-4">
        <h2 className="text-base font-semibold text-text-primary mb-4">{appName}</h2>
        <ol className="space-y-4">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="h-6 w-6 rounded-full bg-accent/15 text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                {i + 1}
              </span>
              <span className="text-sm text-text-secondary">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Download button — always visible */}
      <a
        href={storeUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center gap-2 w-full text-center rounded-input border border-border-neutral bg-surface hover:border-accent/40 text-text-secondary font-medium py-2.5 text-sm transition-colors mb-3"
      >
        <Download size={14} />
        Скачать {appName}
      </a>

      {/* Deep link button — only when subscription is active */}
      {deepLink && (
        <a
          href={deepLink}
          className="flex items-center justify-center gap-2 w-full text-center rounded-input bg-accent hover:bg-accent-hover text-white font-medium py-3 text-sm transition-colors mb-4"
        >
          <ExternalLink size={14} />
          Установить подписку в {appName}
        </a>
      )}

      {/* Manual fallback */}
      {subLink && (
        <div className="rounded-card bg-surface border border-border-neutral p-4">
          <p className="text-xs text-text-muted mb-2">Или вставьте ссылку вручную:</p>
          <div className="flex items-center gap-2 bg-white/5 rounded-input p-3">
            <code className="flex-1 text-xs text-text-secondary break-all">{subLink}</code>
            <CopyButton text={subLink} />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/InstallPage.tsx
git commit -m "feat: update InstallPage — remove clash_verge, always show download btn, load app-config from API"
```

---

## Task 12: Frontend — AdminPlansPage create form

Add a "Добавить тариф" button that expands an inline form above the plan list.

**Files:**
- Modify: `frontend/src/pages/admin/AdminPlansPage.tsx`

- [ ] **Step 1: Update `frontend/src/pages/admin/AdminPlansPage.tsx`**

Add imports:
```tsx
import { Plus, X, Check, Pencil } from 'lucide-react'
import type { PlanAdminItem, PlanAdminUpdateRequest, PlanAdminCreateRequest } from '@/types/api'
```

Add `CreatePlanForm` component before `AdminPlansPage`:
```tsx
function CreatePlanForm({ onCreated }: { onCreated: () => void }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<PlanAdminCreateRequest>({
    name: '',
    label: '',
    duration_days: 30,
    price_rub: 0,
    new_user_price_rub: undefined,
    is_active: true,
    sort_order: 0,
  })
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (data: PlanAdminCreateRequest) =>
      api.post<PlanAdminItem>('/api/admin/plans', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-plans'] })
      onCreated()
      setError(null)
    },
    onError: (e) => setError(e instanceof ApiError ? e.detail : 'Ошибка создания'),
  })

  return (
    <div className="rounded-input bg-surface border border-accent/30 px-4 py-3 mb-4">
      <p className="text-xs font-semibold text-text-muted mb-3 uppercase tracking-wider">Новый тариф</p>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <label className="flex flex-col gap-1 col-span-2">
          <span className="text-xs text-text-muted">Системное имя (уникальное, напр. 2_months)</span>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="2_months"
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Метка</span>
          <input
            value={form.label}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
            placeholder="2 месяца"
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Дней</span>
          <input
            type="number"
            value={form.duration_days}
            onChange={(e) => setForm((f) => ({ ...f, duration_days: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Цена (₽)</span>
          <input
            type="number"
            value={form.price_rub}
            onChange={(e) => setForm((f) => ({ ...f, price_rub: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Цена новому (₽, необяз.)</span>
          <input
            type="number"
            value={form.new_user_price_rub ?? ''}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                new_user_price_rub: e.target.value === '' ? undefined : Number(e.target.value),
              }))
            }
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">Порядок сортировки</span>
          <input
            type="number"
            value={form.sort_order ?? 0}
            onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) }))}
            className="rounded-input bg-background border border-border-neutral px-2.5 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </label>
      </div>
      <label className="flex items-center gap-2 mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_active ?? true}
          onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          className="rounded accent-cyan-500"
        />
        <span className="text-sm text-text-secondary">Активен</span>
      </label>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate(form)}
          disabled={mutation.isPending || !form.name || !form.label}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium disabled:opacity-50"
        >
          <Check size={13} /> Создать
        </button>
        <button
          onClick={onCreated}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-white/5 text-text-secondary text-xs"
        >
          <X size={13} /> Отмена
        </button>
      </div>
    </div>
  )
}
```

In `AdminPlansPage`, add state and render:
```tsx
const [showCreate, setShowCreate] = useState(false)
```

In the return JSX, add header with button + form:
```tsx
<div className="flex items-center justify-between mb-5">
  <h1 className="text-xl font-bold text-text-primary">Тарифы</h1>
  <button
    onClick={() => setShowCreate(true)}
    className="flex items-center gap-1.5 px-3 py-1.5 rounded-input bg-accent text-background text-xs font-medium"
  >
    <Plus size={13} /> Добавить
  </button>
</div>

{showCreate && <CreatePlanForm onCreated={() => setShowCreate(false)} />}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 3: Build to verify no bundle errors**

```bash
cd frontend && npm run build
```

Expected: Build succeeds, no errors

- [ ] **Step 4: Run full backend test suite one last time**

```bash
cd backend && uv run pytest --tb=short -q
```

Expected: All pass

- [ ] **Step 5: Final commit**

```bash
git add frontend/src/pages/admin/AdminPlansPage.tsx
git commit -m "feat: add create plan form to AdminPlansPage"
```

---

## Summary

After all tasks are complete:

| Feature | Status |
|---|---|
| GET /api/auth/oauth-config | ✅ Backend + tests |
| GET /api/install/app-config | ✅ Backend + tests |
| POST /api/admin/plans | ✅ Backend + tests |
| POST /api/users/me/providers/{provider} | ✅ Backend + tests |
| Settings seed (migration) | ✅ Alembic migration |
| LoginPage — VK + Telegram buttons | ✅ Frontend |
| VKCallbackPage | ✅ Frontend |
| GoogleCallbackPage — link intent | ✅ Frontend |
| ProfilePage — add provider | ✅ Frontend |
| SubscriptionPage — single promo field | ✅ Frontend |
| InstallPage — no clash_verge, download always, app-config | ✅ Frontend |
| AdminPlansPage — create form | ✅ Frontend |

**AdminSettingsPage** requires no code changes — seeded settings (telegram_bot_username, site_name, support_telegram_link, install_* keys) appear automatically in the existing key-value UI.

**Environment variables to add for VK OAuth:**
- Backend `.env`: `VK_CLIENT_ID=...`, `VK_CLIENT_SECRET=...`
- Frontend `.env.local`: `VITE_VK_CLIENT_ID=...`

**Telegram setup:** Set `telegram_bot_username` in AdminSettings → Settings after deploying.
