import json
import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "aurum-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
MAX_MEMORIES = 10

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _client


def store_memory(agent_name: str, content: str, session_id: str) -> None:
    try:
        r = _get_client()
        key = f"mem:{agent_name}"
        entry = json.dumps({"content": content, "session": session_id})
        r.lpush(key, entry)
        r.ltrim(key, 0, MAX_MEMORIES - 1)
        r.expire(key, 86400)  # 24h TTL
    except Exception:
        pass


def get_memories(agent_name: str, query: str) -> list[str]:
    try:
        r = _get_client()
        key = f"mem:{agent_name}"
        raw_list = r.lrange(key, 0, MAX_MEMORIES - 1)
        return [json.loads(item).get("content", "") for item in raw_list]
    except Exception:
        return []
