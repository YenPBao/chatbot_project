from typing import Any
from app.core.config import settings

try:
    # redis.asyncio may not have type stubs in the analysis environment; allow import at runtime
    from redis.asyncio import Redis  # type: ignore[import]
except Exception:  # pragma: no cover
    Redis = Any  # type: ignore

# Connect to Redis
rds: Redis = Redis(
    host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
)
