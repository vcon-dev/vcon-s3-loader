"""Tests for date processor."""

import pytest
from datetime import date, timedelta
from src.date_processor import DateProcessor


def test_date_range():
    """Test generating date range."""
    processor = DateProcessor(start_date="2024-01-01")
    dates = list(processor.date_range(date(2024, 1, 5)))
    
    assert len(dates) == 5
    assert dates[0] == date(2024, 1, 1)
    assert dates[4] == date(2024, 1, 5)


def test_mark_processed():
    """Test marking dates as processed."""
    processor = DateProcessor(start_date="2024-01-01")
    test_date = date(2024, 1, 15)
    
    assert processor.is_processed(test_date) is False
    processor.mark_processed(test_date)
    assert processor.is_processed(test_date) is True


def test_get_unprocessed_dates():
    """Test getting unprocessed dates."""
    processor = DateProcessor(start_date="2024-01-01")
    processor.mark_processed(date(2024, 1, 2))
    processor.mark_processed(date(2024, 1, 4))
    
    unprocessed = processor.get_unprocessed_dates(date(2024, 1, 5))
    assert date(2024, 1, 1) in unprocessed
    assert date(2024, 1, 2) not in unprocessed
    assert date(2024, 1, 3) in unprocessed
    assert date(2024, 1, 4) not in unprocessed
    assert date(2024, 1, 5) in unprocessed


def test_get_next_unprocessed_date():
    """Test getting next unprocessed date."""
    processor = DateProcessor(start_date="2024-01-01")
    processor.mark_processed(date(2024, 1, 1))
    
    next_date = processor.get_next_unprocessed_date(date(2024, 1, 5))
    assert next_date == date(2024, 1, 2)


def test_get_processed_count():
    """Test getting processed count."""
    processor = DateProcessor(start_date="2024-01-01")
    
    assert processor.get_processed_count() == 0
    processor.mark_processed(date(2024, 1, 1))
    processor.mark_processed(date(2024, 1, 2))
    assert processor.get_processed_count() == 2


def test_reset_processed():
    """Test resetting processed dates."""
    processor = DateProcessor(start_date="2024-01-01")
    processor.mark_processed(date(2024, 1, 1))
    
    assert processor.get_processed_count() == 1
    processor.reset_processed()
    assert processor.get_processed_count() == 0

