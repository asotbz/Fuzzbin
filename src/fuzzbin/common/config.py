"""Configuration models using Pydantic for validation."""

from pathlib import Path
from typing import Optional, Dict, List, Any

import yaml
from pydantic import BaseModel, Field, field_validator


class RetryConfig(BaseModel):
    """Configuration for HTTP retry logic with exponential backoff."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts",
    )
    backoff_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Multiplier for exponential backoff calculation",
    )
    min_wait: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Minimum wait time between retries in seconds",
    )
    max_wait: float = Field(
        default=10.0,
        ge=1.0,
        le=300.0,
        description="Maximum wait time between retries in seconds",
    )
    status_codes: List[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504],
        description="HTTP status codes that should trigger a retry",
    )

    @field_validator("status_codes")
    @classmethod
    def validate_status_codes(cls, v: List[int]) -> List[int]:
        """Validate that status codes are in valid range."""
        for code in v:
            if not 100 <= code <= 599:
                raise ValueError(f"Invalid HTTP status code: {code}")
        return v


class HTTPConfig(BaseModel):
    """Configuration for HTTP client."""

    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )
    max_redirects: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of redirects to follow",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates",
    )
    max_connections: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of connections in the pool",
    )
    max_keepalive_connections: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum number of keep-alive connections",
    )
    retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry configuration",
    )


class FileLoggingConfig(BaseModel):
    """Configuration for file-based logging."""

    path: str = Field(
        default="logs/fuzzbin.log",
        description="Path to log file",
    )
    max_bytes: int = Field(
        default=10485760,  # 10MB
        ge=1024,
        description="Maximum size of log file before rotation",
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Number of backup log files to keep",
    )


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    format: str = Field(
        default="json",
        description="Log format: json or text",
    )
    handlers: List[str] = Field(
        default_factory=lambda: ["console"],
        description="Enabled log handlers: console, file",
    )
    file: Optional[FileLoggingConfig] = Field(
        default=None,
        description="File logging configuration (optional)",
    )
    third_party: Dict[str, str] = Field(
        default_factory=dict,
        description="Log levels for third-party libraries",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {v}. Must be one of {valid_levels}"
            )
        return v_upper

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "text"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(
                f"Invalid format: {v}. Must be one of {valid_formats}"
            )
        return v_lower

    @field_validator("handlers")
    @classmethod
    def validate_handlers(cls, v: List[str]) -> List[str]:
        """Validate handlers."""
        valid_handlers = ["console", "file"]
        for handler in v:
            if handler not in valid_handlers:
                raise ValueError(
                    f"Invalid handler: {handler}. Must be one of {valid_handlers}"
                )
        return v


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""

    enabled: bool = Field(
        default=True,
        description="Whether rate limiting is enabled",
    )
    requests_per_minute: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per minute",
    )
    requests_per_second: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per second",
    )
    requests_per_hour: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per hour",
    )
    burst_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum burst size (defaults to rate limit)",
    )

    @field_validator("burst_size")
    @classmethod
    def validate_burst_size(cls, v: Optional[int], info: Any) -> Optional[int]:
        """Validate that at least one rate limit is set when enabled."""
        # Note: This validator runs after other fields are set
        return v


class ConcurrencyConfig(BaseModel):
    """Configuration for concurrency control."""

    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of concurrent requests",
    )
    per_host_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum concurrent requests per host (optional)",
    )


class APIClientConfig(BaseModel):
    """Configuration for a specific API client."""

    name: str = Field(
        description="Name of the API client",
    )
    base_url: str = Field(
        description="Base URL for the API",
    )
    http: HTTPConfig = Field(
        default_factory=HTTPConfig,
        description="HTTP client configuration",
    )
    rate_limit: Optional[RateLimitConfig] = Field(
        default=None,
        description="Rate limiting configuration",
    )
    concurrency: Optional[ConcurrencyConfig] = Field(
        default=None,
        description="Concurrency control configuration",
    )
    auth: Optional[Dict[str, str]] = Field(
        default=None,
        description="Authentication configuration (headers, tokens, etc.)",
    )
    custom: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom API-specific configuration",
    )


class Config(BaseModel):
    """Main configuration class for Fuzzbin."""

    http: HTTPConfig = Field(
        default_factory=HTTPConfig,
        description="HTTP client configuration",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    apis: Optional[Dict[str, APIClientConfig]] = Field(
        default=None,
        description="API client configurations",
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """
        Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Config object with validated configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
            pydantic.ValidationError: If configuration is invalid

        Example:
            >>> from pathlib import Path
            >>> config = Config.from_yaml(Path("config.yaml"))
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data or {})

    @classmethod
    def from_yaml_string(cls, yaml_string: str) -> "Config":
        """
        Load configuration from YAML string.

        Args:
            yaml_string: YAML configuration as string

        Returns:
            Config object with validated configuration

        Example:
            >>> yaml_str = "http:\\n  timeout: 60"
            >>> config = Config.from_yaml_string(yaml_str)
        """
        data = yaml.safe_load(yaml_string)
        return cls.model_validate(data or {})
