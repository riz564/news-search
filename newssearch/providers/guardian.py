import os
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from tenacity import retry, stop_after_attempt, wait_fixed, RetryError
import pybreaker

from newssearch.providers.base import NewsProvider
from newssearch.config import GUARDIAN_KEY
from newssearch.utils.circuit_breaker import guardian_breaker
from newssearch.utils.validation import normalize_guardian
from newssearch.utils.logging_setup import configure_logging_from_env

logger = configure_logging_from_env(__name__)

class GuardianProvider(NewsProvider):
    def __init__(
        self,
        api_key: Optional[str] = GUARDIAN_KEY,
        breaker: pybreaker.CircuitBreaker = guardian_breaker,
        egress_limiter: Optional[object] = None,  # duck-typed limiter: needs .allow(str)->bool
    ):
        self.api_key = api_key
        self.breaker = breaker
        self.egress_limiter = egress_limiter
        logger.debug("GuardianProvider initialized | api_key_present=%s", bool(api_key))

    def _check_egress_limit(self) -> None:
        lim = self.egress_limiter
        if lim and hasattr(lim, "allow") and not lim.allow("guardian"):
            raise Exception("Guardian egress rate limit exceeded")

    def _load_offline(self) -> Dict[str, Any]:
        # try several locations so tests/dev don’t break on cwd
        candidates = [
            Path("data/guardian_offline.json"),
            Path("guardian_offline.json"),
            Path(__file__).resolve().parent.parent / "data" / "guardian_offline.json",
        ]
        for p in candidates:
            try:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        logger.debug("Loaded offline Guardian data from %s", p)
                        return data
            except Exception as e:
                logger.error("offline_load_fail path=%s err=%s", p, e, exc_info=True)
        raise FileNotFoundError(f"guardian_offline.json not found in: {', '.join(map(str, candidates))}")

    def _fetch_guardian_api(self, url: str) -> Dict[str, Any]:
        self._check_egress_limit()
        logger.info("Guardian API request: %s", url)
        with urllib.request.urlopen(url, timeout=6) as r:
            raw = r.read().decode("utf-8")
            logger.debug("Guardian API response bytes=%d", len(raw))
            return json.loads(raw)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def fetch(self, query: str, page: int, page_size: int, offline: bool):
        logger.info("Fetch start | query=%r, page=%s, page_size=%s, offline=%s", query, page, page_size, offline)

        if offline or not self.api_key:
            data = self._load_offline()
        else:
            params = {
                "api-key": self.api_key,
                "q": query,
                "page": page,
                "page-size": page_size,
                "show-fields": "trailText",
            }
            url = "https://content.guardianapis.com/search?" + urllib.parse.urlencode(params)
            logger.debug("Constructed Guardian API URL: %s", url)
            try:
                data = self.breaker.call(self._fetch_guardian_api, url)
                logger.info("Guardian API call succeeded.")
            except (pybreaker.CircuitBreakerError, RetryError, Exception) as e:
                logger.error("Guardian upstream error: %s. Falling back to offline.", e, exc_info=True)
                data = self._load_offline()

        normalized = normalize_guardian(data) or {"items": [], "total": 0}
        return normalized
