# backend/app/routers/admin.py
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select, cast, or_, exists, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.deps import require_admin
from app.models.article import Article
from app.models.auth_provider import AuthProvider
from app.models.plan import Plan
from app.models.promo_code import PromoCode, PromoCodeType
from app.models.setting import Setting
from app.models.support_message import SupportMessage
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.transaction import Transaction
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.admin import (
    ArticleAdminDetail,
    ArticleAdminListItem,
    ArticleCreateRequest,
    ArticleUpdateRequest,
    ConflictResolveRequest,
    PlanAdminItem,
    PlanCreateRequest,
    PlanUpdateRequest,
    PromoCodeAdminItem,
    PromoCodeCreateRequest,
    ProviderInfo,
    SettingAdminItem,
    SettingUpsertRequest,
    SubscriptionAdminInfo,
    SupportMessageAdminItem,
    SyncStatusResponse,
    TransactionAdminItem,
    UserAdminDetail,
    UserAdminListItem,
)
from app.services.admin_sync_service import run_sync_all
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted, set_setting
from app.services.subscription_service import sync_subscription_from_remnawave

router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.get("/users", response_model=list[UserAdminListItem])
async def list_users(
    q: str | None = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: Literal["created_at", "last_seen_at", "display_name"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserAdminListItem]:
    sort_map = {
        "created_at": User.created_at,
        "last_seen_at": User.last_seen_at,
        "display_name": User.display_name,
    }
    sort_col = sort_map[sort_by]
    stmt = (
        select(User)
        .options(selectinload(User.auth_providers), selectinload(User.subscription))
    )
    if q:
        q_norm = q.lstrip('#').lower()
        email_exists = exists().where(
            (AuthProvider.user_id == User.id)
            & AuthProvider.provider_user_id.ilike(f"%{q}%")
        )
        stmt = stmt.where(
            or_(
                User.display_name.ilike(f"%{q}%"),
                cast(User.id, String).ilike(f"{q_norm}%"),
                cast(User.remnawave_uuid, String).ilike(f"%{q_norm}%"),
                email_exists,
            )
        )
    if order == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())
    stmt = stmt.offset(skip).limit(min(limit, 200))
    result = await db.execute(stmt)
    users = result.scalars().unique().all()
    return [_build_list_item(u) for u in users]


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


@router.get("/users/{user_id}", response_model=UserAdminDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminDetail:
    return await _build_user_detail(user_id, db)


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
    sub.status = SubscriptionStatus.expired
    sub.expires_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/sync")
async def sync_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if user.remnawave_uuid is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="У пользователя нет Remnawave UUID")

    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Remnawave не настроен")

    rw_client = RemnawaveClient(url, token)
    try:
        rw_user = await rw_client.get_user(str(user.remnawave_uuid))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ошибка связи с Remnawave")

    await sync_subscription_from_remnawave(db, user, rw_user)
    return {"ok": True}


@router.post("/users/{user_id}/resolve-conflict")
async def resolve_conflict(
    user_id: uuid.UUID,
    data: ConflictResolveRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        new_rw_uuid = uuid.UUID(data.remnawave_uuid)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный UUID")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    user.remnawave_uuid = new_rw_uuid
    user.subscription_conflict = False
    await db.commit()

    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if url and token:
        try:
            rw_user = await RemnawaveClient(url, token).get_user(str(new_rw_uuid))
            await sync_subscription_from_remnawave(db, user, rw_user)
        except Exception:
            pass  # Conflict cleared; sync failure is non-critical

    return {"ok": True}


@router.post("/sync/all", status_code=201)
async def sync_all_users(
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    task_id = str(uuid.uuid4())
    await redis.set(
        f"sync:{task_id}",
        json.dumps({"status": "running", "total": 0, "done": 0, "errors": 0}),
        ex=3600,
    )
    background_tasks.add_task(run_sync_all, task_id, redis)
    return {"task_id": task_id}


@router.get("/sync/status/{task_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    task_id: str,
    admin: User = Depends(require_admin),
    redis: Redis = Depends(get_redis),
) -> SyncStatusResponse:
    raw = await redis.get(f"sync:{task_id}")
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    data = json.loads(raw)
    return SyncStatusResponse(**data)


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
    if 'preview_image_url' in data.model_fields_set:
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
    await set_setting(db, key, data.value, data.is_sensitive)
    return SettingAdminItem(
        key=key,
        value="***" if data.is_sensitive else data.value,
        is_sensitive=data.is_sensitive,
        updated_at=datetime.now(tz=timezone.utc),
    )


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
