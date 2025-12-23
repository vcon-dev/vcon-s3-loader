"""Tests for rate limiter."""

import pytest
import time
from src.rate_limiter import RateLimiter, SlidingWindowRateLimiter


def test_rate_limiter_acquire():
    """Test token bucket rate limiter acquire."""
    limiter = RateLimiter(requests_per_second=10.0)
    
    # Should acquire immediately with full bucket
    assert limiter.acquire() is True
    
    # Acquire all tokens
    for _ in range(9):
        assert limiter.acquire() is True
    
    # Should fail when bucket is empty
    assert limiter.acquire() is False


def test_rate_limiter_wait():
    """Test rate limiter wait."""
    limiter = RateLimiter(requests_per_second=10.0)
    
    # Acquire all tokens
    for _ in range(10):
        limiter.acquire()
    
    # Wait should eventually succeed after refill
    start_time = time.time()
    limiter.wait()
    elapsed = time.time() - start_time
    
    # Should have waited for refill (approximately 0.1 seconds for 1 token at 10/sec)
    assert elapsed >= 0.05  # Allow some tolerance


def test_sliding_window_acquire():
    """Test sliding window rate limiter acquire."""
    limiter = SlidingWindowRateLimiter(requests_per_second=10.0, window_size=1.0)
    
    # Should acquire immediately
    assert limiter.acquire() is True
    
    # Acquire up to limit
    for _ in range(9):
        assert limiter.acquire() is True
    
    # Should fail when limit reached
    assert limiter.acquire() is False


def test_sliding_window_wait():
    """Test sliding window rate limiter wait."""
    limiter = SlidingWindowRateLimiter(requests_per_second=2.0, window_size=1.0)
    
    # Fill window
    limiter.acquire()
    limiter.acquire()
    
    # Next acquire should wait
    start_time = time.time()
    limiter.wait()
    elapsed = time.time() - start_time
    
    # Should have waited for window to slide
    assert elapsed >= 0.1  # Allow some tolerance

