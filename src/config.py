"""Configuration management for vCon S3 Loader."""

import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager that supports environment variables and YAML files."""

    def __init__(self, config_file: Optional[str] = None, env_file: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_file: Optional path to YAML/JSON configuration file
            env_file: Optional path to .env file (defaults to .env in current directory)
        """
        self.config: Dict[str, Any] = {}
        
        # Load .env file first (before defaults and config file)
        self._load_env_file(env_file)
        
        self._load_defaults()
        
        if config_file and Path(config_file).exists():
            self._load_from_file(config_file)
        
        self._load_from_env()
        self._validate()

    def _load_env_file(self, env_file: Optional[str] = None):
        """
        Load environment variables from .env file.
        
        Args:
            env_file: Optional path to .env file. If None, looks for .env in current directory.
        """
        if not DOTENV_AVAILABLE:
            logger.warning("python-dotenv not installed, skipping .env file loading")
            return
        
        # Determine .env file path
        if env_file:
            env_path = Path(env_file)
        else:
            # Look for .env in current directory and parent directories
            env_path = Path(".env")
            if not env_path.exists():
                # Try parent directory
                env_path = Path("..") / ".env"
        
        if env_path.exists():
            logger.debug(f"Loading environment variables from {env_path}")
            load_dotenv(env_path, override=False)  # Don't override existing env vars
            logger.info(f"Loaded .env file from {env_path}")
        else:
            logger.debug(f"No .env file found at {env_path}")

    def _load_defaults(self):
        """Load default configuration values."""
        self.config = {
            "s3": {
                "bucket": os.getenv("S3_BUCKET_NAME", ""),
                "prefix": os.getenv("S3_PREFIX", ""),
                "region": os.getenv("AWS_REGION", "us-east-1"),
            },
            "post": {
                "url": os.getenv("POST_URL", ""),
                "headers": {},
                "auth_type": os.getenv("POST_AUTH_TYPE", "bearer"),
                "auth_token": os.getenv("POST_AUTH_TOKEN", ""),
                "use_vcon_method": os.getenv("POST_USE_VCON_METHOD", "false").lower() == "true",
                "retry_attempts": int(os.getenv("RETRY_ATTEMPTS", "3")),
                "retry_backoff_base": int(os.getenv("RETRY_BACKOFF_BASE", "2")),
            },
            "rate_limit": {
                "requests_per_second": float(os.getenv("RATE_LIMIT_REQUESTS_PER_SECOND", "10")),
            },
            "processing": {
                "start_date": os.getenv("START_DATE", ""),
                "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
                "checkpoint_file": os.getenv("CHECKPOINT_FILE", ".checkpoint.json"),
                "batch_size": int(os.getenv("BATCH_SIZE", "1")),
                "validate_vcon": os.getenv("VALIDATE_VCON", "true").lower() == "true",
                "migrate_version": os.getenv("MIGRATE_VERSION", "false").lower() == "true",
            },
            "redis": {
                "url": os.getenv("REDIS_URL", "redis://localhost:6379"),
                "enabled": os.getenv("REDIS_ENABLED", "true").lower() == "true",
                "key_prefix": os.getenv("REDIS_KEY_PREFIX", "vcon-loader"),
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
            },
        }

    def _load_from_file(self, config_file: str):
        """Load configuration from YAML or JSON file."""
        path = Path(config_file)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(path, "r") as f:
            if path.suffix.lower() in [".yaml", ".yml"]:
                file_config = yaml.safe_load(f) or {}
            elif path.suffix.lower() == ".json":
                file_config = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {path.suffix}")

        # Merge file config into defaults
        self._merge_config(self.config, file_config)

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]):
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _load_from_env(self):
        """Load configuration from environment variables (takes precedence)."""
        # S3 Configuration
        if os.getenv("S3_BUCKET_NAME"):
            self.config["s3"]["bucket"] = os.getenv("S3_BUCKET_NAME")
        if os.getenv("S3_PREFIX"):
            self.config["s3"]["prefix"] = os.getenv("S3_PREFIX")
        if os.getenv("AWS_REGION"):
            self.config["s3"]["region"] = os.getenv("AWS_REGION")

        # POST Configuration
        if os.getenv("POST_URL"):
            self.config["post"]["url"] = os.getenv("POST_URL")
        if os.getenv("POST_AUTH_TYPE"):
            self.config["post"]["auth_type"] = os.getenv("POST_AUTH_TYPE")
        if os.getenv("POST_AUTH_TOKEN"):
            self.config["post"]["auth_token"] = os.getenv("POST_AUTH_TOKEN")
        if os.getenv("POST_USE_VCON_METHOD"):
            self.config["post"]["use_vcon_method"] = os.getenv("POST_USE_VCON_METHOD").lower() == "true"
        if os.getenv("RETRY_ATTEMPTS"):
            self.config["post"]["retry_attempts"] = int(os.getenv("RETRY_ATTEMPTS"))
        if os.getenv("RETRY_BACKOFF_BASE"):
            self.config["post"]["retry_backoff_base"] = int(os.getenv("RETRY_BACKOFF_BASE"))

        # Rate Limit
        if os.getenv("RATE_LIMIT_REQUESTS_PER_SECOND"):
            self.config["rate_limit"]["requests_per_second"] = float(
                os.getenv("RATE_LIMIT_REQUESTS_PER_SECOND")
            )

        # Processing Configuration
        if os.getenv("START_DATE"):
            self.config["processing"]["start_date"] = os.getenv("START_DATE")
        if os.getenv("POLL_INTERVAL_SECONDS"):
            self.config["processing"]["poll_interval_seconds"] = int(
                os.getenv("POLL_INTERVAL_SECONDS")
            )
        if os.getenv("CHECKPOINT_FILE"):
            self.config["processing"]["checkpoint_file"] = os.getenv("CHECKPOINT_FILE")
        if os.getenv("BATCH_SIZE"):
            self.config["processing"]["batch_size"] = int(os.getenv("BATCH_SIZE"))
        if os.getenv("VALIDATE_VCON"):
            self.config["processing"]["validate_vcon"] = os.getenv("VALIDATE_VCON").lower() == "true"
        if os.getenv("MIGRATE_VERSION"):
            self.config["processing"]["migrate_version"] = os.getenv("MIGRATE_VERSION").lower() == "true"

        # Redis Configuration
        if os.getenv("REDIS_URL"):
            self.config["redis"]["url"] = os.getenv("REDIS_URL")
        if os.getenv("REDIS_ENABLED"):
            self.config["redis"]["enabled"] = os.getenv("REDIS_ENABLED").lower() == "true"
        if os.getenv("REDIS_KEY_PREFIX"):
            self.config["redis"]["key_prefix"] = os.getenv("REDIS_KEY_PREFIX")

        # Logging
        if os.getenv("LOG_LEVEL"):
            self.config["logging"]["level"] = os.getenv("LOG_LEVEL")

        # Build POST headers from auth config
        self._build_post_headers()

    def _build_post_headers(self):
        """Build POST headers from authentication configuration."""
        headers = self.config["post"].get("headers", {})
        
        # Add Content-Type if not specified
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        # Add authentication header based on auth_type
        auth_type = self.config["post"].get("auth_type", "").lower()
        auth_token = self.config["post"].get("auth_token", "")
        
        if auth_token:
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {auth_token}"
            elif auth_type == "api_key":
                headers["X-API-Key"] = auth_token
            # For custom, assume token is already in headers or will be added manually
        
        self.config["post"]["headers"] = headers

    def _validate(self):
        """Validate required configuration values."""
        errors = []
        
        if not self.config["s3"]["bucket"]:
            errors.append("S3_BUCKET_NAME is required")
        
        if not self.config["post"]["url"]:
            errors.append("POST_URL is required")
        
        if not self.config["processing"]["start_date"]:
            errors.append("START_DATE is required")
        else:
            # Validate date format
            try:
                datetime.strptime(self.config["processing"]["start_date"], "%Y-%m-%d")
            except ValueError:
                errors.append(f"START_DATE must be in YYYY-MM-DD format, got: {self.config['processing']['start_date']}")
        
        if self.config["rate_limit"]["requests_per_second"] <= 0:
            errors.append("RATE_LIMIT_REQUESTS_PER_SECOND must be greater than 0")
        
        if self.config["processing"]["batch_size"] < 1:
            errors.append("BATCH_SIZE must be at least 1")
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., "s3.bucket")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value

    def __getitem__(self, key: str) -> Any:
        """Get configuration section."""
        return self.config[key]

    def __contains__(self, key: str) -> bool:
        """Check if configuration section exists."""
        return key in self.config

