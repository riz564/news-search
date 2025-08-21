from __future__ import annotations
from typing import List, Dict
from newssearch.providers.guardian import GuardianProvider
from newssearch.providers.nyt import NYTProvider
from newssearch.utils.cache import Cache
from newssearch.utils.strategies import DedupeStrategy, SortStrategy
from newssearch.utils.logging_setup import configure_logging_from_env

logger = configure_logging_from_env(__name__)

class Aggregator:
    def __init__(
        self,
        providers: List,           # List[NewsProvider]
        cache: Cache,
        dedupe: DedupeStrategy,
        sorter: SortStrategy,
        cache_ttl: int,
    ):
        self._providers = providers
        self._cache = cache
        self._dedupe = dedupe
        self._sorter = sorter
        self._ttl = cache_ttl

    def aggregate(self, query: str, page: int, page_size: int, offline: bool) -> dict:
        key = f"agg:{query}:{page}:{page_size}:{offline}"
        cached = self._cache.get_json(key)
        if cached:
            return cached

        # Run providers sequentially to keep it simple & predictable;
        # swap to threads if needed — but keep that detail inside this class.
        results, totals = [], []
        for p in self._providers:
            try:
                data = p.fetch(query, page, page_size, offline)
                if data and "items" in data and "total" in data:
                    results.extend(data["items"])
                    totals.append(data["total"])
            except Exception as e:
                logger.error("provider_fail name=%s err=%s", p.__class__.__name__, e, exc_info=True)

        items = self._dedupe.dedupe(results)
        items = self._sorter.sort(items)

        sum_total = sum(totals) if totals else len(items)
        total_pages = max(1, (sum_total + page_size - 1) // page_size)

        start = (page - 1) * page_size
        end = start + page_size
        out = {"items": items[start:end], "total_estimated_pages": total_pages}

        self._cache.set_json(key, out, self._ttl)
        return out
