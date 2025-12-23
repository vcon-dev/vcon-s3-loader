"""Date range processor for generating and tracking processed dates."""

import logging
from typing import List, Iterator, Optional
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)


class DateProcessor:
    """Processor for generating date ranges and tracking processed dates."""

    def __init__(self, start_date: str):
        """
        Initialize date processor.

        Args:
            start_date: Start date in YYYY-MM-DD format
        """
        try:
            self.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD") from e
        
        self.processed_dates: set[date] = set()

    def date_range(self, end_date: Optional[date] = None) -> Iterator[date]:
        """
        Generate date range from start_date to end_date.

        Args:
            end_date: End date (defaults to today)

        Yields:
            Dates in the range
        """
        if end_date is None:
            end_date = date.today()
        
        current = self.start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)

    def get_all_dates(self, end_date: Optional[date] = None) -> List[date]:
        """
        Get all dates from start_date to end_date as a list.

        Args:
            end_date: End date (defaults to today)

        Returns:
            List of dates
        """
        return list(self.date_range(end_date))

    def mark_processed(self, date_obj: date):
        """
        Mark a date as processed.

        Args:
            date_obj: Date to mark as processed
        """
        self.processed_dates.add(date_obj)
        logger.debug(f"Marked date {date_obj} as processed")

    def is_processed(self, date_obj: date) -> bool:
        """
        Check if a date has been processed.

        Args:
            date_obj: Date to check

        Returns:
            True if processed, False otherwise
        """
        return date_obj in self.processed_dates

    def get_unprocessed_dates(self, end_date: Optional[date] = None) -> List[date]:
        """
        Get list of unprocessed dates.

        Args:
            end_date: End date (defaults to today)

        Returns:
            List of unprocessed dates
        """
        all_dates = self.get_all_dates(end_date)
        return [d for d in all_dates if not self.is_processed(d)]

    def get_next_unprocessed_date(self, end_date: Optional[date] = None) -> Optional[date]:
        """
        Get the next unprocessed date.

        Args:
            end_date: End date (defaults to today)

        Returns:
            Next unprocessed date, or None if all dates are processed
        """
        unprocessed = self.get_unprocessed_dates(end_date)
        return unprocessed[0] if unprocessed else None

    def reset_processed(self):
        """Reset all processed dates."""
        self.processed_dates.clear()
        logger.info("Reset all processed dates")

    def get_processed_count(self) -> int:
        """
        Get count of processed dates.

        Returns:
            Number of processed dates
        """
        return len(self.processed_dates)

