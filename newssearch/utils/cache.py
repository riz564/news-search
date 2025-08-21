from __future__ import annotations
import json
import redis
from typing import Protocol, Optional
from newssearch.utils.logging_setup import configure_logging_from_env

logger = configure_logging_from_env(__name__)

class Cache(Protocol):
    def get_json(self, key: str) -> Optional[dict]: ...
    def set_json(self, key: str, value: dict, ttl: int) -> None: ...

class RedisCache(Cache):
    def __init__(self, host: str, port: int, db: int):
        self._client = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)

    def get_json(self, key: str) -> Optional[dict]:
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error("cache_read_fail key=%s err=%s", key, e, exc_info=True)
            return None

    def set_json(self, key: str, value: dict, ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error("cache_store_fail key=%s err=%s", key, e, exc_info=True)
