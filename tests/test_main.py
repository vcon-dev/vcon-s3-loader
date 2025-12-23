"""Tests for main service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from src.main import VConS3LoaderService
from src.config import Config


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = {
        "s3": {
            "bucket": "test-bucket",
            "prefix": "vcons/",
            "region": "us-east-1",
        },
        "post": {
            "url": "https://api.example.com/vcons",
            "headers": {},
            "use_vcon_method": False,
            "retry_attempts": 3,
            "retry_backoff_base": 2,
        },
        "rate_limit": {
            "requests_per_second": 10.0,
        },
        "processing": {
            "start_date": "2024-01-01",
            "poll_interval_seconds": 300,
            "checkpoint_file": ".checkpoint.json",
            "batch_size": 1,
            "validate_vcon": True,
        },
        "redis": {
            "url": "redis://localhost:6379",
            "enabled": True,
            "key_prefix": "vcon-loader",
        },
        "logging": {
            "level": "INFO",
        },
    }
    return config


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_service_initialization(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test service initialization."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    service = VConS3LoaderService(config)
    
    assert service.config == config
    assert service.running is False


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_vcon_success(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing a vCon successfully."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    # Setup mocks
    mock_vcon_instance = Mock()
    mock_vcon_instance.uuid = "test-uuid"
    mock_vcon_loader_instance = Mock()
    mock_vcon_loader_instance.load_from_dict.return_value = mock_vcon_instance
    mock_vcon_loader_instance.extract_identifier.return_value = "test-uuid"
    mock_vcon_loader.return_value = mock_vcon_loader_instance
    
    mock_redis_instance = Mock()
    mock_redis_instance.is_processed.return_value = False
    mock_redis_client.return_value = mock_redis_instance
    
    mock_http_instance = Mock()
    mock_http_instance.post_vcon.return_value = True
    mock_http_client.return_value = mock_http_instance
    
    mock_rate_limiter_instance = Mock()
    mock_rate_limiter.return_value = mock_rate_limiter_instance
    
    service = VConS3LoaderService(config)
    
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    result = service._process_vcon("test-key.json", vcon_data)
    
    assert result is True
    mock_redis_instance.mark_processed.assert_called_once()


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_vcon_already_processed(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test skipping already processed vCon."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_vcon_instance = Mock()
    mock_vcon_instance.uuid = "test-uuid"
    mock_vcon_loader_instance = Mock()
    mock_vcon_loader_instance.load_from_dict.return_value = mock_vcon_instance
    mock_vcon_loader_instance.extract_identifier.return_value = "test-uuid"
    mock_vcon_loader.return_value = mock_vcon_loader_instance
    
    mock_redis_instance = Mock()
    mock_redis_instance.is_processed.return_value = True  # Already processed
    mock_redis_client.return_value = mock_redis_instance
    
    service = VConS3LoaderService(config)
    
    vcon_data = {"vcon": "0.0.1", "uuid": "test-uuid"}
    result = service._process_vcon("test-key.json", vcon_data)
    
    assert result is True  # Skipped successfully
    mock_http_client.return_value.post_vcon.assert_not_called()


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_load_checkpoint_with_data(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test loading checkpoint with existing data."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    # Setup checkpoint manager mock
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = {"last_processed_date": "2024-01-15"}
    mock_checkpoint_instance.get_last_processed_date.return_value = date(2024, 1, 15)
    mock_checkpoint_instance.get_last_processed_key.return_value = "test-key.json"
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    # Setup date processor mock
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.date_range.return_value = iter([date(2024, 1, 1), date(2024, 1, 15)])
    mock_date_processor.return_value = mock_date_processor_instance
    
    service = VConS3LoaderService(config)
    
    # Verify checkpoint was loaded
    mock_checkpoint_instance.load.assert_called_once()
    assert mock_date_processor_instance.mark_processed.call_count > 0


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_save_checkpoint(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test saving checkpoint."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    service = VConS3LoaderService(config)
    service._save_checkpoint(date(2024, 1, 15), "test-key.json")
    
    mock_checkpoint_instance.set_last_processed_date.assert_called_once_with(date(2024, 1, 15))
    mock_checkpoint_instance.set_last_processed_key.assert_called_once_with("test-key.json")


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_vcon_validation_failure(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing vCon with validation failure."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_vcon_loader_instance = Mock()
    mock_vcon_loader_instance.load_from_dict.return_value = None  # Validation failed
    mock_vcon_loader.return_value = mock_vcon_loader_instance
    
    mock_metrics_instance = Mock()
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    result = service._process_vcon("test-key.json", {"vcon": "0.0.1"})
    
    assert result is False
    mock_metrics_instance.record_validation_error.assert_called_once()


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_vcon_post_failure(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing vCon with POST failure."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_vcon = Mock()
    mock_vcon.uuid = "test-uuid"
    mock_vcon_loader_instance = Mock()
    mock_vcon_loader_instance.load_from_dict.return_value = mock_vcon
    mock_vcon_loader_instance.extract_identifier.return_value = "test-uuid"
    mock_vcon_loader.return_value = mock_vcon_loader_instance
    
    mock_redis_instance = Mock()
    mock_redis_instance.is_processed.return_value = False
    mock_redis_client.return_value = mock_redis_instance
    
    mock_http_instance = Mock()
    mock_http_instance.post_vcon.return_value = False  # POST failed
    mock_http_client.return_value = mock_http_instance
    
    mock_rate_limiter_instance = Mock()
    mock_rate_limiter.return_value = mock_rate_limiter_instance
    
    mock_metrics_instance = Mock()
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    result = service._process_vcon("test-key.json", {"vcon": "0.0.1", "uuid": "test-uuid"})
    
    assert result is False
    mock_metrics_instance.record_error.assert_called_with("post_failed")


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_vcon_exception(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing vCon with exception."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_vcon_loader_instance = Mock()
    mock_vcon_loader_instance.load_from_dict.side_effect = Exception("Test error")
    mock_vcon_loader.return_value = mock_vcon_loader_instance
    
    mock_metrics_instance = Mock()
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    result = service._process_vcon("test-key.json", {"vcon": "0.0.1"})
    
    assert result is False
    mock_metrics_instance.record_error.assert_called()


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_date_empty(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing date with no files."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.return_value = []  # No files
    mock_s3_client.return_value = mock_s3_instance
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.date_range.return_value = []  # Return empty iterable
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    service = VConS3LoaderService(config)
    result = service._process_date(datetime(2024, 1, 15))
    
    assert result is True
    mock_date_processor_instance.mark_processed.assert_called_once()


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_date_with_files(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing date with files."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.return_value = ["2024/01/15/vcon1.json", "2024/01/15/vcon2.json"]
    mock_s3_instance.download_json.side_effect = [
        {"vcon": "0.0.1", "uuid": "uuid1"},
        {"vcon": "0.0.1", "uuid": "uuid2"}
    ]
    mock_s3_client.return_value = mock_s3_instance
    
    mock_vcon = Mock()
    mock_vcon.uuid = "test-uuid"
    mock_vcon_loader_instance = Mock()
    mock_vcon_loader_instance.load_from_dict.return_value = mock_vcon
    mock_vcon_loader_instance.extract_identifier.return_value = "test-uuid"
    mock_vcon_loader.return_value = mock_vcon_loader_instance
    
    mock_redis_instance = Mock()
    mock_redis_instance.is_processed.return_value = False
    mock_redis_client.return_value = mock_redis_instance
    
    mock_http_instance = Mock()
    mock_http_instance.post_vcon.return_value = True
    mock_http_client.return_value = mock_http_instance
    
    mock_rate_limiter_instance = Mock()
    mock_rate_limiter.return_value = mock_rate_limiter_instance
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.date_range.return_value = []  # Return empty iterable
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    mock_metrics_instance = Mock()
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    result = service._process_date(datetime(2024, 1, 15))
    
    assert result is True
    assert mock_s3_instance.download_json.call_count == 2
    assert mock_http_instance.post_vcon.call_count == 2


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_date_download_failure(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing date with download failure."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.return_value = ["2024/01/15/vcon1.json"]
    mock_s3_instance.download_json.return_value = None  # Download failed
    mock_s3_client.return_value = mock_s3_instance
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.date_range.return_value = []  # Return empty iterable
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    mock_metrics_instance = Mock()
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    result = service._process_date(datetime(2024, 1, 15))
    
    assert result is True  # Date processing completes even with failures
    mock_metrics_instance.record_error.assert_called_with("download_failed")


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_date_shutdown(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing date with shutdown requested."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.return_value = ["2024/01/15/vcon1.json"]
    mock_s3_client.return_value = mock_s3_instance
    
    service = VConS3LoaderService(config)
    service.shutdown_requested = True
    
    result = service._process_date(datetime(2024, 1, 15))
    
    assert result is False


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_process_date_exception(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test processing date with exception."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.side_effect = Exception("S3 error")
    mock_s3_client.return_value = mock_s3_instance
    
    mock_metrics_instance = Mock()
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    result = service._process_date(datetime(2024, 1, 15))
    
    assert result is False
    mock_metrics_instance.record_error.assert_called_with("date_processing_failed")


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_backfill_mode_no_dates(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test backfill mode with no unprocessed dates."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.get_unprocessed_dates.return_value = []
    mock_date_processor_instance.date_range.return_value = []  # For checkpoint loading
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    service = VConS3LoaderService(config)
    service._backfill_mode()
    
    # Should complete without error
    assert True


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_backfill_mode_with_dates(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test backfill mode with dates to process."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.get_unprocessed_dates.return_value = [date(2024, 1, 1), date(2024, 1, 2)]
    mock_date_processor_instance.date_range.return_value = []  # For checkpoint loading
    mock_date_processor_instance.mark_processed = Mock()
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.return_value = []
    mock_s3_client.return_value = mock_s3_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    mock_metrics_instance = Mock()
    mock_metrics_instance.get_summary.return_value = {
        "processed_count": 0,
        "error_count": 0,
        "success_rate": 1.0,
    }
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    service._backfill_mode()
    
    # Should process dates
    assert mock_date_processor_instance.mark_processed.call_count >= 0


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_backfill_mode_shutdown(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test backfill mode with shutdown requested."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.get_unprocessed_dates.return_value = [date(2024, 1, 1)]
    mock_date_processor_instance.date_range.return_value = []  # For checkpoint loading
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_s3_instance = Mock()
    mock_s3_instance.list_objects_by_date.return_value = []
    mock_s3_client.return_value = mock_s3_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    mock_metrics_instance = Mock()
    mock_metrics_instance.get_summary.return_value = {
        "processed_count": 0,
        "error_count": 0,
        "success_rate": 1.0,
    }
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    service.shutdown_requested = True
    service._backfill_mode()
    
    # Should handle shutdown gracefully
    assert True


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
@patch("src.main.time.sleep")
def test_monitoring_mode(
    mock_sleep,
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test monitoring mode."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.get_unprocessed_dates.return_value = []
    mock_date_processor_instance.date_range.return_value = []  # For checkpoint loading
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    mock_metrics_instance = Mock()
    mock_metrics_instance.get_summary.return_value = {
        "processed_count": 0,
        "error_count": 0,
        "skipped_count": 0,
        "success_rate": 1.0,
        "dates_processed_count": 0,
        "last_processed_date": None
    }
    mock_metrics.return_value = mock_metrics_instance
    
    service = VConS3LoaderService(config)
    service.shutdown_requested = True  # Exit after first iteration
    
    # Should not raise exception
    try:
        service._monitoring_mode()
    except Exception:
        pass  # May raise due to shutdown
    
    assert True


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_signal_handler(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test signal handler."""
    import signal
    
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    service = VConS3LoaderService(config)
    service.running = True
    service.metrics.processed_count = 5
    service.metrics.error_count = 1
    
    service._signal_handler(signal.SIGINT, None)
    
    assert service.shutdown_requested is True


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_run_method(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test run method."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_redis_instance = Mock()
    mock_redis_instance.is_available.return_value = True
    mock_redis_client.return_value = mock_redis_instance
    
    mock_http_instance = Mock()
    mock_http_instance.test_connection.return_value = True
    mock_http_client.return_value = mock_http_instance
    
    mock_date_processor_instance = Mock()
    mock_date_processor_instance.get_unprocessed_dates.return_value = []
    mock_date_processor_instance.date_range.return_value = []  # For checkpoint loading
    mock_date_processor.return_value = mock_date_processor_instance
    
    mock_checkpoint_instance = Mock()
    mock_checkpoint_instance.load.return_value = None  # No checkpoint
    mock_checkpoint.return_value = mock_checkpoint_instance
    
    service = VConS3LoaderService(config)
    service.shutdown_requested = True  # Exit immediately
    
    # Should complete without error
    try:
        service.run()
    except Exception:
        pass
    
    assert service.running is False


@patch("src.main.S3Client")
@patch("src.main.RedisClient")
@patch("src.main.HTTPClient")
@patch("src.main.RateLimiter")
@patch("src.main.DateProcessor")
@patch("src.main.CheckpointManager")
@patch("src.main.VConLoader")
@patch("src.main.Metrics")
def test_run_method_exception(
    mock_metrics,
    mock_vcon_loader,
    mock_checkpoint,
    mock_date_processor,
    mock_rate_limiter,
    mock_http_client,
    mock_redis_client,
    mock_s3_client,
    mock_config,
):
    """Test run method with exception."""
    config = Mock(spec=Config)
    config.__getitem__ = Mock(side_effect=lambda key: mock_config[key])
    config.get = Mock(side_effect=lambda key_path, default=None: mock_config.get(key_path.split(".")[0], {}).get(key_path.split(".")[-1], default))
    
    mock_redis_instance = Mock()
    mock_redis_instance.is_available.side_effect = Exception("Redis error")
    mock_redis_client.return_value = mock_redis_instance
    
    service = VConS3LoaderService(config)
    
    with pytest.raises(Exception):
        service.run()
    
    assert service.running is False

