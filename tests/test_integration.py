"""Integration tests for vCon S3 Loader."""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime, date
from moto import mock_aws
import boto3
from src.config import Config
from src.s3_client import S3Client
from src.redis_client import RedisClient
from src.http_client import HTTPClient
from src.rate_limiter import RateLimiter
from src.date_processor import DateProcessor
from src.checkpoint import CheckpointManager
from src.vcon_loader import VConLoader
from src.metrics import Metrics


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def s3_bucket(aws_credentials):
    """Create S3 bucket with test data."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-vcon-bucket"
        s3.create_bucket(Bucket=bucket_name)
        
        # Add test vCon files
        vcon_data = {
            "vcon": "0.0.1",
            "uuid": "test-uuid-1",
            "created_at": "2024-01-15T10:00:00Z",
            "parties": [{"name": "Alice"}],
            "dialog": []
        }
        
        # Add files for different dates
        s3.put_object(
            Bucket=bucket_name,
            Key="vcons/2024/01/15/vcon1.json",
            Body=json.dumps(vcon_data).encode("utf-8")
        )
        
        vcon_data2 = vcon_data.copy()
        vcon_data2["uuid"] = "test-uuid-2"
        s3.put_object(
            Bucket=bucket_name,
            Key="vcons/2024/01/16/vcon2.json",
            Body=json.dumps(vcon_data2).encode("utf-8")
        )
        
        yield bucket_name


def test_s3_client_integration(s3_bucket):
    """Test S3 client integration with moto."""
    client = S3Client(bucket_name=s3_bucket, prefix="vcons/", region="us-east-1")
    
    # Test listing objects by date
    date_obj = datetime(2024, 1, 15)
    objects = client.list_objects_by_date(date_obj)
    assert len(objects) == 1
    assert "vcons/2024/01/15/vcon1.json" in objects
    
    # Test downloading JSON
    vcon_data = client.download_json("vcons/2024/01/15/vcon1.json")
    assert vcon_data is not None
    assert vcon_data["uuid"] == "test-uuid-1"


def test_redis_client_integration():
    """Test Redis client integration (requires Redis or fakeredis)."""
    try:
        import fakeredis
        from unittest.mock import patch
        
        # Use fakeredis for testing
        with patch("src.redis_client.redis") as mock_redis_module:
            fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)
            mock_redis_module.from_url.return_value = fake_redis
            
            redis_url = "redis://localhost:6379"
            client = RedisClient(redis_url=redis_url, enabled=True)
            
            # Test marking and checking processed
            assert client.is_processed("test-id") is False
            client.mark_processed("test-id")
            assert client.is_processed("test-id") is True
            
            # Test count
            count = client.get_processed_count()
            assert count >= 1
    except ImportError:
        pytest.skip("fakeredis not available")


def test_date_processor_integration():
    """Test date processor integration."""
    processor = DateProcessor(start_date="2024-01-01")
    
    # Process dates
    dates = processor.get_all_dates(date(2024, 1, 5))
    assert len(dates) == 5
    
    # Mark some as processed
    processor.mark_processed(date(2024, 1, 2))
    processor.mark_processed(date(2024, 1, 4))
    
    # Get unprocessed
    unprocessed = processor.get_unprocessed_dates(date(2024, 1, 5))
    assert date(2024, 1, 2) not in unprocessed
    assert date(2024, 1, 3) in unprocessed


def test_checkpoint_integration():
    """Test checkpoint manager integration."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    
    try:
        manager = CheckpointManager(temp_path)
        
        # Save checkpoint
        manager.set_last_processed_date(date(2024, 1, 15))
        manager.set_last_processed_key("test-key.json")
        
        # Load checkpoint
        manager2 = CheckpointManager(temp_path)
        loaded_date = manager2.get_last_processed_date()
        loaded_key = manager2.get_last_processed_key()
        
        assert loaded_date == date(2024, 1, 15)
        assert loaded_key == "test-key.json"
    finally:
        import os
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_metrics_integration():
    """Test metrics integration."""
    metrics = Metrics()
    
    # Record various events
    metrics.record_processed(processing_time=1.0)
    metrics.record_processed(processing_time=2.0)
    metrics.record_error("test_error")
    metrics.record_skipped()
    metrics.record_date_processed("2024-01-15")
    
    # Get summary
    summary = metrics.get_summary()
    
    assert summary["processed_count"] == 2
    assert summary["error_count"] == 1
    assert summary["skipped_count"] == 1
    assert summary["success_rate"] == pytest.approx(2/3)
    assert summary["average_processing_time"] == 1.5
    assert summary["dates_processed_count"] == 1


@patch("src.http_client.requests.post")
def test_http_client_integration(mock_post):
    """Test HTTP client integration."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    client = HTTPClient(
        url="https://api.example.com/vcons",
        headers={"Authorization": "Bearer token"},
        retry_attempts=1,
    )
    
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    result = client.post_vcon(vcon_data)
    
    assert result is True
    mock_post.assert_called_once()


def test_rate_limiter_integration():
    """Test rate limiter integration."""
    import time
    limiter = RateLimiter(requests_per_second=10.0)
    
    # Acquire tokens
    acquired = 0
    for _ in range(15):
        if limiter.acquire():
            acquired += 1
    
    # Should acquire up to rate limit
    assert acquired <= 10
    
    # Wait should eventually succeed (wait refills tokens and acquires one)
    # After wait() completes, it has already acquired a token, so we need
    # to wait a bit more for another token to be available
    limiter.wait()
    # Wait for token refill (0.1 seconds for 1 token at 10/sec)
    time.sleep(0.11)
    assert limiter.acquire() is True

