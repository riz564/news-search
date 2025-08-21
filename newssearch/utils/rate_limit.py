import time
import redis
from newssearch.utils.logging_setup import configure_logging_from_env

logger = configure_logging_from_env(__name__)

class RateLimiter:
    """
    Simple Redis-backed token bucket rate limiter.
    """
    def __init__(self, client: redis.StrictRedis, key_prefix: str, rate: int, per_seconds: int):
        """
        :param client: Redis connection
        :param key_prefix: unique key prefix (eg. "ingress:ip" or "egress:nyt")
        :param rate: number of allowed requests
        :param per_seconds: time window in seconds
        """
        self.client = client
        self.key_prefix = key_prefix
        self.rate = rate
        self.per_seconds = per_seconds

    def allow(self, identity: str) -> bool:
        """
        :param identity: per-user / per-IP identifier
        :return: True if allowed, False if limited
        """
        key = f"rl:{self.key_prefix}:{identity}"
        now = int(time.time())
        p = self.client.pipeline()
        p.incr(key, 1)
        p.expire(key, self.per_seconds)
        count, _ = p.execute()
        if count > self.rate:
            logger.error("rate_limit_exceeded key=%s count=%d", key, count)
            return False
        return True
