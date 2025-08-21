# newssearch/config.py
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load project root .env first, and allow it to override the process env (dev-friendly)
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Also try auto-discovery as a secondary source (won't override what is set)
load_dotenv(find_dotenv(), override=False)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

GUARDIAN_KEY = os.getenv("GUARDIAN_API_KEY", "")
NYT_KEY = os.getenv("NYT_API_KEY", "")

OFFLINE_DEFAULT = os.getenv("OFFLINE_DEFAULT", "0") == "1"
UI_DIR = os.path.join(os.path.dirname(__file__), "../ui_build")

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")

# If you had dev defaults like "dev-secret" here, replace with a neutral fallback
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "changeme")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "300"))
