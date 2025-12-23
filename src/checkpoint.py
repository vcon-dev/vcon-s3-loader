"""Checkpoint management for saving/restoring processing state."""

import logging
import json
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, date

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint files for resuming processing after restarts."""

    def __init__(self, checkpoint_file: str):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_file: Path to checkpoint file
        """
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_data: Dict[str, Any] = {}

    def load(self) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint from file.

        Returns:
            Checkpoint data dictionary, or None if file doesn't exist
        """
        if not self.checkpoint_file.exists():
            logger.info(f"Checkpoint file {self.checkpoint_file} does not exist")
            return None
        
        try:
            with open(self.checkpoint_file, "r") as f:
                data = json.load(f)
                self.checkpoint_data = data
                logger.info(f"Loaded checkpoint from {self.checkpoint_file}")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing checkpoint file {self.checkpoint_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading checkpoint file {self.checkpoint_file}: {e}")
            return None

    def save(self, data: Dict[str, Any]):
        """
        Save checkpoint to file.

        Args:
            data: Checkpoint data to save
        """
        try:
            # Add timestamp
            data["last_updated"] = datetime.now().isoformat()
            
            # Ensure directory exists
            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.checkpoint_file.with_suffix(self.checkpoint_file.suffix + ".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            
            temp_file.replace(self.checkpoint_file)
            self.checkpoint_data = data
            logger.debug(f"Saved checkpoint to {self.checkpoint_file}")
        except Exception as e:
            logger.error(f"Error saving checkpoint to {self.checkpoint_file}: {e}")
            raise

    def get_last_processed_date(self) -> Optional[date]:
        """
        Get the last processed date from checkpoint.

        Returns:
            Last processed date, or None if not found
        """
        if not self.checkpoint_data:
            self.load()
        
        date_str = self.checkpoint_data.get("last_processed_date")
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid date format in checkpoint: {date_str}")
        return None

    def set_last_processed_date(self, date_obj: date):
        """
        Set the last processed date in checkpoint.

        Args:
            date_obj: Date to save
        """
        if not self.checkpoint_data:
            self.checkpoint_data = {}
        
        self.checkpoint_data["last_processed_date"] = date_obj.strftime("%Y-%m-%d")
        self.save(self.checkpoint_data)

    def get_last_processed_key(self) -> Optional[str]:
        """
        Get the last processed S3 key from checkpoint.

        Returns:
            Last processed S3 key, or None if not found
        """
        if not self.checkpoint_data:
            self.load()
        
        return self.checkpoint_data.get("last_processed_key")

    def set_last_processed_key(self, key: str):
        """
        Set the last processed S3 key in checkpoint.

        Args:
            key: S3 key to save
        """
        if not self.checkpoint_data:
            self.checkpoint_data = {}
        
        self.checkpoint_data["last_processed_key"] = key
        self.save(self.checkpoint_data)

    def get_processed_keys(self) -> list[str]:
        """
        Get list of processed S3 keys from checkpoint.

        Returns:
            List of processed S3 keys
        """
        if not self.checkpoint_data:
            self.load()
        
        return self.checkpoint_data.get("processed_keys", [])

    def add_processed_key(self, key: str):
        """
        Add a processed S3 key to checkpoint.

        Args:
            key: S3 key to add
        """
        if not self.checkpoint_data:
            self.checkpoint_data = {}
        
        processed_keys = self.checkpoint_data.get("processed_keys", [])
        if key not in processed_keys:
            processed_keys.append(key)
            self.checkpoint_data["processed_keys"] = processed_keys
            self.save(self.checkpoint_data)

    def clear(self):
        """Clear checkpoint data."""
        self.checkpoint_data = {}
        if self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                logger.info(f"Cleared checkpoint file {self.checkpoint_file}")
            except Exception as e:
                logger.error(f"Error clearing checkpoint file: {e}")

