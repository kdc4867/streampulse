import os

try:
    import redis
except Exception:
    redis = None

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

def get_redis_client():
    if not redis:
        return None
    try:
        return redis.Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        return None
