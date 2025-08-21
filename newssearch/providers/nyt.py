import os
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from tenacity import retry, stop_after_attempt, wait_fixed
import pybreaker

from newssearch.providers.base import NewsProvider
from newssearch.config import NYT_KEY
from newssearch.utils.circuit_breaker import nyt_breaker
from newssearch.utils.validation import normalize_nyt
from newssearch.utils.logging_setup import configure_logging_from_env

logger = configure_logging_from_env(__name__)

class NYTProvider(NewsProvider):
    def __init__(
        self,
        api_key: Optional[str] = NYT_KEY,
        breaker: pybreaker.CircuitBreaker = nyt_breaker,
        egress_limiter: Optional[object] = None,  # duck-typed limiter: .allow(str)->bool
    ):
        self.api_key = api_key
        self.breaker = breaker
        self.egress_limiter = egress_limiter
        logger.debug("NYTProvider initialized | api_key_present=%s", bool(api_key))

    def _check_egress_limit(self) -> None:
        lim = self.egress_limiter
        if lim and hasattr(lim, "allow") and not lim.allow("nyt"):
            raise Exception("NYT egress rate limit exceeded")

    def _load_offline(self) -> Dict[str, Any]:
        candidates = [
            Path("data/nyt_offline.json"),
            Path("nyt_offline.json"),
            Path(__file__).resolve().parent.parent / "data" / "nyt_offline.json",
        ]
        for p in candidates:
            try:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        logger.debug("Loaded offline NYT data from %s", p)
                        return data
            except Exception as e:
                logger.error("offline_load_fail path=%s err=%s", p, e, exc_info=True)
        raise FileNotFoundError(f"nyt_offline.json not found in: {', '.join(map(str, candidates))}")

    def _fetch_nyt_api(self, url: str) -> Dict[str, Any]:
        self._check_egress_limit()
        logger.info("NYT API request: %s", url)
        with urllib.request.urlopen(url, timeout=6) as r:
            raw = r.read().decode("utf-8")
            logger.debug("NYT API response bytes=%d", len(raw))
            return json.loads(raw)

    # <<< Key change: retry the upstream call itself, and reraise on failure >>>
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0), reraise=True)
    def _call_nyt(self, url: str) -> Dict[str, Any]:
        return self.breaker.call(self._fetch_nyt_api, url)

    def fetch(self, query: str, page: int, page_size: int, offline: bool):
        logger.info("Fetch start | query=%r, page=%s, page_size=%s, offline=%s", query, page, page_size, offline)

        if offline or not self.api_key:
            data = self._load_offline()
        else:
            params = {"q": query, "page": max(0, page - 1), "api-key": self.api_key}
            url = "https://api.nytimes.com/svc/search/v2/articlesearch.json?" + urllib.parse.urlencode(params)
            logger.debug("Constructed NYT API URL: %s", url)
            try:
                data = self._call_nyt(url)
                logger.info("NYT API call succeeded.")
            except Exception as e:
                logger.error("NYT upstream error: %s. Falling back to offline.", e, exc_info=True)
                data = self._load_offline()

        normalized = normalize_nyt(data, page_size) or {"items": [], "total": 0}
        return normalized
