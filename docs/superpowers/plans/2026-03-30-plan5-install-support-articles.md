# Plan 5: Install, Support & Articles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three small backend feature groups: subscription link endpoint for the Installation page, contact form support endpoint, and public articles (documentation) endpoints.

**Architecture:** Three independent routers — `install`, `support`, `articles` — each registered in `main.py`. Install uses Redis caching (1h TTL) for subscription URLs fetched from Remnawave. Support reuses `send_admin_alert` for Telegram delivery and `check_rate_limit` for abuse prevention. Articles are public read-only from the `articles` DB table.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Redis (asyncio), pytest-asyncio, AsyncMock/MagicMock/patch, `uv run pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `backend/app/schemas/install.py` | `SubscriptionLinkResponse` |
| **Create** | `backend/app/schemas/support.py` | `SupportMessageRequest` |
| **Create** | `backend/app/schemas/article.py` | `ArticleListItem`, `ArticleDetail` |
| **Create** | `backend/app/routers/install.py` | `GET /api/install/subscription-link` |
| **Create** | `backend/app/routers/support.py` | `POST /api/support/message` |
| **Create** | `backend/app/routers/articles.py` | `GET /api/articles`, `GET /api/articles/{slug}` |
| **Modify** | `backend/app/main.py` | Register 3 new routers |
| **Create** | `backend/tests/routers/test_install.py` | 5 tests |
| **Create** | `backend/tests/routers/test_support.py` | 4 tests |
| **Create** | `backend/tests/routers/test_articles.py` | 4 tests |

---

## Task 1: Schemas (install + support + articles)

**Files:**
- Create: `backend/app/schemas/install.py`
- Create: `backend/app/schemas/support.py`
- Create: `backend/app/schemas/article.py`

- [ ] **Step 1: Create install schema**

```python
# backend/app/schemas/install.py
from pydantic import BaseModel


class SubscriptionLinkResponse(BaseModel):
    subscription_url: str
```

- [ ] **Step 2: Create support schema**

```python
# backend/app/schemas/support.py
from pydantic import BaseModel, field_validator


class SupportMessageRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Сообщение не может быть пустым")
        if len(v) > 2000:
            raise ValueError("Сообщение слишком длинное (максимум 2000 символов)")
        return v
```

- [ ] **Step 3: Create article schemas**

```python
# backend/app/schemas/article.py
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ArticleListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    preview_image_url: str | None
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ArticleDetail(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    content: str
    preview_image_url: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Verify all imports work**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run python -c "from app.schemas.install import SubscriptionLinkResponse; from app.schemas.support import SupportMessageRequest; from app.schemas.article import ArticleListItem, ArticleDetail; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/schemas/install.py app/schemas/support.py app/schemas/article.py
git commit -m "feat: add install, support, article schemas"
```

---

## Task 2: Install Router (`GET /api/install/subscription-link`)

**Spec:**
- Auth required (`get_current_user`)
- Returns 403 if user has no subscription OR subscription is not active (status != active)
- On success: tries Redis cache first (`sub_url:{user_id}`, 1h TTL = 3600s)
- Cache miss: calls `RemnawaveClient.get_user(remnawave_uuid)`, caches result, returns URL
- If Remnawave not configured in settings → 503

**Files:**
- Create: `backend/app/routers/install.py`
- Create: `backend/tests/routers/test_install.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/routers/test_install.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.redis_client import get_redis
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionType


def _make_user(remnawave_uuid=None):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.remnawave_uuid = remnawave_uuid or uuid.uuid4()
    return u


def _make_sub(status=SubscriptionStatus.active, type_=SubscriptionType.paid):
    s = MagicMock(spec=Subscription)
    s.status = status
    s.type = type_
    return s


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_install_no_subscription_returns_403():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=None):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_install_expired_subscription_returns_403():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    sub = _make_sub(status=SubscriptionStatus.expired)
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=sub):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_install_returns_cached_url():
    user = _make_user()
    sub = _make_sub()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value="https://rw.example.com/sub/abc123")
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=sub):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["subscription_url"] == "https://rw.example.com/sub/abc123"


@pytest.mark.asyncio
async def test_install_rw_not_configured_returns_503():
    user = _make_user()
    sub = _make_sub()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)  # cache miss
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.install.get_user_subscription", return_value=sub), \
         patch("app.routers.install.get_setting", return_value=None), \
         patch("app.routers.install.get_setting_decrypted", return_value=None):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_install_fetches_from_remnawave_and_caches():
    user = _make_user()
    sub = _make_sub()
    redis = AsyncMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)  # cache miss
    redis.set = AsyncMock()

    rw_user = MagicMock()
    rw_user.subscription_url = "https://rw.example.com/sub/fresh"

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    mock_rw_client = AsyncMock()
    mock_rw_client.get_user = AsyncMock(return_value=rw_user)

    with patch("app.routers.install.get_user_subscription", return_value=sub), \
         patch("app.routers.install.get_setting", return_value="http://rw"), \
         patch("app.routers.install.get_setting_decrypted", return_value="token"), \
         patch("app.routers.install.RemnawaveClient", return_value=mock_rw_client):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/install/subscription-link")
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["subscription_url"] == "https://rw.example.com/sub/fresh"
    # Verify cache was set
    redis.set.assert_called_once()
```

- [ ] **Step 2: Run tests — expect ImportError (router not registered)**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_install.py -v 2>&1 | head -20`
Expected: Errors (404 or ImportError)

- [ ] **Step 3: Create the router**

```python
# backend/app/routers/install.py
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.subscription import SubscriptionStatus
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.install import SubscriptionLinkResponse
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import get_user_subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/install", tags=["install"])

_SUB_URL_TTL = 3600  # 1 hour


@router.get("/subscription-link", response_model=SubscriptionLinkResponse)
async def get_subscription_link(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SubscriptionLinkResponse:
    # Guard: must have an active subscription
    sub = await get_user_subscription(db, current_user.id)
    if sub is None or sub.status != SubscriptionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подписка неактивна. Для доступа к ссылке установки продлите подписку.",
        )

    # Try Redis cache first
    cache_key = f"sub_url:{current_user.id}"
    cached = await redis.get(cache_key)
    if cached:
        return SubscriptionLinkResponse(subscription_url=cached)

    # Cache miss — fetch from Remnawave
    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )

    rw_client = RemnawaveClient(url, token)
    try:
        rw_user = await rw_client.get_user(str(current_user.remnawave_uuid))
    except Exception as exc:
        logger.exception("Failed to fetch subscription URL from Remnawave: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )

    subscription_url = rw_user.subscription_url
    await redis.set(cache_key, subscription_url, ex=_SUB_URL_TTL)

    return SubscriptionLinkResponse(subscription_url=subscription_url)
```

- [ ] **Step 4: Register in main.py** — add after `from app.routers import promo_codes`:
```python
from app.routers import install
```
And after `app.include_router(promo_codes.router)`:
```python
app.include_router(install.router)
```

- [ ] **Step 5: Run install tests — expect 5 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_install.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 5 passed

- [ ] **Step 6: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 109 passed

- [ ] **Step 7: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/install.py app/main.py tests/routers/test_install.py
git commit -m "feat: add GET /api/install/subscription-link with Redis cache"
```

---

## Task 3: Support Router (`POST /api/support/message`)

**Spec:**
- Auth required
- Rate limit: 5 per user per hour (Redis key: `rate:support:{user_id}`)
- Sends message to Telegram via existing `send_admin_alert(bot_token, chat_id, text)`
  - Bot token from `telegram_bot_token` setting (encrypted)
  - Chat from `telegram_support_chat_id` setting
- Message format: `"📨 Новое сообщение\nОт: {display_name} (#{user_id_short})\n\n{message}"`
- Returns 200 `{"ok": true}` on success
- If Telegram not configured (no token/chat): still returns 200 (graceful degradation — message "sent" from user's perspective, just not delivered). This matches `send_admin_alert` which is fire-and-forget.

**Files:**
- Create: `backend/app/routers/support.py`
- Create: `backend/tests/routers/test_support.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/routers/test_support.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.redis_client import get_redis
from app.models.user import User


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.display_name = "Тест Пользователь"
    return u


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


def _override_user(user):
    async def _dep():
        return user
    return _dep


def _override_redis(mock_redis):
    async def _dep():
        return mock_redis
    return _dep


@pytest.mark.asyncio
async def test_support_rate_limited_returns_429():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=6)  # over limit of 5
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/support/message", json={"message": "помогите"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_support_empty_message_returns_422():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/support/message", json={"message": "   "})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_support_success_returns_200():
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.support.get_setting", return_value="bot_token_value"), \
         patch("app.routers.support.get_setting_decrypted", return_value="secret_token"), \
         patch("app.routers.support.send_admin_alert", new_callable=AsyncMock) as mock_alert:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/support/message", json={"message": "Нужна помощь"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_alert.assert_called_once()


@pytest.mark.asyncio
async def test_support_no_telegram_config_still_returns_200():
    """Even if Telegram is not configured, endpoint returns 200 (graceful degradation)."""
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.support.get_setting", return_value=None), \
         patch("app.routers.support.get_setting_decrypted", return_value=None), \
         patch("app.routers.support.send_admin_alert", new_callable=AsyncMock):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/support/message", json={"message": "Нужна помощь"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_support.py -v 2>&1 | head -15`
Expected: Errors (404 or ImportError)

- [ ] **Step 3: Create the router**

```python
# backend/app/routers/support.py
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.support import SupportMessageRequest
from app.services.rate_limiter import check_rate_limit
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.telegram_alert import send_admin_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/support", tags=["support"])

_SUPPORT_RATE_LIMIT = 5
_SUPPORT_RATE_WINDOW = 3600  # 1 hour


@router.post("/message")
async def send_support_message(
    data: SupportMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    # Rate limit per user
    rate_key = f"rate:support:{current_user.id}"
    if not await check_rate_limit(redis, rate_key, _SUPPORT_RATE_LIMIT, _SUPPORT_RATE_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много сообщений. Попробуйте позже.",
        )

    user_id_short = str(current_user.id)[:8]
    text = (
        f"📨 Новое сообщение\n"
        f"От: {current_user.display_name} (#{user_id_short})\n\n"
        f"{data.message}"
    )

    bot_token = await get_setting_decrypted(db, "telegram_bot_token")
    chat_id = await get_setting(db, "telegram_support_chat_id")

    # Fire-and-forget — send_admin_alert swallows all exceptions
    await send_admin_alert(bot_token, chat_id, text)

    return {"ok": True}
```

- [ ] **Step 4: Register in main.py** — add after `from app.routers import install`:
```python
from app.routers import support
```
And after `app.include_router(install.router)`:
```python
app.include_router(support.router)
```

- [ ] **Step 5: Run support tests — expect 4 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_support.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 4 passed

- [ ] **Step 6: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 113 passed

- [ ] **Step 7: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/support.py app/main.py tests/routers/test_support.py
git commit -m "feat: add POST /api/support/message with rate limiting"
```

---

## Task 4: Articles Router (`GET /api/articles`, `GET /api/articles/{slug}`)

**Spec:**
- Public endpoints — no auth required
- `GET /api/articles` — returns published articles (`is_published=True`) sorted by `sort_order` ASC
- `GET /api/articles/{slug}` — returns single article; 404 if not found OR not published

**Files:**
- Create: `backend/app/routers/articles.py`
- Create: `backend/tests/routers/test_articles.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/routers/test_articles.py
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.article import Article


NOW = datetime.now(tz=timezone.utc)


def _make_article(slug="test-slug", title="Тест", is_published=True):
    a = MagicMock(spec=Article)
    a.id = uuid.uuid4()
    a.slug = slug
    a.title = title
    a.content = "# Заголовок\n\nТекст статьи."
    a.preview_image_url = None
    a.is_published = is_published
    a.sort_order = 0
    a.created_at = NOW
    a.updated_at = NOW
    return a


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


@pytest.mark.asyncio
async def test_articles_list_returns_published():
    article = _make_article()
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[article])))))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slug"] == "test-slug"


@pytest.mark.asyncio
async def test_articles_list_empty():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_articles_detail_found():
    article = _make_article(slug="how-to-install")
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=article)))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles/how-to-install")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["slug"] == "how-to-install"
    assert "content" in resp.json()


@pytest.mark.asyncio
async def test_articles_detail_not_found():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/articles/nonexistent")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_articles.py -v 2>&1 | head -15`
Expected: Errors (404 or ImportError)

- [ ] **Step 3: Create the router**

```python
# backend/app/routers/articles.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleDetail, ArticleListItem

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=list[ArticleListItem])
async def list_articles(
    db: AsyncSession = Depends(get_db),
) -> list[ArticleListItem]:
    result = await db.execute(
        select(Article)
        .where(Article.is_published == True)
        .order_by(Article.sort_order.asc())
    )
    articles = result.scalars().all()
    return [ArticleListItem.model_validate(a) for a in articles]


@router.get("/{slug}", response_model=ArticleDetail)
async def get_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> ArticleDetail:
    result = await db.execute(
        select(Article).where(Article.slug == slug, Article.is_published == True)
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    return ArticleDetail.model_validate(article)
```

- [ ] **Step 4: Register in main.py** — add after `from app.routers import support`:
```python
from app.routers import articles
```
And after `app.include_router(support.router)`:
```python
app.include_router(articles.router)
```

- [ ] **Step 5: Run articles tests — expect 4 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_articles.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 4 passed

- [ ] **Step 6: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 117 passed

- [ ] **Step 7: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/articles.py app/main.py tests/routers/test_articles.py
git commit -m "feat: add GET /api/articles and GET /api/articles/{slug}"
```

---

## Final Verification

- [ ] **Run full suite**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest -v 2>&1 | tail -10`
Expected: 117 passed, 0 failed

- [ ] **Tag**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git tag plan-5-complete
```
