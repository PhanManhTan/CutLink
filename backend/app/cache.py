import json
import logging

from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)
cache = Redis.from_url(
    get_settings().redis_url,
    socket_connect_timeout=0.15,
    socket_timeout=0.15,
    retry_on_timeout=False,
    decode_responses=True,
)
CACHE_TTL = 30


def key(code: str) -> str:
    return f"link:{code}"


def read_link(code: str) -> dict | None:
    try:
        value = cache.get(key(code))
        return json.loads(value) if value else None
    except (RedisError, ValueError):
        logger.warning("Redirect cache unavailable", exc_info=True)
        return None


def cache_link(code: str, link_id: str, target_url: str) -> None:
    try:
        cache.setex(key(code), CACHE_TTL, json.dumps({"id": link_id, "url": target_url}))
    except RedisError:
        logger.warning("Cannot populate redirect cache", exc_info=True)


def invalidate(code: str) -> None:
    try:
        cache.delete(key(code))
    except RedisError:
        logger.warning("Cannot invalidate %s; expires within %ss", code, CACHE_TTL, exc_info=True)
