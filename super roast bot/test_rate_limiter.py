"""
Unit tests for the rate_limiter module.

Tests sliding window rate limiting behavior including:
- Allowing requests under the limit
- Blocking requests over the limit
- Sliding window expiry
- Reset functionality
- Usage stats reporting
"""

import time
import unittest
from unittest.mock import patch

import rate_limiter
from rate_limiter import (
    is_rate_limited,
    record_request,
    reset,
    reset_all,
    get_usage,
)


class TestRateLimiter(unittest.TestCase):
    """Tests for the sliding window rate limiter."""

    def setUp(self):
        """Reset all rate limit state before each test."""
        reset_all()

    def tearDown(self):
        """Clean up after each test."""
        reset_all()

    # ── Basic allow / deny ──

    def test_allows_requests_under_limit(self):
        """Requests below MAX_REQUESTS should not be rate limited."""
        identifier = "user-under-limit"
        for _ in range(rate_limiter.MAX_REQUESTS):
            limited, info = is_rate_limited(identifier)
            self.assertFalse(limited)
            self.assertEqual(info["retry_after"], 0)
            record_request(identifier)

    def test_blocks_requests_over_limit(self):
        """Requests at or above MAX_REQUESTS should be rate limited."""
        identifier = "user-over-limit"
        for _ in range(rate_limiter.MAX_REQUESTS):
            record_request(identifier)

        limited, info = is_rate_limited(identifier)
        self.assertTrue(limited)
        self.assertEqual(info["remaining"], 0)
        self.assertGreater(info["retry_after"], 0)

    def test_returns_429_equivalent_info(self):
        """Info dict should contain fields suitable for an HTTP 429 response."""
        identifier = "user-429"
        for _ in range(rate_limiter.MAX_REQUESTS):
            record_request(identifier)

        limited, info = is_rate_limited(identifier)
        self.assertTrue(limited)
        self.assertIn("retry_after", info)
        self.assertIn("limit", info)
        self.assertIn("remaining", info)
        self.assertIn("window", info)
        self.assertEqual(info["limit"], rate_limiter.MAX_REQUESTS)
        self.assertEqual(info["window"], rate_limiter.WINDOW_SECONDS)

    # ── Remaining count ──

    def test_remaining_decrements(self):
        """Remaining count should decrease as requests are recorded."""
        identifier = "user-remaining"
        for i in range(rate_limiter.MAX_REQUESTS):
            _, info = is_rate_limited(identifier)
            self.assertEqual(info["remaining"], rate_limiter.MAX_REQUESTS - i)
            record_request(identifier)

    # ── Sliding window expiry ──

    def test_sliding_window_expires_oldest(self):
        """After the window elapses, old requests should expire and new ones allowed."""
        identifier = "user-expiry"

        # Fill up the limit with timestamps in the past
        past = time.time() - rate_limiter.WINDOW_SECONDS - 1
        with patch("rate_limiter.time") as mock_time:
            mock_time.time.return_value = past
            for _ in range(rate_limiter.MAX_REQUESTS):
                record_request(identifier)

        # Now (real time), all those requests should have expired
        limited, info = is_rate_limited(identifier)
        self.assertFalse(limited)
        self.assertEqual(info["remaining"], rate_limiter.MAX_REQUESTS)

    def test_partial_window_expiry(self):
        """Only expired requests should be removed, recent ones kept."""
        identifier = "user-partial"

        # Record some requests in the past (expired)
        old_time = time.time() - rate_limiter.WINDOW_SECONDS - 1
        with patch("rate_limiter.time") as mock_time:
            mock_time.time.return_value = old_time
            for _ in range(5):
                record_request(identifier)

        # Record some requests now (still valid)
        for _ in range(3):
            record_request(identifier)

        usage = get_usage(identifier)
        self.assertEqual(usage["count"], 3)
        self.assertEqual(usage["remaining"], rate_limiter.MAX_REQUESTS - 3)

    # ── Reset ──

    def test_reset_single_user(self):
        """Resetting a user should clear only their request log."""
        id_a = "user-a"
        id_b = "user-b"
        record_request(id_a)
        record_request(id_b)

        reset(id_a)

        usage_a = get_usage(id_a)
        usage_b = get_usage(id_b)
        self.assertEqual(usage_a["count"], 0)
        self.assertEqual(usage_b["count"], 1)

    def test_reset_all(self):
        """reset_all should clear all tracking data."""
        for i in range(5):
            record_request(f"user-{i}")

        reset_all()

        for i in range(5):
            usage = get_usage(f"user-{i}")
            self.assertEqual(usage["count"], 0)

    # ── get_usage ──

    def test_get_usage_no_requests(self):
        """Usage for a new identifier should show zero count and full remaining."""
        usage = get_usage("new-user")
        self.assertEqual(usage["count"], 0)
        self.assertEqual(usage["remaining"], rate_limiter.MAX_REQUESTS)
        self.assertEqual(usage["limit"], rate_limiter.MAX_REQUESTS)
        self.assertEqual(usage["window"], rate_limiter.WINDOW_SECONDS)

    def test_get_usage_with_requests(self):
        """Usage should reflect recorded requests."""
        identifier = "active-user"
        record_request(identifier)
        record_request(identifier)

        usage = get_usage(identifier)
        self.assertEqual(usage["count"], 2)
        self.assertEqual(usage["remaining"], rate_limiter.MAX_REQUESTS - 2)

    # ── Multiple users ──

    def test_independent_user_limits(self):
        """Each user should have independent rate limit tracking."""
        id_a = "user-independent-a"
        id_b = "user-independent-b"

        # Fill user A to the limit
        for _ in range(rate_limiter.MAX_REQUESTS):
            record_request(id_a)

        # User A should be limited, user B should not
        limited_a, _ = is_rate_limited(id_a)
        limited_b, _ = is_rate_limited(id_b)
        self.assertTrue(limited_a)
        self.assertFalse(limited_b)

    # ── Edge cases ──

    def test_empty_identifier(self):
        """Should work with an empty string identifier."""
        limited, info = is_rate_limited("")
        self.assertFalse(limited)
        self.assertEqual(info["remaining"], rate_limiter.MAX_REQUESTS)

    def test_retry_after_decreases_over_time(self):
        """retry_after should decrease as time passes."""
        identifier = "user-retry"
        for _ in range(rate_limiter.MAX_REQUESTS):
            record_request(identifier)

        _, info1 = is_rate_limited(identifier)
        time.sleep(0.1)
        _, info2 = is_rate_limited(identifier)

        self.assertGreaterEqual(info1["retry_after"], info2["retry_after"])


if __name__ == "__main__":
    unittest.main()
