import os
import redis

_redis_client = None


def get_redis_client() -> redis.Redis:
    """
    Returns a singleton Redis client instance.
    Decodes responses as strings for easier consumption.
    """
    global _redis_client
    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        db = int(os.getenv("REDIS_DB", 0))
        _redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_timeout=5.0,  # Safe timeout for fallback detection
        )
    return _redis_client
