import hashlib
import hmac
import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.models.user import User


NOW = datetime.now(tz=timezone.utc)
SECRET = "test-webhook-secret"


def _make_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _make_body(event: str = "user.first_connected", remnawave_uuid: str | None = None) -> bytes:
    rw_uuid = remnawave_uuid or str(uuid.uuid4())
    return json.dumps({
        "event": event,
        "data": {
            "uuid": rw_uuid,
            "userTraffic": {
                "usedTrafficBytes": 1024,
                "lifetimeUsedTrafficBytes": 1024,
                "onlineAt": None,
                "firstConnectedAt": "2026-04-19T10:00:00Z",
            },
        },
    }, separators=(",", ":")).encode()


def _override_db(mock_db):
    async def _dep():
        yield mock_db
    return _dep


@pytest.mark.asyncio
async def test_webhook_missing_secret_returns_401():
    """Returns 401 when remnawave_webhook_secret is not configured."""
    body = _make_body()
    sig = _make_sig(SECRET, body)
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value="")):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401():
    """Returns 401 when signature does not match."""
    body = _make_body()
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": "wrongsignature"},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_unknown_event_returns_200():
    """Returns 200 for unknown events without touching DB."""
    body = json.dumps({"event": "user.expired", "data": {"uuid": str(uuid.uuid4())}},
                      separators=(",", ":")).encode()
    sig = _make_sig(SECRET, body)
    db = AsyncMock(spec=AsyncSession)

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_first_connected_user_not_found_returns_200():
    """Returns 200 and does not crash when no user matches remnawave_uuid."""
    body = _make_body()
    sig = _make_sig(SECRET, body)
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_first_connected_writes_timestamp():
    """Writes first_connected_at from userTraffic.firstConnectedAt when user found."""
    rw_uuid = uuid.uuid4()
    body = _make_body(remnawave_uuid=str(rw_uuid))
    sig = _make_sig(SECRET, body)

    user = MagicMock(spec=User)
    user.first_connected_at = None

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.first_connected_at is not None
    assert user.first_connected_at == datetime(2026, 4, 19, 10, 0, 0, tzinfo=timezone.utc)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_first_connected_skips_if_already_set():
    """Does not overwrite first_connected_at if already set."""
    rw_uuid = uuid.uuid4()
    body = _make_body(remnawave_uuid=str(rw_uuid))
    sig = _make_sig(SECRET, body)

    existing_ts = datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc)
    user = MagicMock(spec=User)
    user.first_connected_at = existing_ts

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.first_connected_at == existing_ts
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_null_first_connected_at_skips_write():
    """Does not write first_connected_at when userTraffic.firstConnectedAt is null."""
    rw_uuid = uuid.uuid4()
    body = json.dumps({
        "event": "user.first_connected",
        "data": {
            "uuid": str(rw_uuid),
            "userTraffic": {
                "usedTrafficBytes": 0,
                "lifetimeUsedTrafficBytes": 0,
                "onlineAt": None,
                "firstConnectedAt": None,
            },
        },
    }, separators=(",", ":")).encode()
    sig = _make_sig(SECRET, body)

    user = MagicMock(spec=User)
    user.first_connected_at = None

    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=user))

    with patch("app.routers.remnawave_webhook.get_setting_decrypted", new=AsyncMock(return_value=SECRET)):
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/webhooks/remnawave",
                    content=body,
                    headers={"X-Remnawave-Signature": sig},
                )
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert user.first_connected_at is None
    db.commit.assert_not_called()
