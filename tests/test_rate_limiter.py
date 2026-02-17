"""Tests for the RateLimiter class."""

import time
from unittest.mock import patch

import pytest

from src.rate_limiter import RateLimiter


def test_requests_within_limit_allowed():
    """3 requests within 1 second are all allowed (default limit=3)."""
    rl = RateLimiter(max_requests_per_second=3)
    assert rl.is_allowed("10.0.0.1") is True
    assert rl.is_allowed("10.0.0.1") is True
    assert rl.is_allowed("10.0.0.1") is True


def test_fourth_request_rejected():
    """4th request in same window is rejected."""
    rl = RateLimiter(max_requests_per_second=3)
    for _ in range(3):
        rl.is_allowed("10.0.0.1")
    assert rl.is_allowed("10.0.0.1") is False


def test_allowed_again_after_window_expires():
    """After the 1-second window passes, requests are allowed again."""
    rl = RateLimiter(max_requests_per_second=3)
    base = 1000000.0

    with patch("src.rate_limiter.time.time", return_value=base):
        for _ in range(3):
            rl.is_allowed("10.0.0.1")

    # Jump 1.1 seconds forward
    with patch("src.rate_limiter.time.time", return_value=base + 1.1):
        assert rl.is_allowed("10.0.0.1") is True


def test_different_ips_isolated():
    """Rate limits are per-IP; one IP's usage doesn't affect another."""
    rl = RateLimiter(max_requests_per_second=3)
    for _ in range(3):
        rl.is_allowed("10.0.0.1")

    # Different IP should still be allowed
    assert rl.is_allowed("10.0.0.2") is True


def test_custom_rate_limit():
    """Custom max_requests_per_second is respected."""
    rl = RateLimiter(max_requests_per_second=5)
    for _ in range(5):
        assert rl.is_allowed("10.0.0.1") is True
    assert rl.is_allowed("10.0.0.1") is False


def test_cleanup_removes_expired_ips():
    """Expired IPs are cleaned up from internal state."""
    rl = RateLimiter(max_requests_per_second=3)
    base = 1000000.0

    with patch("src.rate_limiter.time.time", return_value=base):
        rl.is_allowed("10.0.0.1")

    # 2 seconds later – the old entry should be cleaned
    with patch("src.rate_limiter.time.time", return_value=base + 2.0):
        rl.is_allowed("10.0.0.2")

    assert "10.0.0.1" not in rl._timestamps


def test_sliding_window_partial_expiry():
    """Older timestamps expire while newer ones stay valid."""
    rl = RateLimiter(max_requests_per_second=3)
    base = 1000000.0

    # First two at t=0
    with patch("src.rate_limiter.time.time", return_value=base):
        rl.is_allowed("10.0.0.1")
        rl.is_allowed("10.0.0.1")

    # Third at t=0.5
    with patch("src.rate_limiter.time.time", return_value=base + 0.5):
        rl.is_allowed("10.0.0.1")

    # At t=1.05 the first two expire but the third is still in window
    # so only 1 timestamp remains → 2 more should be allowed
    with patch("src.rate_limiter.time.time", return_value=base + 1.05):
        assert rl.is_allowed("10.0.0.1") is True
        assert rl.is_allowed("10.0.0.1") is True
        assert rl.is_allowed("10.0.0.1") is False
