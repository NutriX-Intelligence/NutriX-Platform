import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("shared.redis")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
if "@redis:" in REDIS_URL or REDIS_URL.startswith("redis://redis:"):
    REDIS_URL = REDIS_URL.replace("redis://redis:", "redis://localhost:", 1)

_redis_client = None
_in_memory_cache: Dict[str, Any] = {}
_is_fallback_mode = False

def get_redis_client():
    global _redis_client, _is_fallback_mode
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        _is_fallback_mode = False
        logger.info(f"Connected to Redis at {REDIS_URL}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed ({e}). Falling back to in-memory cache.")
        _is_fallback_mode = True
        return None

def get_daily_macros(user_id: int, date_str: str) -> Optional[Dict[str, Any]]:
    client = get_redis_client()
    key = f"user:{user_id}:macros:{date_str}"
    if client:
        try:
            val = client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.error(f"Error reading macros from Redis key {key}: {e}")
            return None
    return _in_memory_cache.get(key)

def set_daily_macros(user_id: int, date_str: str, macros: Dict[str, Any], ttl_seconds: int = 86400) -> bool:
    client = get_redis_client()
    key = f"user:{user_id}:macros:{date_str}"
    data_str = json.dumps(macros)
    if client:
        try:
            client.setex(key, ttl_seconds, data_str)
            return True
        except Exception as e:
            logger.error(f"Error writing macros to Redis key {key}: {e}")
            return False
    _in_memory_cache[key] = macros
    return True

def invalidate_daily_macros(user_id: int, date_str: str) -> bool:
    client = get_redis_client()
    key = f"user:{user_id}:macros:{date_str}"
    if client:
        try:
            client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error invalidating Redis key {key}: {e}")
            return False
    _in_memory_cache.pop(key, None)
    return True

def publish_event(channel: str, message: Dict[str, Any]) -> bool:
    client = get_redis_client()
    msg_str = json.dumps(message)
    if client:
        try:
            client.publish(channel, msg_str)
            return True
        except Exception as e:
            logger.error(f"Error publishing to Redis channel {channel}: {e}")
            return False
    logger.info(f"[In-Memory Mode] Event published to {channel}: {msg_str}")
    return True
