"""Rate limiter for throttling POST requests."""

import logging
import time
import threading
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for throttling requests."""

    def __init__(self, requests_per_second: float):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum number of requests per second
        """
        self.requests_per_second = requests_per_second
        self.tokens = requests_per_second  # Start with full bucket
        self.last_update = time.time()
        self.lock = threading.Lock()
        
        # Calculate token refill rate
        self.refill_rate = requests_per_second  # Tokens per second

    def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens for a request.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if tokens acquired, False otherwise
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Refill tokens based on elapsed time
            self.tokens = min(
                self.requests_per_second,
                self.tokens + (elapsed * self.refill_rate)
            )
            self.last_update = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def wait(self, tokens: int = 1) -> None:
        """
        Wait until tokens are available, then acquire them.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        wait_start = time.time()
        wait_iterations = 0
        
        while not self.acquire(tokens):
            wait_iterations += 1
            # Calculate wait time
            with self.lock:
                needed = tokens - self.tokens
                wait_time = needed / self.refill_rate if self.refill_rate > 0 else 0.1
                wait_time = max(0.01, min(wait_time, 1.0))  # Cap at 1 second
                current_tokens = self.tokens
            
            logger.debug(f"Rate limiter waiting: tokens_needed={tokens}, tokens_available={current_tokens:.2f}, wait_time={wait_time:.3f}s, iteration={wait_iterations}")
            time.sleep(wait_time)
        
        total_wait_time = time.time() - wait_start
        if wait_iterations > 0:
            logger.debug(f"Rate limiter wait completed: tokens_acquired={tokens}, wait_iterations={wait_iterations}, total_wait_time={total_wait_time:.3f}s")


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for throttling requests."""

    def __init__(self, requests_per_second: float, window_size: float = 1.0):
        """
        Initialize sliding window rate limiter.

        Args:
            requests_per_second: Maximum number of requests per second
            window_size: Size of the time window in seconds
        """
        self.requests_per_window = requests_per_second * window_size
        self.window_size = window_size
        self.requests: deque = deque()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        Check if request can be made within rate limit.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if request can be made, False otherwise
        """
        with self.lock:
            now = time.time()
            
            # Remove requests outside the window
            while self.requests and self.requests[0] < now - self.window_size:
                self.requests.popleft()
            
            # Check if we can add more requests
            if len(self.requests) + tokens <= self.requests_per_window:
                for _ in range(tokens):
                    self.requests.append(now)
                return True
            else:
                return False

    def wait(self, tokens: int = 1) -> None:
        """
        Wait until request can be made within rate limit.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        while not self.acquire(tokens):
            with self.lock:
                if self.requests:
                    # Wait until oldest request expires
                    oldest = self.requests[0]
                    wait_time = self.window_size - (time.time() - oldest)
                    wait_time = max(0.01, min(wait_time, self.window_size))
                else:
                    wait_time = 0.01
            
            time.sleep(wait_time)


# Default to token bucket implementation
RateLimiter = RateLimiter  # Export token bucket as default

