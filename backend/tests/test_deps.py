import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status
from app.deps import get_current_user


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
