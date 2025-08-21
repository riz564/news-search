import re
def canon(url: str) -> str:
    # Remove protocol, www, trailing slashes, and lowercase
    url = url.strip().lower()
    url = re.sub(r'^https?://(www\.)?', '', url)
    url = url.rstrip('/')
    return url
def normalize_guardian(data):
    resp = data.get("response", {})
    results = resp.get("results", [])
    total = int(resp.get("total", len(results)))
    norm = []
    for it in results:
        norm.append({
            "source": "guardian",
            "title": it.get("webTitle"),
            "description": ((it.get("fields") or {}).get("trailText") or ""),
            "url": it.get("webUrl"),
            "published_at": it.get("webPublicationDate"),
            "website": "The Guardian",
        })
    return {"items": norm, "total": total}

def normalize_nyt(data, page_size):
    resp = data.get("response", {})
    docs = resp.get("docs", [])
    meta = resp.get("meta", {})
    total = int(meta.get("hits", len(docs)))
    norm = []
    for d in docs[:page_size]:
        norm.append({
            "source": "nytimes",
            "title": (d.get("headline") or {}).get("main"),
            "description": (d.get("abstract") or "")[:280],
            "url": d.get("web_url"),
            "published_at": d.get("pub_date"),
            "website": "The New York Times",
        })
    return {"items": norm, "total": total}
