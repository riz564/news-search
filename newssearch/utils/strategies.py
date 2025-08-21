from __future__ import annotations
from typing import List, Dict, Protocol, Callable
from newssearch.utils.validation import canon

class DedupeStrategy(Protocol):
    def dedupe(self, items: List[Dict]) -> List[Dict]: ...

class SortStrategy(Protocol):
    def sort(self, items: List[Dict]) -> List[Dict]: ...

class CanonUrlDedupe(DedupeStrategy):
    def __init__(self, canon_fn: Callable[[str], str] = canon):
        self._canon = canon_fn

    def dedupe(self, items: List[Dict]) -> List[Dict]:
        seen, out = set(), []
        for it in items:
            u = self._canon((it.get("url") or ""))
            if not u or u in seen:
                continue
            seen.add(u); out.append(it)
        return out

class PublishedAtSort(SortStrategy):
    def __init__(self, desc: bool = True):
        self._desc = desc

    def sort(self, items: List[Dict]) -> List[Dict]:
        return sorted(items, key=lambda x: (x.get("published_at") or ""), reverse=self._desc)
