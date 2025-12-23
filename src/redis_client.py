"""Redis client for deduplication tracking."""

import logging
from typing import Optional
import redis
from redis.exceptions import RedisError, ConnectionError

logger = logging.getLogger(__name__)


class RedisClient:
    """Client for tracking processed vCons in Redis."""

    def __init__(self, redis_url: str, key_prefix: str = "vcon-loader", enabled: bool = True):
        """
        Initialize Redis client.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all Redis keys
            enabled: Whether Redis is enabled (if False, operations are no-ops)
        """
        self.enabled = enabled
        self.key_prefix = key_prefix
        self._client: Optional[redis.Redis] = None
        self._connected = False
        
        if enabled:
            try:
                self._client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self._client.ping()
                self._connected = True
                logger.info(f"Connected to Redis at {redis_url}")
            except (ConnectionError, RedisError) as e:
                logger.warning(f"Failed to connect to Redis: {e}. Continuing without Redis.")
                self._connected = False
                self.enabled = False

    def _make_key(self, identifier: str) -> str:
        """Create a Redis key with prefix."""
        return f"{self.key_prefix}:processed:{identifier}"

    def is_processed(self, identifier: str) -> bool:
        """
        Check if a vCon has been processed.

        Args:
            identifier: vCon UUID or S3 key

        Returns:
            True if processed, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Redis disabled, skipping processed check for identifier={identifier}")
            return False
        
        if not self._connected:
            logger.debug(f"Redis not connected, skipping processed check for identifier={identifier}")
            return False
        
        try:
            key = self._make_key(identifier)
            logger.debug(f"Checking Redis for processed status: key={key}, identifier={identifier}")
            exists = self._client.exists(key)  # type: ignore
            result = bool(exists)
            logger.debug(f"Redis processed check result: identifier={identifier}, is_processed={result}")
            return result
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis error checking processed status: identifier={identifier}, error_type={type(e).__name__}, error={str(e)}")
            self._connected = False
            return False

    def mark_processed(self, identifier: str, ttl: Optional[int] = None):
        """
        Mark a vCon as processed.

        Args:
            identifier: vCon UUID or S3 key
            ttl: Optional TTL in seconds (if None, key persists indefinitely)
        """
        if not self.enabled:
            logger.debug(f"Redis disabled, skipping mark processed for identifier={identifier}")
            return
        
        if not self._connected:
            logger.debug(f"Redis not connected, skipping mark processed for identifier={identifier}")
            return
        
        try:
            key = self._make_key(identifier)
            logger.debug(f"Marking as processed in Redis: key={key}, identifier={identifier}, ttl={ttl}")
            if ttl:
                self._client.setex(key, ttl, "1")  # type: ignore
                logger.debug(f"Marked {identifier} as processed in Redis with TTL={ttl}s")
            else:
                self._client.set(key, "1")  # type: ignore
                logger.debug(f"Marked {identifier} as processed in Redis (no TTL)")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis error marking as processed: identifier={identifier}, error_type={type(e).__name__}, error={str(e)}")
            self._connected = False

    def mark_unprocessed(self, identifier: str):
        """
        Remove a vCon from processed tracking (for retry scenarios).

        Args:
            identifier: vCon UUID or S3 key
        """
        if not self.enabled or not self._connected:
            return
        
        try:
            key = self._make_key(identifier)
            self._client.delete(key)  # type: ignore
            logger.debug(f"Removed {identifier} from processed tracking")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis error removing from processed: {e}")
            self._connected = False

    def get_processed_count(self) -> int:
        """
        Get count of processed vCons.

        Returns:
            Number of processed vCons
        """
        if not self.enabled or not self._connected:
            return 0
        
        try:
            pattern = self._make_key("*")
            keys = self._client.keys(pattern)  # type: ignore
            return len(keys)
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis error getting processed count: {e}")
            return 0

    def clear_all(self):
        """Clear all processed tracking (use with caution)."""
        if not self.enabled or not self._connected:
            return
        
        try:
            pattern = self._make_key("*")
            keys = self._client.keys(pattern)  # type: ignore
            if keys:
                self._client.delete(*keys)  # type: ignore
                logger.info(f"Cleared {len(keys)} processed entries from Redis")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis error clearing all: {e}")

    def is_available(self) -> bool:
        """
        Check if Redis is available.

        Returns:
            True if Redis is connected and available
        """
        if not self.enabled:
            return False
        
        if not self._connected:
            return False
        
        try:
            self._client.ping()  # type: ignore
            return True
        except (RedisError, ConnectionError):
            self._connected = False
            return False

