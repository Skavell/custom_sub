import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status
from httpx import AsyncClient, ASGITransport
from app.deps import get_current_user
from app.services.auth.jwt_service import create_access_token, create_refresh_token
from app.models.user import User


@pytest.mark.asyncio
async def test_get_current_user_no_cookie_raises():
    request = MagicMock(spec=Request)
    request.cookies = {}
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=request, db=AsyncMock(), redis=AsyncMock())
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises():
    request = MagicMock(spec=Request)
    request.cookies = {"access_token": "not.a.valid.token"}
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=request, db=AsyncMock(), redis=AsyncMock())
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


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
    assert exc_info.value.detail == "Аккаунт заблокирован"


@pytest.mark.asyncio
async def test_refresh_endpoint_banned_user_returns_403():
    """POST /api/auth/refresh returns 403 when the user is banned."""
    from app.main import app
    from app.database import get_db
    from app.redis_client import get_redis

    banned_user = MagicMock(spec=User)
    banned_user.id = uuid.uuid4()
    banned_user.is_banned = True

    refresh_token, jti = create_refresh_token(str(banned_user.id))

    # Redis mock: refresh jti exists (token is valid/not revoked)
    redis_mock = AsyncMock()
    redis_mock.exists = AsyncMock(return_value=1)
    redis_mock.delete = AsyncMock()

    # DB mock: returns banned user
    db_mock = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = banned_user
    db_mock.execute = AsyncMock(return_value=result_mock)

    async def _override_db():
        yield db_mock

    async def _override_redis():
        return redis_mock

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/refresh",
                cookies={"refresh_token": refresh_token},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["detail"] == "Аккаунт заблокирован"
