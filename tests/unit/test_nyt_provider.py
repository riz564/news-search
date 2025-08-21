import io, json
from newssearch.providers.nyt import NYTProvider

class FakeResp:
    def __init__(self, payload): self._p = payload
    def read(self): return self._p
    def __enter__(self): return self
    def __exit__(self, *a): return False

def test_nyt_retry_then_success(monkeypatch, tmp_path, offline_files):
    attempts = {"n": 0}
    def fake_open(url, timeout=6):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TimeoutError("boom")
        payload = json.dumps({"response": {"docs": []}}).encode()
        return FakeResp(payload)
    monkeypatch.setattr("urllib.request.urlopen", fake_open)

    np = NYTProvider(api_key="k")
    out = np.fetch("apple", page=1, page_size=10, offline=False)
    assert attempts["n"] == 3
    assert "items" in out
