# backend/app/routers/admin.py
from __future__ import annotations
import json
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_admin
from app.models.auth_provider import AuthProvider
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.admin import (
    ConflictResolveRequest,
    ProviderInfo,
    SubscriptionAdminInfo,
    SyncStatusResponse,
    TransactionAdminItem,
    UserAdminDetail,
    UserAdminListItem,
)
from app.services.admin_sync_service import run_sync_all
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import sync_subscription_from_remnawave

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _build_list_item(u: User) -> UserAdminListItem:
    sub = u.subscription
    return UserAdminListItem(
        id=u.id,
        display_name=u.display_name,
        avatar_url=u.avatar_url,
        is_admin=u.is_admin,
        remnawave_uuid=u.remnawave_uuid,
        has_made_payment=u.has_made_payment,
        subscription_conflict=u.subscription_conflict,
        created_at=u.created_at,
        last_seen_at=u.last_seen_at,
        subscription_status=sub.status.value if sub else None,
        subscription_type=sub.type.value if sub else None,
        subscription_expires_at=sub.expires_at if sub else None,
        providers=[p.provider.value for p in u.auth_providers],
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
        stmt = stmt.where(User.display_name.ilike(f"%{q}%"))
    if order == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())
    stmt = stmt.offset(skip).limit(min(limit, 200))
    result = await db.execute(stmt)
    users = result.scalars().unique().all()
    return [_build_list_item(u) for u in users]


@router.get("/users/{user_id}", response_model=UserAdminDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserAdminDetail:
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

    return UserAdminDetail(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        remnawave_uuid=user.remnawave_uuid,
        has_made_payment=user.has_made_payment,
        subscription_conflict=user.subscription_conflict,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        subscription=SubscriptionAdminInfo.model_validate(user.subscription) if user.subscription else None,
        providers=[ProviderInfo.model_validate(p) for p in user.auth_providers],
        recent_transactions=[TransactionAdminItem.model_validate(tx) for tx in transactions],
    )


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
