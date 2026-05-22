"""Unified configuration manager for Custom Crawler Scraper."""

import os
from typing import Any, Optional

import yaml


class ConfigManager:
    """Unified configuration manager supporting multiple sources."""

    def __init__(self, config_path: str = "config/sources.yaml"):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to YAML configuration file
        """
        self._config_path = config_path
        self._defaults = {
            # Database
            "DATABASE_PATH": "custom_crawler.db",
            # GitHub scraping
            "GITHUB_TRENDING_URL": "https://github.com/trending",
            "REQUEST_TIMEOUT": 30,
            "REQUEST_DELAY_MIN": 1,
            "REQUEST_DELAY_MAX": 2,
            # HTML generation
            "ITEMS_PER_PAGE": 50,
            "OUTPUT_DIR": ".",
            "TEMPLATE_DIR": "templates",
            # Reports
            "REPORTS_DIR": "reports",
            # Logging
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "%(asctime)s - %(levelname)s - %(message)s",
            "LOG_DIR": "logs",
            "LOG_FILE": "scraper.log",
            "LOG_MAX_BYTES": 10 * 1024 * 1024,  # 10MB
            "LOG_BACKUP_COUNT": 5,
            # Scheduling
            "DEFAULT_SCHEDULE_HOUR": 8,
            "DEFAULT_SCHEDULE_MINUTE": 0,
            # GitHub GraphQL
            "GITHUB_TOKEN": None,
            # Product Hunt
            "PH_API_KEY": None,
            # HTTP Proxy
            "HTTP_PROXY": None,
            # Retry
            "MAX_RETRIES": 3,
            "RETRY_DELAY": 1,
        }
        self._yaml_config = self._load_yaml()

    def _load_yaml(self) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with priority:
        1. Environment variable
        2. YAML config
        3. Default value

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        # 1. Check environment variable
        env_value = os.getenv(key)
        if env_value is not None:
            return self._convert_type(env_value, key)

        # 2. Check YAML config
        if key in self._yaml_config:
            return self._yaml_config[key]

        # 3. Check defaults
        if key in self._defaults:
            return self._defaults[key]

        # 4. Return provided default
        return default

    def _convert_type(self, value: str, key: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Check if default is an integer
        default = self._defaults.get(key)
        if isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return value
        # Check if default is a boolean
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes", "on")
        return value

    def get_database_path(self) -> str:
        """Get database path."""
        return self.get("DATABASE_PATH", "custom_crawler.db")

    def get_github_trending_url(self) -> str:
        """Get GitHub trending URL."""
        return self.get("GITHUB_TRENDING_URL", "https://github.com/trending")

    def get_request_timeout(self) -> int:
        """Get request timeout."""
        return self.get("REQUEST_TIMEOUT", 30)

    def get_request_delay(self) -> tuple:
        """Get request delay range (min, max)."""
        return (
            self.get("REQUEST_DELAY_MIN", 1),
            self.get("REQUEST_DELAY_MAX", 2),
        )

    def get_items_per_page(self) -> int:
        """Get items per page."""
        return self.get("ITEMS_PER_PAGE", 50)

    def get_output_dir(self) -> str:
        """Get output directory."""
        return self.get("OUTPUT_DIR", "output")

    def get_reports_dir(self) -> str:
        """Get reports directory."""
        return self.get("REPORTS_DIR", "reports")

    def get_log_level(self) -> str:
        """Get log level."""
        return self.get("LOG_LEVEL", "INFO")

    def get_log_format(self) -> str:
        """Get log format."""
        return self.get("LOG_FORMAT", "%(asctime)s - %(levelname)s - %(message)s")

    def get_log_dir(self) -> str:
        """Get log directory."""
        return self.get("LOG_DIR", "logs")

    def get_log_file(self) -> str:
        """Get log file name."""
        return self.get("LOG_FILE", "scraper.log")

    def get_log_max_bytes(self) -> int:
        """Get log max bytes."""
        return self.get("LOG_MAX_BYTES", 10 * 1024 * 1024)

    def get_log_backup_count(self) -> int:
        """Get log backup count."""
        return self.get("LOG_BACKUP_COUNT", 5)

    def get_github_token(self) -> Optional[str]:
        """Get GitHub token."""
        return self.get("GITHUB_TOKEN")

    def get_ph_api_key(self) -> Optional[str]:
        """Get Product Hunt API key."""
        return self.get("PH_API_KEY")

    def get_http_proxy(self) -> Optional[str]:
        """Get HTTP proxy."""
        return self.get("HTTP_PROXY")

    def get_max_retries(self) -> int:
        """Get max retries."""
        return self.get("MAX_RETRIES", 3)

    def get_retry_delay(self) -> int:
        """Get retry delay."""
        return self.get("RETRY_DELAY", 1)


# Singleton ConfigManager for module-level constant access
_config = ConfigManager()


def get_config(config_path: str = "config/sources.yaml") -> ConfigManager:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = ConfigManager(config_path)
    return _config

DATABASE_PATH = _config.get_database_path()
GITHUB_TRENDING_URL = _config.get_github_trending_url()
REQUEST_TIMEOUT = _config.get_request_timeout()
REQUEST_DELAY_MIN = _config.get_request_delay()[0]
REQUEST_DELAY_MAX = _config.get_request_delay()[1]
ITEMS_PER_PAGE = _config.get_items_per_page()
OUTPUT_DIR = _config.get_output_dir()
TEMPLATE_DIR = _config.get("TEMPLATE_DIR", "templates")
REPORTS_DIR = _config.get_reports_dir()
LOG_LEVEL = _config.get_log_level()
LOG_FORMAT = _config.get_log_format()
LOG_DIR = _config.get_log_dir()
LOG_FILE = _config.get_log_file()
LOG_MAX_BYTES = _config.get_log_max_bytes()
LOG_BACKUP_COUNT = _config.get_log_backup_count()
DEFAULT_SCHEDULE_HOUR = _config.get("DEFAULT_SCHEDULE_HOUR", 8)
DEFAULT_SCHEDULE_MINUTE = _config.get("DEFAULT_SCHEDULE_MINUTE", 0)
GITHUB_TOKEN = _config.get_github_token()
PH_API_KEY = _config.get_ph_api_key()
HTTP_PROXY = _config.get_http_proxy()
MAX_RETRIES = _config.get_max_retries()
RETRY_DELAY = _config.get_retry_delay()
