"""
Unit tests for the RateLimiter module.

Tests cover:
- Basic allow/deny behavior
- Sliding window expiration
- Per-client isolation
- Remaining request count
- Retry-after calculation
- Reset functionality
- Custom configuration
- Thread safety
"""

import time
import threading
import unittest
from unittest.mock import patch

from rate_limiter import RateLimiter


class TestRateLimiterBasic(unittest.TestCase):
    """Test basic rate limiting allow/deny behavior."""

    def setUp(self):
        self.limiter = RateLimiter(max_requests=3, window_seconds=60)

    def test_allows_requests_under_limit(self):
        """Requests under the limit should be allowed."""
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user1"))

    def test_denies_requests_over_limit(self):
        """Requests exceeding the limit should be denied."""
        for _ in range(3):
            self.limiter.is_allowed("user1")
        self.assertFalse(self.limiter.is_allowed("user1"))

    def test_denies_multiple_excess_requests(self):
        """Multiple excess requests should all be denied."""
        for _ in range(3):
            self.limiter.is_allowed("user1")
        self.assertFalse(self.limiter.is_allowed("user1"))
        self.assertFalse(self.limiter.is_allowed("user1"))


class TestRateLimiterIsolation(unittest.TestCase):
    """Test that rate limits are isolated per client."""

    def setUp(self):
        self.limiter = RateLimiter(max_requests=2, window_seconds=60)

    def test_different_clients_have_separate_limits(self):
        """Each client should have their own rate limit counter."""
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertFalse(self.limiter.is_allowed("user1"))
        # user2 should still be allowed
        self.assertTrue(self.limiter.is_allowed("user2"))
        self.assertTrue(self.limiter.is_allowed("user2"))
        self.assertFalse(self.limiter.is_allowed("user2"))

    def test_one_client_limit_does_not_affect_another(self):
        """Hitting the limit for one client should not block another."""
        for _ in range(2):
            self.limiter.is_allowed("blocked_user")
        self.assertFalse(self.limiter.is_allowed("blocked_user"))
        self.assertTrue(self.limiter.is_allowed("free_user"))


class TestRateLimiterSlidingWindow(unittest.TestCase):
    """Test sliding window behavior and expiration."""

    def test_requests_allowed_after_window_expires(self):
        """Requests should be allowed again after the window expires."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        self.assertTrue(limiter.is_allowed("user1"))
        self.assertTrue(limiter.is_allowed("user1"))
        self.assertFalse(limiter.is_allowed("user1"))

        # Wait for the window to expire
        time.sleep(1.1)
        self.assertTrue(limiter.is_allowed("user1"))

    def test_sliding_window_partial_expiry(self):
        """Only expired requests should be removed from the window."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.is_allowed("user1")
        time.sleep(0.6)
        limiter.is_allowed("user1")
        self.assertFalse(limiter.is_allowed("user1"))

        # First request expires, but second is still in window
        time.sleep(0.5)
        self.assertTrue(limiter.is_allowed("user1"))


class TestRateLimiterRemaining(unittest.TestCase):
    """Test remaining request count."""

    def setUp(self):
        self.limiter = RateLimiter(max_requests=5, window_seconds=60)

    def test_remaining_starts_at_max(self):
        """Remaining should equal max_requests initially."""
        self.assertEqual(self.limiter.get_remaining("user1"), 5)

    def test_remaining_decreases_with_requests(self):
        """Remaining should decrease as requests are made."""
        self.limiter.is_allowed("user1")
        self.assertEqual(self.limiter.get_remaining("user1"), 4)
        self.limiter.is_allowed("user1")
        self.assertEqual(self.limiter.get_remaining("user1"), 3)

    def test_remaining_never_negative(self):
        """Remaining should not go below zero."""
        for _ in range(10):
            self.limiter.is_allowed("user1")
        self.assertEqual(self.limiter.get_remaining("user1"), 0)


class TestRateLimiterRetryAfter(unittest.TestCase):
    """Test retry-after calculation for HTTP 429 responses."""

    def test_retry_after_zero_when_allowed(self):
        """Retry-after should be 0 when requests are allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        self.assertEqual(limiter.get_retry_after("user1"), 0)

    def test_retry_after_positive_when_limited(self):
        """Retry-after should be positive when rate limited."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        retry_after = limiter.get_retry_after("user1")
        self.assertGreater(retry_after, 0)
        self.assertLessEqual(retry_after, 61)


class TestRateLimiterReset(unittest.TestCase):
    """Test reset functionality."""

    def setUp(self):
        self.limiter = RateLimiter(max_requests=2, window_seconds=60)

    def test_reset_specific_client(self):
        """Resetting a specific client should clear only their history."""
        self.limiter.is_allowed("user1")
        self.limiter.is_allowed("user1")
        self.assertFalse(self.limiter.is_allowed("user1"))

        self.limiter.is_allowed("user2")

        self.limiter.reset("user1")
        self.assertTrue(self.limiter.is_allowed("user1"))
        # user2's count should be unaffected
        self.assertEqual(self.limiter.get_remaining("user2"), 1)

    def test_reset_all_clients(self):
        """Resetting all should clear all client histories."""
        self.limiter.is_allowed("user1")
        self.limiter.is_allowed("user1")
        self.limiter.is_allowed("user2")
        self.limiter.is_allowed("user2")

        self.limiter.reset()
        self.assertTrue(self.limiter.is_allowed("user1"))
        self.assertTrue(self.limiter.is_allowed("user2"))

    def test_reset_nonexistent_client(self):
        """Resetting a client that doesn't exist should not raise an error."""
        self.limiter.reset("nonexistent")


class TestRateLimiterConfiguration(unittest.TestCase):
    """Test custom configuration."""

    def test_custom_max_requests(self):
        """Custom max_requests should be respected."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        self.assertTrue(limiter.is_allowed("user1"))
        self.assertFalse(limiter.is_allowed("user1"))

    def test_custom_window_seconds(self):
        """Custom window_seconds should be respected."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        self.assertTrue(limiter.is_allowed("user1"))
        self.assertFalse(limiter.is_allowed("user1"))
        time.sleep(1.1)
        self.assertTrue(limiter.is_allowed("user1"))

    @patch.dict("os.environ", {"RATE_LIMIT_MAX_REQUESTS": "5", "RATE_LIMIT_WINDOW_SECONDS": "30"})
    def test_env_var_configuration(self):
        """Environment variables should configure defaults when no args are passed."""
        # Re-import to pick up patched env vars
        import importlib
        import rate_limiter as rl_module
        importlib.reload(rl_module)

        self.assertEqual(rl_module.MAX_REQUESTS, 5)
        self.assertEqual(rl_module.WINDOW_SECONDS, 30)

        limiter = rl_module.RateLimiter()
        self.assertEqual(limiter.max_requests, 5)
        self.assertEqual(limiter.window_seconds, 30)


class TestRateLimiterThreadSafety(unittest.TestCase):
    """Test thread safety of the rate limiter."""

    def test_concurrent_requests(self):
        """Rate limiter should correctly handle concurrent requests."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        results = []

        def make_request():
            result = limiter.is_allowed("user1")
            results.append(result)

        threads = [threading.Thread(target=make_request) for _ in range(150)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(1 for r in results if r)
        denied_count = sum(1 for r in results if not r)

        self.assertEqual(allowed_count, 100)
        self.assertEqual(denied_count, 50)


if __name__ == "__main__":
    unittest.main()
