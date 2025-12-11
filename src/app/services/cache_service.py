import json
from app.core.redis_client import rds  # async Redis client

CONV_LIST_TTL = 600


def conv_list_key(user_id: str, offset: int, limit: int, order: str) -> str:
    return f"user:{user_id}:conversation_list:{offset}:{limit}:{order}"


async def get_cached_conversation_list(
    user_id: str, offset: int, limit: int, order: str
) -> dict | None:
    key = conv_list_key(user_id, offset, limit, order)
    data = await rds.get(key)
    return json.loads(data) if data else None


async def cache_conversation_list(
    user_id: str, offset: int, limit: int, order: str, payload: dict
):
    key = conv_list_key(user_id, offset, limit, order)
    await rds.set(key, json.dumps(payload), ex=CONV_LIST_TTL)


async def invalidate_conversation_list_cache(user_id: str):
    pattern = f"user:{user_id}:conversation_list:*"
    async for k in rds.scan_iter(match=pattern):
        await rds.delete(k)
