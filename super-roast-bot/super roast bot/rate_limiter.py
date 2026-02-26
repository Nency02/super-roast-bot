"""
Rate Limiter Module for Super RoastBot.

Provides sliding window rate limiting to prevent excessive or spam usage.
Supports per-session, per-IP, or per-user limiting with configurable thresholds.
Designed for compatibility with future authentication systems.
"""

import os
import time
import threading
from collections import defaultdict


# ── Configuration via environment variables ──
DEFAULT_MAX_REQUESTS = 10
DEFAULT_WINDOW_SECONDS = 60

MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", DEFAULT_MAX_REQUESTS))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS))


class RateLimiter:
    """
    Sliding window rate limiter.

    Tracks request timestamps per client identifier (session ID, IP, or user ID).
    Thread-safe for concurrent access.

    Attributes:
        max_requests: Maximum number of requests allowed within the time window.
        window_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, max_requests: int = None, window_seconds: int = None):
        self.max_requests = max_requests if max_requests is not None else MAX_REQUESTS
        self.window_seconds = window_seconds if window_seconds is not None else WINDOW_SECONDS
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    def _cleanup(self, client_id: str):
        """Remove expired timestamps for a given client."""
        cutoff = time.time() - self.window_seconds
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]
        if not self._requests[client_id]:
            del self._requests[client_id]

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if a request from the given client is allowed.

        Args:
            client_id: Unique identifier for the client (session ID, IP, or user ID).

        Returns:
            True if the request is within the rate limit, False otherwise.
        """
        with self._lock:
            self._cleanup(client_id)
            count = len(self._requests.get(client_id, []))
            if count >= self.max_requests:
                return False
            self._requests[client_id].append(time.time())
            return True

    def get_remaining(self, client_id: str) -> int:
        """
        Get the number of remaining requests for a client within the current window.

        Args:
            client_id: Unique identifier for the client.

        Returns:
            Number of requests remaining before the limit is reached.
        """
        with self._lock:
            self._cleanup(client_id)
            count = len(self._requests.get(client_id, []))
            return max(0, self.max_requests - count)

    def get_retry_after(self, client_id: str) -> int:
        """
        Get the number of seconds until the client can make another request.

        Useful for setting Retry-After headers (HTTP 429 responses).

        Args:
            client_id: Unique identifier for the client.

        Returns:
            Seconds until the oldest request in the window expires, or 0 if allowed.
        """
        with self._lock:
            self._cleanup(client_id)
            timestamps = self._requests.get(client_id, [])
            if len(timestamps) < self.max_requests:
                return 0
            oldest = min(timestamps)
            retry_after = self.window_seconds - (time.time() - oldest)
            return max(0, int(retry_after) + 1)

    def reset(self, client_id: str = None):
        """
        Reset rate limit tracking.

        Args:
            client_id: If provided, reset only this client. Otherwise, reset all.
        """
        with self._lock:
            if client_id:
                self._requests.pop(client_id, None)
            else:
                self._requests.clear()


# ── Global rate limiter instance ──
rate_limiter = RateLimiter()
