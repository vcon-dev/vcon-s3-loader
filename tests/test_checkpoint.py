"""Tests for checkpoint manager."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import date
from src.checkpoint import CheckpointManager


def test_checkpoint_save_load():
    """Test saving and loading checkpoint."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    
    try:
        manager = CheckpointManager(temp_path)
        manager.set_last_processed_date(date(2024, 1, 15))
        manager.set_last_processed_key("test-key.json")
        
        # Create new manager to test loading
        manager2 = CheckpointManager(temp_path)
        loaded_date = manager2.get_last_processed_date()
        loaded_key = manager2.get_last_processed_key()
        
        assert loaded_date == date(2024, 1, 15)
        assert loaded_key == "test-key.json"
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_checkpoint_add_processed_key():
    """Test adding processed keys."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    
    try:
        manager = CheckpointManager(temp_path)
        manager.add_processed_key("key1.json")
        manager.add_processed_key("key2.json")
        
        keys = manager.get_processed_keys()
        assert "key1.json" in keys
        assert "key2.json" in keys
        assert len(keys) == 2
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_checkpoint_load_nonexistent():
    """Test loading nonexistent checkpoint."""
    manager = CheckpointManager("/nonexistent/path/checkpoint.json")
    data = manager.load()
    assert data is None


def test_checkpoint_clear():
    """Test clearing checkpoint."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    
    try:
        manager = CheckpointManager(temp_path)
        manager.set_last_processed_date(date(2024, 1, 15))
        manager.clear()
        
        assert not Path(temp_path).exists()
    finally:
        Path(temp_path).unlink(missing_ok=True)

