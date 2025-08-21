import pybreaker

guardian_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)
nyt_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=60)
