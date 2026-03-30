# backend/app/services/admin_sync_service.py
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.subscription_service import sync_subscription_from_remnawave

logger = logging.getLogger(__name__)

_BATCH_TIMEOUT = 600   # 10 minutes total
_PER_USER_TIMEOUT = 10  # seconds per user
_REDIS_TTL = 3600       # 1 hour


async def run_sync_all(task_id: str, redis: Redis) -> None:
    """Background task: sync all Remnawave users.
    Creates its own DB session — must NOT receive the request session.
    Stores progress in Redis as JSON under key sync:{task_id}.
    """
    async with AsyncSessionLocal() as db:
        url = await get_setting(db, "remnawave_url")
        token = await get_setting_decrypted(db, "remnawave_token")

        if not url or not token:
            await redis.set(
                f"sync:{task_id}",
                json.dumps({"status": "failed", "total": 0, "done": 0, "errors": 0}),
                ex=_REDIS_TTL,
            )
            return

        result = await db.execute(select(User).where(User.remnawave_uuid.is_not(None)))
        users = result.scalars().all()
        total = len(users)
        done = 0
        errors = 0

        await redis.set(
            f"sync:{task_id}",
            json.dumps({"status": "running", "total": total, "done": 0, "errors": 0}),
            ex=_REDIS_TTL,
        )

        rw_client = RemnawaveClient(url, token)
        start_time = datetime.now(tz=timezone.utc)

        for user in users:
            elapsed = (datetime.now(tz=timezone.utc) - start_time).total_seconds()
            if elapsed > _BATCH_TIMEOUT:
                await redis.set(
                    f"sync:{task_id}",
                    json.dumps({"status": "timed_out", "total": total, "done": done, "errors": errors}),
                    ex=_REDIS_TTL,
                )
                return

            try:
                async with asyncio.timeout(_PER_USER_TIMEOUT):
                    rw_user = await rw_client.get_user(str(user.remnawave_uuid))
                    await sync_subscription_from_remnawave(db, user, rw_user)
                done += 1
            except Exception as exc:
                logger.warning("Sync failed for user %s: %s", user.remnawave_uuid, exc)
                errors += 1

            await redis.set(
                f"sync:{task_id}",
                json.dumps({"status": "running", "total": total, "done": done, "errors": errors}),
                ex=_REDIS_TTL,
            )

        await redis.set(
            f"sync:{task_id}",
            json.dumps({"status": "completed", "total": total, "done": done, "errors": errors}),
            ex=_REDIS_TTL,
        )
