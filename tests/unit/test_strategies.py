from newssearch.utils.strategies import CanonUrlDedupe, PublishedAtSort

def test_dedupe_by_canon():
    items = [
        {"url": "HTTP://EXAMPLE.com/a"},
        {"url": "http://example.com/a"},
        {"url": "http://example.com/b"},
    ]
    out = CanonUrlDedupe().dedupe(items)
    assert len(out) == 2

def test_sort_by_published_at():
    items = [{"published_at": "2024-01-01"}, {"published_at": "2025-01-01"}]
    out = PublishedAtSort(desc=True).sort(items)
    assert out[0]["published_at"] == "2025-01-01"
