"""
Rate Limiter - Sliding window rate limiting for Super RoastBot.

Uses a sliding window algorithm to track requests per user/session.
Configurable via environment variables for max requests and window duration.
Designed for compatibility with future authentication (per-user or per-IP limiting).
"""

import os
import time
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# Configuration via environment variables with sensible defaults
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 10))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

# In-memory store: maps user/session identifier -> list of request timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


def _cleanup_expired(identifier: str) -> None:
    """Remove timestamps outside the current sliding window."""
    cutoff = time.time() - WINDOW_SECONDS
    _request_log[identifier] = [
        ts for ts in _request_log[identifier] if ts > cutoff
    ]


def is_rate_limited(identifier: str) -> tuple[bool, dict]:
    """
    Check if the given identifier has exceeded the rate limit.

    Args:
        identifier: A unique key for the requester (session ID, user ID, or IP).

    Returns:
        A tuple of (is_limited, info) where info contains:
            - remaining: number of requests remaining in the window
            - limit: the max requests allowed
            - retry_after: seconds until the next request is allowed (0 if not limited)
    """
    _cleanup_expired(identifier)

    current_count = len(_request_log[identifier])
    remaining = max(0, MAX_REQUESTS - current_count)

    if current_count >= MAX_REQUESTS:
        oldest = min(_request_log[identifier])
        retry_after = round(oldest + WINDOW_SECONDS - time.time(), 1)
        retry_after = max(0, retry_after)
        return True, {
            "remaining": 0,
            "limit": MAX_REQUESTS,
            "window": WINDOW_SECONDS,
            "retry_after": retry_after,
        }

    return False, {
        "remaining": remaining,
        "limit": MAX_REQUESTS,
        "window": WINDOW_SECONDS,
        "retry_after": 0,
    }


def record_request(identifier: str) -> None:
    """Record a new request timestamp for the given identifier."""
    _request_log[identifier].append(time.time())


def reset(identifier: str) -> None:
    """Reset the request log for a specific identifier."""
    _request_log.pop(identifier, None)


def reset_all() -> None:
    """Clear all rate limit tracking data."""
    _request_log.clear()


def get_usage(identifier: str) -> dict:
    """
    Get current usage stats for the given identifier without recording a request.

    Args:
        identifier: A unique key for the requester.

    Returns:
        Dict with current usage info (count, remaining, limit, window).
    """
    _cleanup_expired(identifier)
    current_count = len(_request_log[identifier])
    return {
        "count": current_count,
        "remaining": max(0, MAX_REQUESTS - current_count),
        "limit": MAX_REQUESTS,
        "window": WINDOW_SECONDS,
    }
