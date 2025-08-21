import os
import json
import time
import urllib.parse
import mimetypes
import re
import redis
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from newssearch.config import (
    HOST, PORT, OFFLINE_DEFAULT, UI_DIR, API_SECRET_KEY, ALLOWED_ORIGIN,
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_CACHE_TTL,
)
from newssearch.providers.guardian import GuardianProvider
from newssearch.providers.nyt import NYTProvider
from newssearch.utils.cache import RedisCache
from newssearch.utils.strategies import CanonUrlDedupe, PublishedAtSort
from newssearch.services.aggregator import Aggregator
from newssearch.utils.logging_setup import configure_logging_from_env
from newssearch.utils.rate_limit import RateLimiter  # <-- added

logger = configure_logging_from_env(__name__)

def clamp(n, lo, hi): return max(lo, min(hi, n))
def now_ms(): return int(time.time() * 1000)

# ----- ingress rate limiter (Redis-backed) -----
# 60 requests per minute per API key (fallback to client IP)
_redis_rl = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)  # <-- added
INGRESS_LIMITER = RateLimiter(_redis_rl, "ingress", rate=60, per_seconds=60)  # <-- added

def bootstrap():
    cache = RedisCache(REDIS_HOST, REDIS_PORT, REDIS_DB)
    providers = [GuardianProvider(), NYTProvider()]
    dedupe = CanonUrlDedupe()
    sorter = PublishedAtSort(desc=True)
    return Aggregator(providers, cache, dedupe, sorter, REDIS_CACHE_TTL)

AGGREGATOR = bootstrap()  # single instance; thread-safe as used

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default stdout access logs

    def _send_json(self, status: int, payload: dict):
        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            origin = self.headers.get("Origin", "")
            allow_origin = origin if re.match(r"^http://localhost:\d+$", origin) else ALLOWED_ORIGIN
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error("http_send_fail status=%d err=%s", status, e, exc_info=True)

    def do_OPTIONS(self):
        try:
            origin = self.headers.get("Origin", "")
            allow_origin = origin if re.match(r"^http://localhost:\d+$", origin) else ALLOWED_ORIGIN
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.end_headers()
        except Exception as e:
            logger.error("http_options_fail err=%s", e, exc_info=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        try:
            if parsed.path.startswith("/search") or parsed.path == "/openapi.json":
                auth = self.headers.get("Authorization", "")
                if not auth or auth != f"Bearer {API_SECRET_KEY}":
                    return self._send_json(401, {"error": "unauthorized"})

            if parsed.path == "/docs":
                docs_path = os.path.join(os.path.dirname(__file__), "../swagger_ui", "index.html")
                if not os.path.exists(docs_path):
                    return self._send_json(404, {"error": "swagger_ui_not_found"})
                with open(docs_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            if parsed.path == "/health":
                return self._send_json(200, {"status": "ok"})

            if parsed.path == "/openapi.json":
                try:
                    with open("../openapi.json", "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    return self.wfile.write(data)
                except FileNotFoundError:
                    return self._send_json(404, {"error": "openapi_missing"})
                except Exception as e:
                    logger.error("openapi_serve_fail err=%s", e, exc_info=True)
                    return self._send_json(500, {"error": "openapi_serve_error"})

            if parsed.path == "/search":
                # ---- ingress rate-limit check (per API key/IP) ----
                identity = self.headers.get("Authorization") or self.client_address[0]  # <-- added
                if not INGRESS_LIMITER.allow(identity):  # <-- added
                    return self._send_json(429, {"error": "rate_limit_exceeded"})  # <-- added

                qs = urllib.parse.parse_qs(parsed.query or "")
                query = (qs.get("query", [""])[0]).strip()
                if not re.match(r'^[\w\s-]{1,100}$', query):
                    return self._send_json(400, {"error": "invalid_query"})
                if not query:
                    return self._send_json(400, {"error": "query_required"})
                try:
                    page = int(qs.get("page", ["1"])[0])
                except Exception:
                    page = 1
                try:
                    page_size = int(qs.get("page_size", ["10"])[0])
                except Exception:
                    page_size = 10
                city = (qs.get("city", [""])[0])[:100]
                offline_param = (qs.get("offline", [""])[0]).strip()
                offline = OFFLINE_DEFAULT or (offline_param == "1")

                page = clamp(page, 1, 1000)
                page_size = clamp(page_size, 1, 50)

                start_ms = now_ms()
                try:
                    agg = AGGREGATOR.aggregate(query, page, page_size, offline)
                    time_taken = now_ms() - start_ms
                    base = "/search?query={}&page_size={}&city={}".format(
                        urllib.parse.quote(query), page_size, urllib.parse.quote(city)
                    )
                    next_page = page + 1 if page < agg["total_estimated_pages"] else None
                    prev_page = page - 1 if page > 1 else None
                    return self._send_json(200, {
                        "keyword": query,
                        "city": city,
                        "page": page,
                        "page_size": page_size,
                        "total_estimated_pages": agg["total_estimated_pages"],
                        "time_taken_ms": time_taken,
                        "links": {
                            "self": f"{base}&page={page}",
                            "next": f"{base}&page={next_page}" if next_page else None,
                            "prev": f"{base}&page={prev_page}" if prev_page else None
                        },
                        "items": agg["items"]
                    })
                except Exception as e:
                    logger.error("search_fail query=%r err=%s", query, e, exc_info=True)
                    agg = AGGREGATOR.aggregate(query, page, page_size, True)
                    time_taken = now_ms() - start_ms
                    return self._send_json(200, {
                        "keyword": query, "city": city,
                        "page": page, "page_size": page_size,
                        "total_estimated_pages": agg["total_estimated_pages"],
                        "time_taken_ms": time_taken,
                        "offline": True,
                        "links": {
                            "self": f"/search?query={urllib.parse.quote(query)}&page={page}&page_size={page_size}&city={urllib.parse.quote(city)}"
                        },
                        "items": agg["items"]
                    })

            return self._serve_static(parsed.path)
        except Exception as e:
            logger.error("request_unhandled_error path=%s err=%s", parsed.path, e, exc_info=True)
            return self._send_json(500, {"error": "internal_error"})

    def _serve_static(self, path: str):
        try:
            if not os.path.isdir(UI_DIR):
                return self._send_json(404, {"error": "ui_not_built"})
            if path in ("/", ""):
                file_path = os.path.join(UI_DIR, "index.html")
            else:
                file_path = os.path.join(UI_DIR, path.lstrip("/"))
                if not os.path.exists(file_path):
                    file_path = os.path.join(UI_DIR, "index.html")
            if not os.path.exists(file_path):
                return self._send_json(404, {"error": "not_found"})
            ctype, _ = mimetypes.guess_type(file_path)
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            logger.error("static_serve_fail path=%s err=%s", path, e, exc_info=True)
            return self._send_json(500, {"error": "static_serve_error"})

def main():
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical("server_crash err=%s", e, exc_info=True)
        raise
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
