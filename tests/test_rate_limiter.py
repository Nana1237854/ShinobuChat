import time
import unittest

from app.core.exceptions import TooManyRequestsError
from app.core.rate_limiter import MemoryRateLimiterBackend, RateLimiter


class MemoryRateLimiterBackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryRateLimiterBackend()

    def test_allows_requests_within_limit(self):
        for _ in range(30):
            self.assertTrue(self.backend.is_allowed("test_key", 30, 60))

    def test_blocks_requests_over_limit(self):
        for _ in range(30):
            self.backend.is_allowed("test_key", 30, 60)
        self.assertFalse(self.backend.is_allowed("test_key", 30, 60))

    def test_sliding_window_evicts_old_entries(self):
        for _ in range(30):
            self.backend.is_allowed("test_key", 30, 60)
        self.assertFalse(self.backend.is_allowed("test_key", 30, 60))
        self.backend._store["test_key"][0] -= 61
        self.assertTrue(self.backend.is_allowed("test_key", 30, 60))

    def test_independent_keys_dont_conflict(self):
        for _ in range(30):
            self.backend.is_allowed("key_a", 30, 60)
        self.assertTrue(self.backend.is_allowed("key_b", 30, 60))

    def test_oldest_timestamp_returns_none_for_unknown_key(self):
        self.assertIsNone(self.backend.oldest_timestamp("nonexistent"))

    def test_oldest_timestamp_returns_first_entry(self):
        t0 = time.monotonic()
        self.backend.is_allowed("test_key", 30, 60)
        oldest = self.backend.oldest_timestamp("test_key")
        self.assertIsNotNone(oldest)
        self.assertGreaterEqual(oldest, t0)


class RateLimiterCheckTests(unittest.TestCase):
    def setUp(self):
        self.limiter = RateLimiter()

    def test_check_raises_too_many_requests_on_limit(self):
        for _ in range(5):
            self.limiter.check("test_key", 5, 60)
        with self.assertRaises(TooManyRequestsError) as ctx:
            self.limiter.check("test_key", 5, 60)
        self.assertIn("Rate limit exceeded", ctx.exception.detail)
        self.assertGreater(ctx.exception.retry_after, 0)

    def test_check_includes_retry_after(self):
        for _ in range(5):
            self.limiter.check("retry_key", 5, 60)
        with self.assertRaises(TooManyRequestsError) as ctx:
            self.limiter.check("retry_key", 5, 60)
        self.assertGreater(ctx.exception.retry_after, 0)

    def test_allows_exact_limit(self):
        for _ in range(3):
            self.limiter.check("exact_key", 3, 60)


if __name__ == "__main__":
    unittest.main()
