import json
import os
import redis

_client: redis.Redis | None = None

CACHE_TTL = int(os.getenv("FF_CACHE_TTL_SECONDS", 3300))


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "aurum-redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return _client


def cache_get(key: str) -> list | None:
    raw = _get_client().get(key)
    if raw:
        return json.loads(raw)
    return None


def cache_set(key: str, data: list, ttl: int = CACHE_TTL) -> None:
    _get_client().setex(key, ttl, json.dumps(data))
