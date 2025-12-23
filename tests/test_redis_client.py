"""Tests for Redis client."""

import pytest
from unittest.mock import Mock, patch
from redis.exceptions import RedisError, ConnectionError
from src.redis_client import RedisClient


def test_redis_client_enabled():
    """Test Redis client when enabled and connected."""
    with patch("src.redis_client.redis") as mock_redis:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.exists.return_value = True
        mock_redis.from_url.return_value = mock_client
        
        client = RedisClient(redis_url="redis://localhost:6379", enabled=True)
        assert client.is_available() is True
        assert client.is_processed("test-id") is True


def test_redis_client_disabled():
    """Test Redis client when disabled."""
    client = RedisClient(redis_url="redis://localhost:6379", enabled=False)
    assert client.is_available() is False
    assert client.is_processed("test-id") is False


def test_redis_client_connection_failure():
    """Test Redis client when connection fails."""
    with patch("src.redis_client.redis") as mock_redis:
        mock_redis.from_url.side_effect = ConnectionError("Connection failed")
        
        client = RedisClient(redis_url="redis://localhost:6379", enabled=True)
        assert client.is_available() is False
        assert client.is_processed("test-id") is False


def test_mark_processed():
    """Test marking vCon as processed."""
    with patch("src.redis_client.redis") as mock_redis:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client
        
        client = RedisClient(redis_url="redis://localhost:6379", enabled=True)
        client.mark_processed("test-id")
        
        mock_client.set.assert_called_once()


def test_mark_unprocessed():
    """Test removing vCon from processed tracking."""
    with patch("src.redis_client.redis") as mock_redis:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.from_url.return_value = mock_client
        
        client = RedisClient(redis_url="redis://localhost:6379", enabled=True)
        client.mark_unprocessed("test-id")
        
        mock_client.delete.assert_called_once()


def test_get_processed_count():
    """Test getting processed count."""
    with patch("src.redis_client.redis") as mock_redis:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.from_url.return_value = mock_client
        
        client = RedisClient(redis_url="redis://localhost:6379", enabled=True)
        count = client.get_processed_count()
        assert count == 3

