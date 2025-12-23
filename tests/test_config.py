"""Tests for configuration management."""

import os
import pytest
import tempfile
import yaml
from pathlib import Path
from src.config import Config


def test_config_defaults():
    """Test default configuration values."""
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    os.environ["POST_URL"] = "https://api.example.com/vcons"
    os.environ["START_DATE"] = "2024-01-01"
    
    config = Config()
    assert config["s3"]["bucket"] == "test-bucket"
    assert config["post"]["url"] == "https://api.example.com/vcons"
    assert config["processing"]["start_date"] == "2024-01-01"


def test_config_from_file():
    """Test loading configuration from YAML file."""
    # Clear env vars to test file config
    env_vars_to_clear = ["S3_BUCKET_NAME", "POST_URL", "START_DATE"]
    saved_env = {k: os.environ.get(k) for k in env_vars_to_clear}
    for k in env_vars_to_clear:
        if k in os.environ:
            del os.environ[k]
    
    try:
        config_data = {
            "s3": {
                "bucket": "file-bucket",
                "prefix": "vcons/",
            },
            "post": {
                "url": "https://file-api.example.com/vcons",
                "headers": {
                    "Authorization": "Bearer token123"
                }
            },
            "processing": {
                "start_date": "2024-01-01"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = Config(config_file=temp_path)
            assert config["s3"]["bucket"] == "file-bucket"
            assert config["s3"]["prefix"] == "vcons/"
            assert config["post"]["url"] == "https://file-api.example.com/vcons"
            assert config["post"]["headers"]["Authorization"] == "Bearer token123"
        finally:
            Path(temp_path).unlink()
    finally:
        # Restore env vars
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v


def test_config_validation():
    """Test configuration validation."""
    # Clear env vars first
    env_vars_to_clear = ["S3_BUCKET_NAME", "POST_URL", "START_DATE"]
    saved_env = {k: os.environ.get(k) for k in env_vars_to_clear}
    for k in env_vars_to_clear:
        if k in os.environ:
            del os.environ[k]
    
    try:
        # Missing required fields
        with pytest.raises(ValueError):
            Config()
        
        # Invalid date format
        os.environ["S3_BUCKET_NAME"] = "test-bucket"
        os.environ["POST_URL"] = "https://api.example.com/vcons"
        os.environ["START_DATE"] = "invalid-date"
        
        with pytest.raises(ValueError):
            Config()
    finally:
        # Restore env vars
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v


def test_config_get_method():
    """Test get method with dot notation."""
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    os.environ["POST_URL"] = "https://api.example.com/vcons"
    os.environ["START_DATE"] = "2024-01-01"
    
    config = Config()
    assert config.get("s3.bucket") == "test-bucket"
    assert config.get("nonexistent.key", "default") == "default"


def test_config_build_post_headers():
    """Test building POST headers from auth config."""
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    os.environ["POST_URL"] = "https://api.example.com/vcons"
    os.environ["START_DATE"] = "2024-01-01"
    os.environ["POST_AUTH_TYPE"] = "bearer"
    os.environ["POST_AUTH_TOKEN"] = "test-token"
    
    config = Config()
    assert "Authorization" in config["post"]["headers"]
    assert config["post"]["headers"]["Authorization"] == "Bearer test-token"
    assert config["post"]["headers"]["Content-Type"] == "application/json"


def test_config_from_env_file():
    """Test loading configuration from .env file."""
    # Clear env vars first
    env_vars_to_clear = ["S3_BUCKET_NAME", "POST_URL", "START_DATE"]
    saved_env = {k: os.environ.get(k) for k in env_vars_to_clear}
    for k in env_vars_to_clear:
        if k in os.environ:
            del os.environ[k]
    
    try:
        # Create temporary .env file
        env_content = """S3_BUCKET_NAME=env-bucket
POST_URL=https://env-api.example.com/vcons
START_DATE=2024-01-01
S3_PREFIX=env-prefix/
POST_AUTH_TOKEN=env-token
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(env_content)
            env_path = f.name
        
        try:
            config = Config(env_file=env_path)
            assert config["s3"]["bucket"] == "env-bucket"
            assert config["post"]["url"] == "https://env-api.example.com/vcons"
            assert config["processing"]["start_date"] == "2024-01-01"
            assert config["s3"]["prefix"] == "env-prefix/"
        finally:
            Path(env_path).unlink()
    finally:
        # Restore env vars
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v


def test_config_env_file_priority():
    """Test that environment variables override .env file values."""
    # Set environment variable
    os.environ["S3_BUCKET_NAME"] = "env-var-bucket"
    os.environ["POST_URL"] = "https://api.example.com/vcons"
    os.environ["START_DATE"] = "2024-01-01"
    
    try:
        # Create .env file with different value
        env_content = """S3_BUCKET_NAME=env-file-bucket
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(env_content)
            env_path = f.name
        
        try:
            config = Config(env_file=env_path)
            # Environment variable should take precedence
            assert config["s3"]["bucket"] == "env-var-bucket"
        finally:
            Path(env_path).unlink()
    finally:
        # Clean up
        if "S3_BUCKET_NAME" in os.environ:
            del os.environ["S3_BUCKET_NAME"]

