"""Metrics tracking for monitoring processing performance."""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class Metrics:
    """Metrics tracker for processing statistics."""

    def __init__(self):
        """Initialize metrics tracker."""
        self.start_time = datetime.now()
        self.processed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.validation_error_count = 0
        self.redis_unavailable_count = 0
        
        # Timing metrics
        self.processing_times: list[float] = []
        self.last_processed_time: Optional[datetime] = None
        
        # Error tracking
        self.error_types: Dict[str, int] = defaultdict(int)
        
        # Date tracking
        self.dates_processed: set[str] = set()
        self.last_processed_date: Optional[str] = None

    def record_processed(self, processing_time: Optional[float] = None):
        """
        Record a successfully processed vCon.

        Args:
            processing_time: Optional processing time in seconds
        """
        self.processed_count += 1
        self.last_processed_time = datetime.now()
        if processing_time is not None:
            self.processing_times.append(processing_time)

    def record_error(self, error_type: str = "unknown"):
        """
        Record an error.

        Args:
            error_type: Type of error
        """
        self.error_count += 1
        self.error_types[error_type] += 1

    def record_skipped(self):
        """Record a skipped vCon."""
        self.skipped_count += 1

    def record_validation_error(self):
        """Record a validation error."""
        self.validation_error_count += 1

    def record_redis_unavailable(self):
        """Record when Redis is unavailable."""
        self.redis_unavailable_count += 1

    def record_date_processed(self, date_str: str):
        """
        Record a processed date.

        Args:
            date_str: Date string in YYYY-MM-DD format
        """
        self.dates_processed.add(date_str)
        self.last_processed_date = date_str

    def get_success_rate(self) -> float:
        """
        Calculate success rate.

        Returns:
            Success rate as a float between 0 and 1
        """
        total = self.processed_count + self.error_count
        if total == 0:
            return 0.0
        return self.processed_count / total

    def get_average_processing_time(self) -> Optional[float]:
        """
        Get average processing time.

        Returns:
            Average processing time in seconds, or None if no data
        """
        if not self.processing_times:
            return None
        return sum(self.processing_times) / len(self.processing_times)

    def get_runtime_seconds(self) -> float:
        """
        Get total runtime in seconds.

        Returns:
            Runtime in seconds
        """
        return (datetime.now() - self.start_time).total_seconds()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get metrics summary.

        Returns:
            Dictionary with all metrics
        """
        return {
            "runtime_seconds": self.get_runtime_seconds(),
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "validation_error_count": self.validation_error_count,
            "redis_unavailable_count": self.redis_unavailable_count,
            "success_rate": self.get_success_rate(),
            "average_processing_time": self.get_average_processing_time(),
            "error_types": dict(self.error_types),
            "dates_processed_count": len(self.dates_processed),
            "last_processed_date": self.last_processed_date,
            "last_processed_time": (
                self.last_processed_time.isoformat() if self.last_processed_time else None
            ),
        }

    def reset(self):
        """Reset all metrics."""
        self.start_time = datetime.now()
        self.processed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.validation_error_count = 0
        self.redis_unavailable_count = 0
        self.processing_times.clear()
        self.error_types.clear()
        self.dates_processed.clear()
        self.last_processed_time = None
        self.last_processed_date = None

