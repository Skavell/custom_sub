import pytest
from unittest.mock import AsyncMock, MagicMock
from app.deps import get_current_user
from fastapi import Request


@pytest.mark.asyncio
async def test_get_current_user_no_cookie_raises():
    request = MagicMock(spec=Request)
    request.cookies = {}
    with pytest.raises(Exception):  # HTTPException 401
        await get_current_user(request=request, db=AsyncMock(), redis=AsyncMock())


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises():
    request = MagicMock(spec=Request)
    request.cookies = {"access_token": "not.a.valid.token"}
    with pytest.raises(Exception):
        await get_current_user(request=request, db=AsyncMock(), redis=AsyncMock())
