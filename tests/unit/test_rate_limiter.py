from newssearch.utils.rate_limit import RateLimiter
import fakeredis
from freezegun import freeze_time

def test_rate_limiter_allows_until_threshold():
    rl = RateLimiter(fakeredis.FakeStrictRedis(), "ingress", rate=3, per_seconds=60)
    assert rl.allow("user")
    assert rl.allow("user")
    assert rl.allow("user")
    assert rl.allow("user") is False

def test_rate_limiter_window_resets():
    rl = RateLimiter(fakeredis.FakeStrictRedis(), "ingress", rate=1, per_seconds=60)
    with freeze_time("2025-08-20 10:00:00"):
        assert rl.allow("ip")
        assert rl.allow("ip") is False
    with freeze_time("2025-08-20 10:01:01"):
        assert rl.allow("ip")  # new window
