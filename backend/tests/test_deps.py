import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status
from app.deps import get_current_user
from app.services.auth.jwt_service import create_access_token
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
    assert "заблокирован" in exc_info.value.detail.lower()
