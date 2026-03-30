# backend/tests/services/test_admin_sync_service.py
import asyncio
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


def _make_redis():
    r = AsyncMock(spec=Redis)
    r.set = AsyncMock()
    return r


def _make_db(users=None):
    """Mock AsyncSessionLocal context manager."""
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = users or []
    db.execute = AsyncMock(return_value=result)
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.mark.asyncio
async def test_sync_all_no_rw_config_sets_failed_status():
    from app.services.admin_sync_service import run_sync_all

    task_id = str(uuid.uuid4())
    redis = _make_redis()
    mock_db = _make_db()

    with patch("app.services.admin_sync_service.AsyncSessionLocal", return_value=mock_db), \
         patch("app.services.admin_sync_service.get_setting", return_value=None), \
         patch("app.services.admin_sync_service.get_setting_decrypted", return_value=None):
        await run_sync_all(task_id, redis)

    # Verify final Redis set called with failed status
    last_call = redis.set.call_args_list[-1]
    stored = json.loads(last_call[0][1])
    assert stored["status"] == "failed"


@pytest.mark.asyncio
async def test_sync_all_success_sets_completed_status():
    from app.services.admin_sync_service import run_sync_all

    task_id = str(uuid.uuid4())
    redis = _make_redis()

    user1 = MagicMock()
    user1.remnawave_uuid = uuid.uuid4()
    user2 = MagicMock()
    user2.remnawave_uuid = uuid.uuid4()
    mock_db = _make_db(users=[user1, user2])

    rw_user = MagicMock()

    with patch("app.services.admin_sync_service.AsyncSessionLocal", return_value=mock_db), \
         patch("app.services.admin_sync_service.get_setting", return_value="http://rw"), \
         patch("app.services.admin_sync_service.get_setting_decrypted", return_value="token"), \
         patch("app.services.admin_sync_service.RemnawaveClient") as mock_rw_cls, \
         patch("app.services.admin_sync_service.sync_subscription_from_remnawave", new_callable=AsyncMock):
        mock_rw_cls.return_value.get_user = AsyncMock(return_value=rw_user)
        await run_sync_all(task_id, redis)

    last_call = redis.set.call_args_list[-1]
    stored = json.loads(last_call[0][1])
    assert stored["status"] == "completed"
    assert stored["done"] == 2
    assert stored["errors"] == 0


@pytest.mark.asyncio
async def test_sync_all_per_user_error_counted_and_continues():
    from app.services.admin_sync_service import run_sync_all

    task_id = str(uuid.uuid4())
    redis = _make_redis()

    user1 = MagicMock()
    user1.remnawave_uuid = uuid.uuid4()
    user2 = MagicMock()
    user2.remnawave_uuid = uuid.uuid4()
    mock_db = _make_db(users=[user1, user2])

    call_count = [0]
    async def _failing_get_user(uid):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("Remnawave error")
        return MagicMock()

    with patch("app.services.admin_sync_service.AsyncSessionLocal", return_value=mock_db), \
         patch("app.services.admin_sync_service.get_setting", return_value="http://rw"), \
         patch("app.services.admin_sync_service.get_setting_decrypted", return_value="token"), \
         patch("app.services.admin_sync_service.RemnawaveClient") as mock_rw_cls, \
         patch("app.services.admin_sync_service.sync_subscription_from_remnawave", new_callable=AsyncMock):
        mock_rw_cls.return_value.get_user = _failing_get_user
        await run_sync_all(task_id, redis)

    last_call = redis.set.call_args_list[-1]
    stored = json.loads(last_call[0][1])
    assert stored["status"] == "completed"
    assert stored["done"] == 1
    assert stored["errors"] == 1
