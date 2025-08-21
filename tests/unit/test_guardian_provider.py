import json
from types import SimpleNamespace
from newssearch.providers.guardian import GuardianProvider

class DummyLimiter:
    def __init__(self, allow_n=999): self.n = allow_n
    def allow(self, key):
        self.n -= 1
        return self.n >= 0

def test_guardian_egress_denied_falls_back_offline(monkeypatch, offline_files, tmp_path):
    # Make _fetch read from a fake urlopen that shouldn't be reached
    def bad_open(url, timeout=6): raise AssertionError("Should not call upstream")
    monkeypatch.setattr("urllib.request.urlopen", bad_open)

    gp = GuardianProvider(api_key="k", egress_limiter=DummyLimiter(allow_n=0))
    out = gp.fetch("apple", 1, 10, offline=False)
    assert isinstance(out, dict)
    assert "items" in out
