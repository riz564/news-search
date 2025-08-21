# tests/conftest.py
import os
import json
import threading
import importlib
from contextlib import contextmanager
from pathlib import Path

import fakeredis
import pytest
from freezegun import freeze_time


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    import redis
    monkeypatch.setattr(redis, "StrictRedis", fakeredis.FakeStrictRedis)
    yield


@pytest.fixture
def offline_files(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    guardian_payload = {"response": {"results": []}}
    nyt_payload = {"response": {"docs": []}}

    (tmp_path / "guardian_offline.json").write_text(json.dumps(guardian_payload), encoding="utf-8")
    (tmp_path / "nyt_offline.json").write_text(json.dumps(nyt_payload), encoding="utf-8")
    (data_dir / "guardian_offline.json").write_text(json.dumps(guardian_payload), encoding="utf-8")
    (data_dir / "nyt_offline.json").write_text(json.dumps(nyt_payload), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    yield tmp_path


@pytest.fixture
def freeze():
    with freeze_time("2025-08-20 10:00:00") as fz:
        yield fz


def _write_temp_env(project_root: Path, updates: dict) -> tuple[bool, str]:
    env_path = project_root / ".env"
    had_original = env_path.exists()
    original = env_path.read_text() if had_original else ""

    lines = []
    if had_original:
        for line in original.splitlines():
            if not line or line.startswith("#"):
                lines.append(line)
                continue
            k = line.split("=", 1)[0].strip()
            if k in updates:
                continue  # will replace
            lines.append(line)

    for k, v in updates.items():
        lines.append(f"{k}={v}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return had_original, original


@contextmanager
def run_server(host="127.0.0.1", port=8083, env=None):
    """
    Start the HTTP server with a temporary project .env so newssearch.config
    picks up test-specific values like API_SECRET_KEY/OFFLINE_DEFAULT even
    though it loads .env with override=True.
    """
    # Resolve project root (repo directory that contains `newssearch/`)
    project_root = Path(__file__).resolve().parents[1]

    # Prepare the .env content we need for this test
    updates = {
        "API_SECRET_KEY": (env or {}).get("API_SECRET_KEY", "test-secret"),
        "OFFLINE_DEFAULT": (env or {}).get("OFFLINE_DEFAULT", "1"),
        "HOST": host,
        "PORT": str(port),
    }
    had_original, original_env = _write_temp_env(project_root, updates)

    # Also mirror into process env (harmless; .env still wins in config.py)
    os.environ.update(updates)

    # Reload config & app so they pick up the new .env
    import newssearch.config as config
    importlib.reload(config)
    import newssearch.app as app
    importlib.reload(app)

    httpd = app.HTTPServer((host, port), app.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield (httpd, f"http://{host}:{port}")
    finally:
        httpd.shutdown()
        t.join()
        # Restore original .env
        env_path = project_root / ".env"
        if had_original:
            env_path.write_text(original_env, encoding="utf-8")
        else:
            try:
                env_path.unlink()
            except FileNotFoundError:
                pass
