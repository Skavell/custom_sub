# Plan 7: Admin API Part 2 — Plans, Promo Codes, Articles, Settings, Support Log

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the admin API with CRUD endpoints for Plans, Promo Codes, Articles, Settings management, and a Support Message log with DB persistence.

**Architecture:** All new endpoints appended to `app/routers/admin.py` under `/api/admin`. New schemas added to `app/schemas/admin.py`. Support messages require a new SQLAlchemy model (`SupportMessage`) registered in `app/models/__init__.py`, an Alembic migration, and an update to the existing `POST /api/support/message` router to persist to DB (best-effort — never raises). No new service files; logic stays thin in the router.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, pytest-asyncio, AsyncMock/MagicMock/patch, `uv run pytest`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Modify** | `backend/app/schemas/admin.py` | Add Plan, PromoCode, Article, Setting, SupportMessage schemas |
| **Modify** | `backend/app/routers/admin.py` | Append all new endpoints |
| **Create** | `backend/app/models/support_message.py` | SupportMessage ORM model |
| **Modify** | `backend/app/models/__init__.py` | Register SupportMessage for Alembic discovery |
| **Create** | `backend/alembic/versions/<rev>_add_support_messages.py` | Migration: create support_messages table |
| **Modify** | `backend/app/routers/support.py` | Persist message to DB (best-effort) |
| **Modify** | `backend/tests/routers/test_admin.py` | Append all new admin tests |
| **Modify** | `backend/tests/routers/test_support.py` | Add DB-persist test |

---

## Task 1: Extend Admin Schemas

**Files:**
- Modify: `backend/app/schemas/admin.py`

- [ ] **Step 1: Append new schema classes**

Open `backend/app/schemas/admin.py` and append at the end:

```python

# --- Plans ---

class PlanAdminItem(BaseModel):
    id: uuid.UUID
    name: str
    label: str
    duration_days: int
    price_rub: int
    new_user_price_rub: int | None
    is_active: bool
    sort_order: int
    model_config = {"from_attributes": True}


class PlanUpdateRequest(BaseModel):
    label: str | None = None
    duration_days: int | None = None
    price_rub: int | None = None
    new_user_price_rub: int | None = None
    is_active: bool | None = None


# --- Promo Codes ---

class PromoCodeAdminItem(BaseModel):
    id: uuid.UUID
    code: str
    type: str
    value: int
    max_uses: int | None
    used_count: int
    valid_until: datetime | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class PromoCodeCreateRequest(BaseModel):
    code: str
    type: str  # "discount_percent" | "bonus_days"
    value: int
    max_uses: int | None = None
    valid_until: datetime | None = None
    is_active: bool = True


# --- Articles ---

class ArticleAdminListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    preview_image_url: str | None
    is_published: bool
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ArticleAdminDetail(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    content: str
    preview_image_url: str | None
    is_published: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ArticleCreateRequest(BaseModel):
    slug: str
    title: str
    content: str
    preview_image_url: str | None = None
    sort_order: int = 0
    is_published: bool = False


class ArticleUpdateRequest(BaseModel):
    slug: str | None = None
    title: str | None = None
    content: str | None = None
    preview_image_url: str | None = None
    sort_order: int | None = None


# --- Settings ---

class SettingAdminItem(BaseModel):
    key: str
    value: str  # "***" if sensitive
    is_sensitive: bool
    updated_at: datetime


# --- Settings upsert ---

class SettingUpsertRequest(BaseModel):
    value: str
    is_sensitive: bool = False


# --- Support Messages ---

class SupportMessageAdminItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    message: str
    created_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Verify import**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run python -c "from app.schemas.admin import PlanAdminItem, PromoCodeAdminItem, ArticleAdminDetail, SettingAdminItem, SupportMessageAdminItem; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/schemas/admin.py
git commit -m "feat: extend admin schemas for plans, promo codes, articles, settings, support"
```

---

## Task 2: Admin Plans Endpoints

**Files:**
- Modify: `backend/app/routers/admin.py` (append)
- Modify: `backend/tests/routers/test_admin.py` (append)

### Context
- `Plan` model: `id` (UUID), `name`, `label`, `duration_days`, `price_rub`, `new_user_price_rub`, `is_active`, `sort_order`
- `GET /api/admin/plans` — list ALL plans including inactive, ordered by `sort_order asc`
- `PATCH /api/admin/plans/{plan_id}` — partial update; `db.get(Plan, plan_id)` for lookup; 404 if not found

- [ ] **Step 1: Append tests to test_admin.py**

Append to `backend/tests/routers/test_admin.py`:

```python
from app.models.plan import Plan as PlanModel


# --- GET /api/admin/plans ---

@pytest.mark.asyncio
async def test_admin_plans_list_returns_all_including_inactive():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    plan = MagicMock(spec=PlanModel)
    plan.id = uuid.uuid4()
    plan.name = "basic"
    plan.label = "Базовый"
    plan.duration_days = 30
    plan.price_rub = 300
    plan.new_user_price_rub = None
    plan.is_active = False  # inactive — must still appear
    plan.sort_order = 0

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [plan]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/plans")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_active"] is False
    assert data[0]["label"] == "Базовый"


@pytest.mark.asyncio
async def test_admin_plan_patch_updates_fields():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    plan = MagicMock(spec=PlanModel)
    plan.id = uuid.uuid4()
    plan.name = "basic"
    plan.label = "Базовый"
    plan.duration_days = 30
    plan.price_rub = 300
    plan.new_user_price_rub = None
    plan.is_active = True
    plan.sort_order = 0

    db.get = AsyncMock(return_value=plan)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(
                f"/api/admin/plans/{plan.id}",
                json={"price_rub": 500, "is_active": False},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert plan.price_rub == 500
    assert plan.is_active is False
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_admin_plan_patch_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(f"/api/admin/plans/{uuid.uuid4()}", json={"price_rub": 100})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
```

- [ ] **Step 2: Run new tests — expect failures**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py::test_admin_plans_list_returns_all_including_inactive -v 2>&1 | head -15`
Expected: FAILED (404 — endpoint doesn't exist yet)

- [ ] **Step 3: Append plans endpoints to admin.py**

Add these imports to the top of `backend/app/routers/admin.py` (in the models import block):
```python
from app.models.plan import Plan
from app.schemas.admin import PlanAdminItem, PlanUpdateRequest  # add to existing schemas import
```

Then append to the router:

```python

# --- Admin Plans ---

@router.get("/plans", response_model=list[PlanAdminItem])
async def admin_list_plans(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PlanAdminItem]:
    result = await db.execute(select(Plan).order_by(Plan.sort_order.asc()))
    plans = result.scalars().all()
    return [PlanAdminItem.model_validate(p) for p in plans]


@router.patch("/plans/{plan_id}", response_model=PlanAdminItem)
async def admin_update_plan(
    plan_id: uuid.UUID,
    data: PlanUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PlanAdminItem:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тариф не найден")
    if data.label is not None:
        plan.label = data.label
    if data.duration_days is not None:
        plan.duration_days = data.duration_days
    if data.price_rub is not None:
        plan.price_rub = data.price_rub
    if data.new_user_price_rub is not None:
        plan.new_user_price_rub = data.new_user_price_rub
    if data.is_active is not None:
        plan.is_active = data.is_active
    await db.commit()
    return PlanAdminItem.model_validate(plan)
```

- [ ] **Step 4: Run plan tests — expect 3 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -k "plan" -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 3 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 136 passed

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/admin.py tests/routers/test_admin.py
git commit -m "feat: add admin plans list and patch endpoints"
```

---

## Task 3: Admin Promo Codes Endpoints

**Files:**
- Modify: `backend/app/routers/admin.py` (append)
- Modify: `backend/tests/routers/test_admin.py` (append)

### Context
- `PromoCode` model: `id`, `code` (unique, stored uppercase), `type` (PromoCodeType enum: `discount_percent`|`bonus_days`), `value`, `max_uses`, `used_count`, `valid_until`, `is_active`, `created_at`
- `GET /api/admin/promo-codes` — list all, ordered by `created_at desc`
- `POST /api/admin/promo-codes` → 201; code uppercased; 409 on `IntegrityError` (duplicate code)
- `PATCH /api/admin/promo-codes/{code_id}/toggle` — flip `is_active`; 404 if not found
- `DELETE /api/admin/promo-codes/{code_id}` → 204; 404 if not found

- [ ] **Step 1: Append tests to test_admin.py**

Append to `backend/tests/routers/test_admin.py`:

```python
from app.models.promo_code import PromoCode as PromoCodeModel, PromoCodeType
from sqlalchemy.exc import IntegrityError


# --- GET /api/admin/promo-codes ---

@pytest.mark.asyncio
async def test_admin_promo_list_returns_all():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    promo = MagicMock(spec=PromoCodeModel)
    promo.id = uuid.uuid4()
    promo.code = "SALE10"
    promo.type = PromoCodeType.discount_percent
    promo.value = 10
    promo.max_uses = None
    promo.used_count = 0
    promo.valid_until = None
    promo.is_active = True
    promo.created_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [promo]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/promo-codes")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "SALE10"


@pytest.mark.asyncio
async def test_admin_promo_create_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/promo-codes",
                json={"code": "test10", "type": "discount_percent", "value": 10},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "TEST10"  # uppercased


@pytest.mark.asyncio
async def test_admin_promo_create_duplicate_returns_409():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, Exception()))
    db.rollback = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/promo-codes",
                json={"code": "EXISTING", "type": "bonus_days", "value": 7},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_promo_toggle_flips_is_active():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    promo = MagicMock(spec=PromoCodeModel)
    promo.id = uuid.uuid4()
    promo.code = "SALE10"
    promo.type = PromoCodeType.discount_percent
    promo.value = 10
    promo.max_uses = None
    promo.used_count = 0
    promo.valid_until = None
    promo.is_active = True
    promo.created_at = NOW

    db.get = AsyncMock(return_value=promo)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(f"/api/admin/promo-codes/{promo.id}/toggle")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert promo.is_active is False
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_admin_promo_delete_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    promo = MagicMock(spec=PromoCodeModel)
    db.get = AsyncMock(return_value=promo)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api/admin/promo-codes/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    db.delete.assert_called_once_with(promo)
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_admin_promo_delete_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api/admin/promo-codes/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
```

- [ ] **Step 2: Run new tests — expect failures**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py::test_admin_promo_list_returns_all -v 2>&1 | head -15`
Expected: FAILED (404)

- [ ] **Step 3: Append promo code endpoints to admin.py**

Add to imports in `backend/app/routers/admin.py`:
```python
from sqlalchemy.exc import IntegrityError
from app.models.promo_code import PromoCode, PromoCodeType
from app.schemas.admin import PromoCodeAdminItem, PromoCodeCreateRequest  # add to existing import
```

Append to the router:

```python

# --- Admin Promo Codes ---

@router.get("/promo-codes", response_model=list[PromoCodeAdminItem])
async def admin_list_promo_codes(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PromoCodeAdminItem]:
    result = await db.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
    promos = result.scalars().all()
    return [PromoCodeAdminItem.model_validate(p) for p in promos]


@router.post("/promo-codes", response_model=PromoCodeAdminItem, status_code=201)
async def admin_create_promo_code(
    data: PromoCodeCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PromoCodeAdminItem:
    try:
        promo_type = PromoCodeType(data.type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный тип промокода")

    promo = PromoCode(
        code=data.code.upper(),
        type=promo_type,
        value=data.value,
        max_uses=data.max_uses,
        valid_until=data.valid_until,
        is_active=data.is_active,
    )
    db.add(promo)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Промокод уже существует")
    await db.refresh(promo)
    return PromoCodeAdminItem.model_validate(promo)


@router.patch("/promo-codes/{code_id}/toggle", response_model=PromoCodeAdminItem)
async def admin_toggle_promo_code(
    code_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PromoCodeAdminItem:
    promo = await db.get(PromoCode, code_id)
    if promo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
    promo.is_active = not promo.is_active
    await db.commit()
    return PromoCodeAdminItem.model_validate(promo)


@router.delete("/promo-codes/{code_id}", status_code=204)
async def admin_delete_promo_code(
    code_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    promo = await db.get(PromoCode, code_id)
    if promo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
    await db.delete(promo)
    await db.commit()
```

- [ ] **Step 4: Run promo tests — expect 6 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -k "promo" -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 6 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 142 passed

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/admin.py tests/routers/test_admin.py
git commit -m "feat: add admin promo codes CRUD endpoints"
```

---

## Task 4: Admin Articles Endpoints

**Files:**
- Modify: `backend/app/routers/admin.py` (append)
- Modify: `backend/tests/routers/test_admin.py` (append)

### Context
- `Article` model: `id`, `slug` (unique), `title`, `content`, `preview_image_url`, `is_published`, `sort_order`, `created_at`, `updated_at`
- `GET /api/admin/articles` — list ALL including unpublished, ordered by `sort_order asc`
- `POST /api/admin/articles` → 201; 409 on slug duplicate (`IntegrityError`)
- `GET /api/admin/articles/{article_id}` — `db.get(Article, article_id)`, 404 if not found
- `PATCH /api/admin/articles/{article_id}` — partial update; 409 on slug duplicate; 404 if not found
- `DELETE /api/admin/articles/{article_id}` → 204; 404 if not found
- `POST /api/admin/articles/{article_id}/publish` — set `is_published=True`, commit, return
- `POST /api/admin/articles/{article_id}/unpublish` — set `is_published=False`, commit, return

- [ ] **Step 1: Append tests to test_admin.py**

Append to `backend/tests/routers/test_admin.py`:

```python
from app.models.article import Article as ArticleModel


def _make_article(published=True):
    a = MagicMock(spec=ArticleModel)
    a.id = uuid.uuid4()
    a.slug = "test-article"
    a.title = "Тест"
    a.content = "Содержимое"
    a.preview_image_url = None
    a.is_published = published
    a.sort_order = 0
    a.created_at = NOW
    a.updated_at = NOW
    return a


# --- GET /api/admin/articles ---

@pytest.mark.asyncio
async def test_admin_articles_list_includes_unpublished():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article(published=False)

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [article]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/articles")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["is_published"] is False


@pytest.mark.asyncio
async def test_admin_article_create_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/articles",
                json={"slug": "new-article", "title": "Новая", "content": "Текст"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_admin_article_create_duplicate_slug_returns_409():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=IntegrityError("duplicate", {}, Exception()))
    db.rollback = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/admin/articles",
                json={"slug": "existing-slug", "title": "Новая", "content": "Текст"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_article_get_not_found_returns_404():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=None)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/admin/articles/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_article_patch_updates_title():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article()
    db.get = AsyncMock(return_value=article)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.patch(
                f"/api/admin/articles/{article.id}",
                json={"title": "Обновлённый заголовок"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert article.title == "Обновлённый заголовок"


@pytest.mark.asyncio
async def test_admin_article_delete_success():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article()
    db.get = AsyncMock(return_value=article)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete(f"/api/admin/articles/{article.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    db.delete.assert_called_once_with(article)


@pytest.mark.asyncio
async def test_admin_article_publish_sets_published():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article(published=False)
    db.get = AsyncMock(return_value=article)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/admin/articles/{article.id}/publish")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert article.is_published is True


@pytest.mark.asyncio
async def test_admin_article_unpublish_clears_published():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)
    article = _make_article(published=True)
    db.get = AsyncMock(return_value=article)
    db.commit = AsyncMock()

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/admin/articles/{article.id}/unpublish")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert article.is_published is False
```

- [ ] **Step 2: Run new tests — expect failures**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py::test_admin_articles_list_includes_unpublished -v 2>&1 | head -15`
Expected: FAILED (404)

- [ ] **Step 3: Append article endpoints to admin.py**

Add to imports in `backend/app/routers/admin.py`:
```python
from app.models.article import Article
from app.schemas.admin import (
    ArticleAdminDetail, ArticleAdminListItem,
    ArticleCreateRequest, ArticleUpdateRequest,  # add to existing import
)
```

Append to the router:

```python

# --- Admin Articles ---

@router.get("/articles", response_model=list[ArticleAdminListItem])
async def admin_list_articles(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ArticleAdminListItem]:
    result = await db.execute(select(Article).order_by(Article.sort_order.asc()))
    articles = result.scalars().all()
    return [ArticleAdminListItem.model_validate(a) for a in articles]


@router.post("/articles", response_model=ArticleAdminDetail, status_code=201)
async def admin_create_article(
    data: ArticleCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ArticleAdminDetail:
    article = Article(
        slug=data.slug,
        title=data.title,
        content=data.content,
        preview_image_url=data.preview_image_url,
        sort_order=data.sort_order,
        is_published=data.is_published,
    )
    db.add(article)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug уже существует")
    await db.refresh(article)
    return ArticleAdminDetail.model_validate(article)


@router.get("/articles/{article_id}", response_model=ArticleAdminDetail)
async def admin_get_article(
    article_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ArticleAdminDetail:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    return ArticleAdminDetail.model_validate(article)


@router.patch("/articles/{article_id}", response_model=ArticleAdminDetail)
async def admin_update_article(
    article_id: uuid.UUID,
    data: ArticleUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ArticleAdminDetail:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    if data.slug is not None:
        article.slug = data.slug
    if data.title is not None:
        article.title = data.title
    if data.content is not None:
        article.content = data.content
    if data.preview_image_url is not None:
        article.preview_image_url = data.preview_image_url
    if data.sort_order is not None:
        article.sort_order = data.sort_order
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug уже существует")
    await db.refresh(article)
    return ArticleAdminDetail.model_validate(article)


@router.delete("/articles/{article_id}", status_code=204)
async def admin_delete_article(
    article_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    await db.delete(article)
    await db.commit()


@router.post("/articles/{article_id}/publish", response_model=ArticleAdminDetail)
async def admin_publish_article(
    article_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ArticleAdminDetail:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    article.is_published = True
    await db.commit()
    return ArticleAdminDetail.model_validate(article)


@router.post("/articles/{article_id}/unpublish", response_model=ArticleAdminDetail)
async def admin_unpublish_article(
    article_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ArticleAdminDetail:
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")
    article.is_published = False
    await db.commit()
    return ArticleAdminDetail.model_validate(article)
```

- [ ] **Step 4: Run article tests — expect 8 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -k "article" -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 8 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 150 passed

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/admin.py tests/routers/test_admin.py
git commit -m "feat: add admin articles CRUD and publish/unpublish endpoints"
```

---

## Task 5: Admin Settings Endpoints

**Files:**
- Modify: `backend/app/routers/admin.py` (append)
- Modify: `backend/tests/routers/test_admin.py` (append)

### Context
- `Setting` model: `key` (PK str), `value` (JSONB: `{"value": "plain"}` or `{"encrypted": "blob"}`), `is_sensitive` (bool), `updated_at`
- `GET /api/admin/settings` — list all ordered by `key asc`; mask sensitive rows: return `value="***"` if `is_sensitive=True`, else `setting.value.get("value", "")`
- `PUT /api/admin/settings/{key}` — call `set_setting(db, key, data.value, data.is_sensitive)`, then return `SettingAdminItem` constructed from request data (no re-fetch needed); if `is_sensitive`, return `value="***"`
- `set_setting` is already imported from `app.services.setting_service` — just add `set_setting` to the existing import

- [ ] **Step 1: Append tests to test_admin.py**

Append to `backend/tests/routers/test_admin.py`:

```python
from app.models.setting import Setting as SettingModel


# --- GET /api/admin/settings ---

@pytest.mark.asyncio
async def test_admin_settings_list_masks_sensitive():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    s = MagicMock(spec=SettingModel)
    s.key = "telegram_bot_token"
    s.value = {"encrypted": "abc123"}
    s.is_sensitive = True
    s.updated_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [s]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/settings")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["value"] == "***"
    assert data[0]["is_sensitive"] is True


@pytest.mark.asyncio
async def test_admin_settings_list_shows_plain_value():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    s = MagicMock(spec=SettingModel)
    s.key = "remnawave_url"
    s.value = {"value": "http://rw.example.com"}
    s.is_sensitive = False
    s.updated_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [s]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/settings")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["value"] == "http://rw.example.com"


@pytest.mark.asyncio
async def test_admin_settings_upsert_plain():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.set_setting", new_callable=AsyncMock) as mock_set:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.put(
                    "/api/admin/settings/remnawave_url",
                    json={"value": "http://rw.example.com", "is_sensitive": False},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_set.assert_called_once_with(db, "remnawave_url", "http://rw.example.com", False)
    data = resp.json()
    assert data["value"] == "http://rw.example.com"


@pytest.mark.asyncio
async def test_admin_settings_upsert_sensitive_masks_value():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)

    with patch("app.routers.admin.set_setting", new_callable=AsyncMock) as mock_set:
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.put(
                    "/api/admin/settings/telegram_bot_token",
                    json={"value": "secret_token", "is_sensitive": True},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_set.assert_called_once_with(db, "telegram_bot_token", "secret_token", True)
    data = resp.json()
    assert data["value"] == "***"
    assert data["is_sensitive"] is True
```

- [ ] **Step 2: Run new tests — expect failures**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py::test_admin_settings_list_masks_sensitive -v 2>&1 | head -15`
Expected: FAILED (404)

- [ ] **Step 3: Append settings endpoints to admin.py**

In the existing `from app.services.setting_service import get_setting, get_setting_decrypted` line, add `set_setting`:
```python
from app.services.setting_service import get_setting, get_setting_decrypted, set_setting
```

Add to the schemas import:
```python
from app.models.setting import Setting
from app.schemas.admin import SettingAdminItem, SettingUpsertRequest  # add to existing import
```

Append to the router:

```python

# --- Admin Settings ---

@router.get("/settings", response_model=list[SettingAdminItem])
async def admin_list_settings(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SettingAdminItem]:
    result = await db.execute(select(Setting).order_by(Setting.key.asc()))
    settings_list = result.scalars().all()
    return [
        SettingAdminItem(
            key=s.key,
            value="***" if s.is_sensitive else (s.value.get("value") or ""),
            is_sensitive=s.is_sensitive,
            updated_at=s.updated_at,
        )
        for s in settings_list
    ]


@router.put("/settings/{key}", response_model=SettingAdminItem)
async def admin_upsert_setting(
    key: str,
    data: SettingUpsertRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SettingAdminItem:
    from datetime import datetime, timezone
    await set_setting(db, key, data.value, data.is_sensitive)
    return SettingAdminItem(
        key=key,
        value="***" if data.is_sensitive else data.value,
        is_sensitive=data.is_sensitive,
        updated_at=datetime.now(tz=timezone.utc),
    )
```

- [ ] **Step 4: Run settings tests — expect 4 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_admin.py -k "settings" -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 4 passed

- [ ] **Step 5: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 154 passed

- [ ] **Step 6: Commit**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/routers/admin.py tests/routers/test_admin.py
git commit -m "feat: add admin settings list and upsert endpoints"
```

---

## Task 6: Support Message Model, Migration, Persist, Admin List

**Files:**
- Create: `backend/app/models/support_message.py`
- Modify: `backend/app/models/__init__.py` (register model for Alembic)
- Create: `backend/alembic/versions/<rev>_add_support_messages.py`
- Modify: `backend/app/routers/support.py` (persist to DB)
- Modify: `backend/app/routers/admin.py` (append support-messages list endpoint)
- Modify: `backend/tests/routers/test_support.py` (add persist test)
- Modify: `backend/tests/routers/test_admin.py` (append support messages list tests)

### Context
- `SupportMessage`: `id` (UUID PK), `user_id` (UUID FK → users.id CASCADE), `display_name` (String 255, denormalized at write time), `message` (Text), `created_at` (server_default now())
- Persist in `POST /api/support/message`: wrap in `try/except Exception` — log warning on failure, never raise
- `GET /api/admin/support-messages?skip=0&limit=50` — ordered by `created_at desc`
- Alembic discovers models via `app/models/__init__.py` which is imported by `alembic/env.py`

- [ ] **Step 1: Create SupportMessage model**

```python
# backend/app/models/support_message.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    display_name: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Register in models/__init__.py**

Add to `backend/app/models/__init__.py`:
```python
from app.models.support_message import SupportMessage
```
Add `"SupportMessage"` to the `__all__` list.

- [ ] **Step 3: Verify import**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run python -c "from app.models.support_message import SupportMessage; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Create Alembic migration**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run alembic revision --autogenerate -m "add_support_messages" 2>&1 | tail -5`

The generated file is in `alembic/versions/`. Open it and confirm the `upgrade` function contains `create_table('support_messages', ...)` with the four columns and the FK to `users.id`. If autogenerate produced different or extra code, adjust to match the pattern from `e7cbe1ed933e_initial_schema.py`. The `downgrade` function should drop the table.

- [ ] **Step 5: Commit model + migration**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/models/support_message.py app/models/__init__.py alembic/versions/
git commit -m "feat: add SupportMessage model and migration"
```

- [ ] **Step 6: Write failing tests**

Append to `backend/tests/routers/test_support.py`:

```python
from app.models.support_message import SupportMessage


@pytest.mark.asyncio
async def test_support_message_persists_to_db():
    """After posting a support message, a SupportMessage row is added to the DB."""
    user = _make_user()
    redis = AsyncMock(spec=Redis)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_redis] = _override_redis(redis)

    with patch("app.routers.support.get_setting", return_value="chat_id"), \
         patch("app.routers.support.get_setting_decrypted", return_value="token"), \
         patch("app.routers.support.send_admin_alert", new_callable=AsyncMock):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post("/api/support/message", json={"message": "Нужна помощь"})
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    db.add.assert_called_once()
    added_obj = db.add.call_args[0][0]
    assert isinstance(added_obj, SupportMessage)
    assert added_obj.message == "Нужна помощь"
    assert added_obj.display_name == user.display_name
```

Append to `backend/tests/routers/test_admin.py`:

```python
from app.models.support_message import SupportMessage as SupportMessageModel


# --- GET /api/admin/support-messages ---

@pytest.mark.asyncio
async def test_admin_support_messages_list_returns_items():
    admin = _make_admin()
    db = AsyncMock(spec=AsyncSession)

    msg = MagicMock(spec=SupportMessageModel)
    msg.id = uuid.uuid4()
    msg.user_id = uuid.uuid4()
    msg.display_name = "Иван"
    msg.message = "Нужна помощь"
    msg.created_at = NOW

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [msg]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[require_admin] = _override_admin(admin)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/support-messages")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Иван"
    assert data[0]["message"] == "Нужна помощь"


@pytest.mark.asyncio
async def test_admin_support_messages_not_admin_returns_403():
    from fastapi import HTTPException

    def _not_admin():
        raise HTTPException(status_code=403, detail="Admin required")

    app.dependency_overrides[require_admin] = _not_admin
    app.dependency_overrides[get_db] = _override_db(AsyncMock(spec=AsyncSession))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/api/admin/support-messages")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403
```

- [ ] **Step 7: Run new tests — expect failures**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_support.py::test_support_message_persists_to_db tests/routers/test_admin.py::test_admin_support_messages_list_returns_items -v 2>&1 | head -20`
Expected: FAILED

- [ ] **Step 8: Update support.py to persist to DB**

In `backend/app/routers/support.py`, add import at top:
```python
from app.models.support_message import SupportMessage
```

In the `send_support_message` handler, after the rate limit check and before reading Telegram config, add:

```python
    # Persist message to DB (best-effort)
    try:
        db.add(SupportMessage(
            user_id=current_user.id,
            display_name=current_user.display_name,
            message=data.message,
        ))
        await db.commit()
    except Exception:
        logger.warning("Failed to persist support message for user %s", current_user.id)
```

Full updated handler (replace the body after the rate limit block):

```python
    # Persist message to DB (best-effort)
    try:
        db.add(SupportMessage(
            user_id=current_user.id,
            display_name=current_user.display_name,
            message=data.message,
        ))
        await db.commit()
    except Exception:
        logger.warning("Failed to persist support message for user %s", current_user.id)

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

- [ ] **Step 9: Append support-messages endpoint to admin.py**

Add to imports in `backend/app/routers/admin.py`:
```python
from app.models.support_message import SupportMessage
from app.schemas.admin import SupportMessageAdminItem  # add to existing import
```

Append to the router:

```python

# --- Admin Support Messages ---

@router.get("/support-messages", response_model=list[SupportMessageAdminItem])
async def admin_list_support_messages(
    skip: int = 0,
    limit: int = 50,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SupportMessageAdminItem]:
    result = await db.execute(
        select(SupportMessage)
        .order_by(SupportMessage.created_at.desc())
        .offset(skip)
        .limit(min(limit, 200))
    )
    messages = result.scalars().all()
    return [SupportMessageAdminItem.model_validate(m) for m in messages]
```

- [ ] **Step 10: Run all new tests — expect 3 passed**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest tests/routers/test_support.py::test_support_message_persists_to_db tests/routers/test_admin.py::test_admin_support_messages_list_returns_items tests/routers/test_admin.py::test_admin_support_messages_not_admin_returns_403 -v 2>&1 | grep -E "PASSED|FAILED|ERROR|passed|failed"`
Expected: 3 passed

- [ ] **Step 11: Full suite — no regressions**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest --tb=short -q 2>&1 | tail -3`
Expected: 158 passed

- [ ] **Step 12: Commit + tag**

```bash
cd E:/Projects/vpn/custom_sub_pages/backend
git add app/models/support_message.py app/models/__init__.py alembic/versions/ \
        app/routers/support.py app/routers/admin.py \
        tests/routers/test_support.py tests/routers/test_admin.py
git commit -m "feat: add support message persistence and admin support-messages endpoint"
git tag plan-7-complete
```

---

## Final Verification

- [ ] **Run full suite**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run pytest -v 2>&1 | tail -10`
Expected: 158 passed, 0 failed

- [ ] **Verify all new admin endpoints registered**

Run: `cd E:/Projects/vpn/custom_sub_pages/backend && uv run python -c "from app.main import app; routes = [r.path for r in app.routes]; [print(r) for r in routes if 'admin' in r]"`

Expected output includes:
```
/api/admin/users
/api/admin/users/{user_id}
/api/admin/users/{user_id}/sync
/api/admin/users/{user_id}/resolve-conflict
/api/admin/sync/all
/api/admin/sync/status/{task_id}
/api/admin/plans
/api/admin/plans/{plan_id}
/api/admin/promo-codes
/api/admin/promo-codes/{code_id}/toggle
/api/admin/promo-codes/{code_id}
/api/admin/articles
/api/admin/articles/{article_id}
/api/admin/articles/{article_id}/publish
/api/admin/articles/{article_id}/unpublish
/api/admin/settings
/api/admin/settings/{key}
/api/admin/support-messages
```
