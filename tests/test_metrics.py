"""Tests for metrics tracking."""

import pytest
import time
from src.metrics import Metrics


def test_record_processed():
    """Test recording processed vCon."""
    metrics = Metrics()
    
    assert metrics.processed_count == 0
    metrics.record_processed(processing_time=0.5)
    assert metrics.processed_count == 1
    assert len(metrics.processing_times) == 1


def test_record_error():
    """Test recording error."""
    metrics = Metrics()
    
    assert metrics.error_count == 0
    metrics.record_error("test_error")
    assert metrics.error_count == 1
    assert metrics.error_types["test_error"] == 1


def test_record_skipped():
    """Test recording skipped vCon."""
    metrics = Metrics()
    
    assert metrics.skipped_count == 0
    metrics.record_skipped()
    assert metrics.skipped_count == 1


def test_get_success_rate():
    """Test calculating success rate."""
    metrics = Metrics()
    
    metrics.record_processed()
    metrics.record_processed()
    metrics.record_error("error")
    
    success_rate = metrics.get_success_rate()
    assert success_rate == pytest.approx(2/3)


def test_get_average_processing_time():
    """Test getting average processing time."""
    metrics = Metrics()
    
    metrics.record_processed(processing_time=1.0)
    metrics.record_processed(processing_time=2.0)
    metrics.record_processed(processing_time=3.0)
    
    avg_time = metrics.get_average_processing_time()
    assert avg_time == pytest.approx(2.0)


def test_get_summary():
    """Test getting metrics summary."""
    metrics = Metrics()
    
    metrics.record_processed(processing_time=1.0)
    metrics.record_error("test_error")
    metrics.record_date_processed("2024-01-01")
    
    summary = metrics.get_summary()
    
    assert summary["processed_count"] == 1
    assert summary["error_count"] == 1
    assert summary["success_rate"] == pytest.approx(0.5)
    assert summary["average_processing_time"] == 1.0
    assert summary["dates_processed_count"] == 1
    assert "test_error" in summary["error_types"]


def test_reset():
    """Test resetting metrics."""
    metrics = Metrics()
    
    metrics.record_processed()
    metrics.record_error("error")
    metrics.record_date_processed("2024-01-01")
    
    metrics.reset()
    
    assert metrics.processed_count == 0
    assert metrics.error_count == 0
    assert len(metrics.dates_processed) == 0

