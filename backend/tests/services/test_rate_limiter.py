import pytest
from unittest.mock import AsyncMock
from app.services.rate_limiter import check_rate_limit


@pytest.mark.asyncio
async def test_first_request_allowed():
    redis = AsyncMock()
    redis.incr.return_value = 1  # first increment
    result = await check_rate_limit(redis, "rate:trial:1.2.3.4", limit=3, window_seconds=86400)
    assert result is True
    redis.expire.assert_awaited_once_with("rate:trial:1.2.3.4", 86400)


@pytest.mark.asyncio
async def test_at_limit_allowed():
    redis = AsyncMock()
    redis.incr.return_value = 3  # exactly at limit
    result = await check_rate_limit(redis, "rate:trial:1.2.3.4", limit=3, window_seconds=86400)
    assert result is True
    # expire must NOT be called for any count > 1 (TTL is set only on first increment)
    redis.expire.assert_not_awaited()


@pytest.mark.asyncio
async def test_over_limit_blocked():
    redis = AsyncMock()
    redis.incr.return_value = 4  # one over limit
    result = await check_rate_limit(redis, "rate:trial:1.2.3.4", limit=3, window_seconds=86400)
    assert result is False
    # expire should NOT be called when not the first request
    redis.expire.assert_not_awaited()
