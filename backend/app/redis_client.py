from redis.asyncio import Redis
from app.config import settings

# Initialized at module load — safe for asyncio (no race condition)
redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> Redis:
    return redis
