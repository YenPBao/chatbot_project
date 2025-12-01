from redis.asyncio import Redis
from app.core.config import settings
# Connect to Redis

rds = Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db)